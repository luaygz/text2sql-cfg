"""Content-addressed cache of API responses and embeddings in one SQLite file.

This file is the local working store; git holds the same rows as immutable shards (see
`text2sql.llm.shards`), so a reviewer without an API key can replay every run. A key is the
SHA-256 of the canonical JSON of everything that shapes the model's output (model, input items,
tools including the grammar, tool choice, reasoning, text format, output cap) plus a sample
index. Fields that only change how a request is served (service tier, prompt-cache options and
breakpoints, storage) are left out, so switching tiers or moving a breakpoint keeps cache hits.
Rows hold the zlib-compressed JSON of the SDK response object: no headers, no API key.

Embeddings are cached per (model, text, dimensions) as raw little-endian float16 when that is
lossless for the vector, else float32 (`pack_vector`). The API reports tokens and latency per
batch, so each row also stores the text's share of its batch's totals, split by UTF-8 length;
summing shares makes replayed usage, price and latency match the live call exactly.

A third table records whether the API accepted a grammar at all, keyed by grammar fingerprint,
and a fourth records requests the API refused as policy violations (`invalid_prompt`), keyed
like responses: neither has a response to cache, but both have to replay offline. Two more
tables remember which shards the store has loaded or written and which rows those hold.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import zlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

_TRANSPORT_FIELDS = frozenset({"service_tier", "prompt_cache_options", "prompt_cache_key", "store"})
_BREAKPOINT_FIELD = "prompt_cache_breakpoint"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    api_latency_s REAL NOT NULL,
    payload BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    api_latency_s REAL NOT NULL,
    dtype TEXT NOT NULL CHECK (dtype IN ('f2', 'f4')),
    vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS grammar_verdicts (
    fingerprint TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    message TEXT
);
CREATE TABLE IF NOT EXISTS flagged_requests (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shard_rows (
    kind TEXT NOT NULL,
    row_id TEXT NOT NULL,
    PRIMARY KEY (kind, row_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS shards (
    name TEXT PRIMARY KEY,
    recorded_at TEXT NOT NULL
);
"""

_UPSERT_VERDICT = (
    "INSERT INTO grammar_verdicts (fingerprint, model, created_at, accepted, message) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT (fingerprint) DO UPDATE SET model = excluded.model, "
    "created_at = excluded.created_at, accepted = 0, message = excluded.message "
    "WHERE excluded.accepted = 0"
)

ShardRow = dict[str, Any]
"""One cached row as a shard line: `kind` names the table, the other fields are its columns."""

# Columns of each table as they appear in shard lines, the key column first. Sorted by table
# name, which is the order rows are exported in.
SHARD_TABLES: dict[str, tuple[str, ...]] = {
    "embeddings": ("key", "model", "created_at", "tokens", "api_latency_s", "dtype", "vector"),
    "flagged_requests": ("key", "model", "created_at", "message"),
    "grammar_verdicts": ("fingerprint", "model", "created_at", "accepted", "message"),
    "responses": ("key", "model", "created_at", "api_latency_s", "payload"),
}


def _row_id_sql(kind: str) -> str:
    # Only verdicts change after insert (a rejection replaces an acceptance), so the verdict
    # itself is part of their identity and a later rejection is exported again.
    return "fingerprint || ':' || accepted" if kind == "grammar_verdicts" else "key"


def shard_row_id(row: ShardRow) -> str:
    if row["kind"] == "grammar_verdicts":
        return f"{row['fingerprint']}:{int(row['accepted'])}"
    return str(row["key"])


def _to_shard_value(column: str, value: Any) -> Any:  # noqa: ANN401 - a SQLite column value
    """Inline response JSON and base64 vectors: gzip over many rows compresses those far
    better than it compresses the stored zlib blobs."""
    if column == "payload":
        return json.loads(zlib.decompress(value))
    if column == "vector":
        return base64.b64encode(value).decode("ascii")
    return value


def _from_shard_value(column: str, value: Any) -> Any:  # noqa: ANN401 - a JSON value
    if column == "payload":
        return zlib.compress(canonical_json(value).encode(), level=9)
    if column == "vector":
        return base64.b64decode(value)
    return value


VectorDType = Literal["f2", "f4"]


def pack_vector(vector: Sequence[float]) -> tuple[VectorDType, bytes]:
    """Little-endian float16 bytes when every component survives the round trip exactly
    (true of every text-embedding-3-small vector we checked), float32 otherwise. Either way
    the stored vector equals the float32 vector the API returned."""
    full = np.asarray(vector, dtype="<f4")
    with np.errstate(over="ignore"):
        half = full.astype("<f2")
    if np.array_equal(half.astype("<f4"), full):
        return "f2", half.tobytes()
    return "f4", full.tobytes()


def unpack_vector(dtype: VectorDType, blob: bytes) -> list[float]:
    return [float(x) for x in np.frombuffer(blob, dtype=f"<{dtype}")]


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _without_breakpoints(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: _without_breakpoints(v) for k, v in value.items() if k != _BREAKPOINT_FIELD}
    if isinstance(value, list | tuple):
        return [_without_breakpoints(v) for v in value]
    return value


def request_key(endpoint: str, request: Mapping[str, Any], sample: int = 0) -> str:
    """Cache key for `request` sent to `endpoint`; `sample` separates repeated draws."""
    semantic = {k: v for k, v in request.items() if k not in _TRANSPORT_FIELDS}
    material = {"endpoint": endpoint, "request": _without_breakpoints(semantic), "sample": sample}
    return hashlib.sha256(canonical_json(material).encode()).hexdigest()


def embedding_request(
    model: str, inputs: str | Sequence[str], dimensions: int | None
) -> dict[str, Any]:
    """The output-shaping fields of an embeddings request. `dimensions` is left out when
    unset, so keys for full-size vectors do not depend on this option existing."""
    request: dict[str, Any] = {
        "model": model,
        "input": inputs if isinstance(inputs, str) else list(inputs),
    }
    if dimensions is not None:
        request["dimensions"] = dimensions
    return request


def embedding_key(model: str, text: str, dimensions: int | None = None) -> str:
    return request_key("embeddings", embedding_request(model, text, dimensions))


@dataclass(frozen=True)
class CachedResponse:
    payload: dict[str, Any]
    api_latency_s: float


@dataclass(frozen=True)
class CachedEmbedding:
    vector: list[float]
    tokens: int
    """This text's share of the tokens its batch was billed for."""
    api_latency_s: float
    """This text's share of its batch's API latency."""


@dataclass(frozen=True)
class GrammarVerdict:
    accepted: bool
    message: str | None
    """The API's error message when it rejected the grammar."""
    model: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class ResponseCache:
    """One connection per instance, used from a single event-loop thread. Across processes,
    SQLite's file locking serialises writers and the first writer of a key wins."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path, timeout=30.0)
        self._db.executescript(_SCHEMA)

    def get_response(self, key: str) -> CachedResponse | None:
        row = self._db.execute(
            "SELECT payload, api_latency_s FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return CachedResponse(json.loads(zlib.decompress(row[0])), row[1])

    def put_response(
        self, key: str, *, model: str, payload: dict[str, Any], api_latency_s: float
    ) -> CachedResponse:
        """Store `payload` unless the key exists, and return whichever row is stored."""
        blob = zlib.compress(canonical_json(payload).encode(), level=9)
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO responses VALUES (?, ?, ?, ?, ?)",
                (key, model, _now(), api_latency_s, blob),
            )
        stored = self.get_response(key)
        if stored is None:
            raise sqlite3.DatabaseError(f"response {key} vanished right after insert")
        return stored

    def get_embeddings(self, keys: Iterable[str]) -> dict[str, CachedEmbedding]:
        wanted = list(dict.fromkeys(keys))
        found: dict[str, CachedEmbedding] = {}
        # Chunked to stay under SQLite's bound-parameter limit.
        for start in range(0, len(wanted), 500):
            chunk = wanted[start : start + 500]
            marks = ",".join("?" * len(chunk))
            rows = self._db.execute(
                "SELECT key, dtype, vector, tokens, api_latency_s FROM embeddings "
                f"WHERE key IN ({marks})",
                chunk,
            )
            for key, dtype, blob, tokens, latency in rows:
                found[key] = CachedEmbedding(unpack_vector(dtype, blob), tokens, latency)
        return found

    def put_embeddings(
        self, model: str, rows: Mapping[str, CachedEmbedding]
    ) -> dict[str, CachedEmbedding]:
        """Store `rows` unless a key exists (see `pack_vector` for the encoding), and return
        whichever rows are stored."""
        created = _now()
        values = []
        for key, row in rows.items():
            dtype, blob = pack_vector(row.vector)
            values.append((key, model, created, row.tokens, row.api_latency_s, dtype, blob))
        with self._db:
            self._db.executemany(
                "INSERT OR IGNORE INTO embeddings "
                "(key, model, created_at, tokens, api_latency_s, dtype, vector) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                values,
            )
        return self.get_embeddings(rows)

    def get_grammar_verdict(self, fingerprint: str) -> GrammarVerdict | None:
        row = self._db.execute(
            "SELECT accepted, message, model FROM grammar_verdicts WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        return None if row is None else GrammarVerdict(bool(row[0]), row[1], row[2])

    def put_grammar_verdict(self, fingerprint: str, verdict: GrammarVerdict) -> None:
        """A rejection overrides an earlier acceptance; an acceptance never overrides anything."""
        with self._db:
            self._db.execute(
                _UPSERT_VERDICT,
                (fingerprint, verdict.model, _now(), int(verdict.accepted), verdict.message),
            )

    def get_flagged(self, key: str) -> str | None:
        """The API's message if the request with this key was refused as `invalid_prompt`."""
        row = self._db.execute(
            "SELECT message FROM flagged_requests WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    def put_flagged(self, key: str, *, model: str, message: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO flagged_requests VALUES (?, ?, ?, ?)",
                (key, model, _now(), message),
            )

    def unsharded_rows(self) -> list[ShardRow]:
        """Every row that no recorded shard holds, as shard lines sorted by table and key."""
        rows: list[ShardRow] = []
        for kind, columns in SHARD_TABLES.items():
            cursor = self._db.execute(
                f"SELECT {', '.join(columns)} FROM {kind} WHERE {_row_id_sql(kind)} NOT IN "
                f"(SELECT row_id FROM shard_rows WHERE kind = ?) ORDER BY {columns[0]}",
                (kind,),
            )
            rows.extend(
                {"kind": kind}
                | {c: _to_shard_value(c, v) for c, v in zip(columns, values, strict=True)}
                for values in cursor
            )
        return rows

    def shard_names(self) -> set[str]:
        return {name for (name,) in self._db.execute("SELECT name FROM shards")}

    def record_export(self, shard: str, rows: Iterable[ShardRow]) -> None:
        """Note that shard file `shard` now holds `rows`, which this store already has."""
        with self._db:
            for row in rows:
                self._mark(row)
            self._db.execute("INSERT OR IGNORE INTO shards VALUES (?, ?)", (shard, _now()))

    def import_shard(self, shard: str, rows: Iterable[ShardRow]) -> tuple[int, int]:
        """Load the rows of shard file `shard` in one transaction; returns (rows read, rows
        new to this store). Rows already stored win, as with live writes; verdicts merge as in
        `put_grammar_verdict`."""
        read = new = 0
        with self._db:
            for row in rows:
                kind = row.get("kind")
                columns = SHARD_TABLES.get(str(kind))
                if columns is None or set(row) != {"kind", *columns}:
                    raise ValueError(f"{shard}: not a cache row: {sorted(row)} (kind {kind!r})")
                values = [_from_shard_value(c, row[c]) for c in columns]
                sql = (
                    _UPSERT_VERDICT
                    if kind == "grammar_verdicts"
                    else f"INSERT OR IGNORE INTO {kind} ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' * len(columns))})"
                )
                new += self._db.execute(sql, values).rowcount
                read += 1
                self._mark(row)
            self._db.execute("INSERT OR IGNORE INTO shards VALUES (?, ?)", (shard, _now()))
        return read, new

    def _mark(self, row: ShardRow) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO shard_rows VALUES (?, ?)", (row["kind"], shard_row_id(row))
        )

    def close(self) -> None:
        self._db.close()
