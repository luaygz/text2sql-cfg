"""The committed form of the response cache: immutable, append-only gzip shards.

The SQLite store under `cache/llm/` is a local working file and is not committed. A binary file
that changes on every run would add a full copy of itself to git history with every commit, and
GitHub refuses files over 100 MB. Git holds `cache/llm/shards/*.jsonl.gz` instead. An export
writes every local row that no shard holds yet into new shard files, which are never rewritten;
an import loads shards into the store. `open_cache` imports any shard the store has not seen
yet, so fresh clones, CI, containers and offline replays need no extra step.

Each line is one row as canonical JSON (`kind` names its table; see `cache.SHARD_TABLES`),
rows are sorted by table and key, and gzip's timestamp and file name fields are left empty, so
the same rows always give the same bytes. A shard is named `<UTC export time>-<first 8 hex of
the file's SHA-256>.jsonl.gz`. Shards import in name order and rows already stored win, so when
two shards disagree on a key (two machines recorded the same request) the older shard's row
is the one kept.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog

from text2sql.llm.cache import ResponseCache, ShardRow, canonical_json

CACHE_FILENAME = "responses.sqlite"
SHARD_SUFFIX = ".jsonl.gz"
MAX_SHARD_BYTES = 45_000_000
"""A shard closes once its compressed size reaches this, keeping files well under 50 MB."""

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ShardWrite:
    path: Path
    rows: int
    size_bytes: int


@dataclass(frozen=True)
class ShardImport:
    name: str
    rows: int
    new_rows: int
    """Rows the store did not hold before."""


def shard_dir(cache_dir: Path) -> Path:
    return cache_dir / "shards"


def open_cache(cache_dir: Path) -> ResponseCache:
    """The SQLite store under `cache_dir`, after importing every shard it has not seen."""
    cache = ResponseCache(cache_dir / CACHE_FILENAME)
    try:
        imported = import_shards(cache, shard_dir(cache_dir))
    except BaseException:
        cache.close()
        raise
    if imported:
        log.info(
            "llm.cache.shards_imported",
            shards=len(imported),
            new_rows=sum(s.new_rows for s in imported),
        )
    return cache


def pending_shards(cache: ResponseCache, directory: Path) -> list[Path]:
    """Shard files in `directory` the store has neither imported nor written, in name order.
    A directory listing and one small query, cheap enough to run whenever a client starts."""
    if not directory.is_dir():
        return []
    seen = cache.shard_names()
    return sorted(p for p in directory.glob(f"*{SHARD_SUFFIX}") if p.name not in seen)


def import_shards(cache: ResponseCache, directory: Path) -> list[ShardImport]:
    imported = []
    for path in pending_shards(cache, directory):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            rows, new = cache.import_shard(path.name, (json.loads(line) for line in fh))
        imported.append(ShardImport(path.name, rows, new))
    return imported


def export_shards(
    cache: ResponseCache,
    directory: Path,
    *,
    max_bytes: int = MAX_SHARD_BYTES,
    now: datetime | None = None,
) -> list[ShardWrite]:
    """Write every row no shard holds into new shards; returns nothing when all are covered.

    Pending shards are imported first, so rows that arrived in someone else's shard are not
    exported a second time."""
    import_shards(cache, directory)
    rows = cache.unsharded_rows()
    if not rows:
        return []
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    written = []
    for data, chunk in pack_rows(rows, max_bytes):
        path = directory / f"{stamp}-{hashlib.sha256(data).hexdigest()[:8]}{SHARD_SUFFIX}"
        partial = directory / f".{path.name}.partial"
        partial.write_bytes(data)
        partial.replace(path)
        cache.record_export(path.name, chunk)
        written.append(ShardWrite(path, len(chunk), len(data)))
    return written


def pack_rows(
    rows: Sequence[ShardRow], max_bytes: int
) -> Iterator[tuple[bytes, Sequence[ShardRow]]]:
    """Gzip `rows` into shard files of about `max_bytes` each, in order; the split points
    depend only on the rows, so the output is deterministic too."""
    start = 0
    buffer = io.BytesIO()
    gz = _gzip_writer(buffer)
    for index, row in enumerate(rows):
        gz.write((canonical_json(row) + "\n").encode())
        if buffer.tell() >= max_bytes:
            gz.close()
            yield buffer.getvalue(), rows[start : index + 1]
            start, buffer = index + 1, io.BytesIO()
            gz = _gzip_writer(buffer)
    gz.close()
    if start < len(rows):
        yield buffer.getvalue(), rows[start:]


def _gzip_writer(buffer: io.BytesIO) -> gzip.GzipFile:
    return gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=buffer, mtime=0)
