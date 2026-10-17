"""Stage 2 value retrieval: match question literals and keywords to stored database values.

Offline, per database, the distinct values of the columns worth searching are put in a MinHash
LSH (`lsh.py`). Online, `ValueIndex.match` runs three passes over the analysis' literals and
keywords, following CHESS's `retrieve_entity` (docs/research/prompts-from-papers.md, Part 1 §1):

1. case- and whitespace-insensitive exact match against every indexed value;
2. LSH candidates for each search string (the term, the parts left and right of each space,
   the right-hand side of `=`), top 10 by estimated Jaccard, kept when difflib's ratio is at
   least 0.3, then per column only those within 0.9 of the column's best ratio;
3. with an LLM client, an embedding re-rank of those survivors only: cosine at least 0.6 to
   the search string, then per column within 0.9 of the column's best cosine.

Which columns are indexed (`eligible_column`, `keep_column`) is CHESS's filter with two
additions: date-typed columns are skipped by type, and columns whose values mostly look like
numbers, dates, times, URLs, e-mail addresses or UUIDs are skipped by content. Neither kind is
a value a question names in words, and 3-gram similarity between digit strings is noise.

Tenant data. A tenant-scoped table (catalog `samples_withheld`) is indexed only when a scope
policy is given, and then only its low-cardinality columns, and only the values present in
every tenant (shared vocabulary such as deal stages or ticket statuses). The index is shared by
all tenants' requests, so anything specific to some tenants (account names, planted canaries,
free text) must never be in it; see docs/adr/011-retrieval.md.
"""

from __future__ import annotations

import difflib
import re
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from text2sql.catalog import Catalog, CatalogColumn, CatalogTable
from text2sql.llm import CallMeta
from text2sql.retrieval.calls import EmbeddingLLM, embed
from text2sql.retrieval.lsh import (
    NGRAM,
    NUM_PERM,
    SCHEME,
    BandIndex,
    normalize,
    signature,
    signatures,
)
from text2sql.retrieval.store import database_dir, dataset_of, missing
from text2sql.retrieval.types import QuestionAnalysis, ValueMatches
from text2sql.safety.policy import ScopePolicy

PURPOSE = "retrieval.values"

LSH_TOP_N = 10
EDIT_THRESHOLD = 0.3
EMBEDDING_THRESHOLD = 0.6
RELATIVE_CUT = 0.9
"""CHESS's settings (retrieve_entity.py, run_preprocess.sh)."""
MAX_VALUES_PER_COLUMN = 5
"""Same as `render_matched_values` shows per column."""

MAX_VALUE_CHARS = 100
"""Longer values are prose, never a literal a question repeats."""
# CHESS's size filter (db_values/preprocess.py): keep a column if it is a name column under 5M
# characters of distinct values, or under 2M characters with values averaging under 25, or if it
# has fewer than 100 distinct values. It bounds the index of free-text columns.
NAME_COLUMN_MAX_CHARS = 5_000_000
COLUMN_MAX_CHARS = 2_000_000
COLUMN_MAX_AVG_CHARS = 25
SMALL_COLUMN_DISTINCT = 100
NON_ENTITY_SHARE = 0.5
"""A column is skipped when more than this share of its values look like numbers, dates, etc."""
VOCABULARY_MAX_DISTINCT = 50
"""Tenant-table columns with more distinct values than this are records, not vocabulary."""

_SKIP_TOKENS = frozenset(
    {"id", "ids", "uuid", "guid", "url", "uri", "link", "email", "web", "website", "phone",
     "fax", "date", "time", "timestamp", "datetime", "address", "street", "str"}
)  # fmt: skip
"""CHESS skips names containing `_id`, ` id`, url, email, web, time, phone, date, address or
ending in `Id`; matching whole name tokens instead avoids skipping e.g. `candidate`. Street
columns are addresses under another name (california_schools has four with ~13,000 values each)."""
_DATE_TYPES = frozenset({"DATE", "DATETIME", "TIME", "TIMESTAMP"})
_NAME_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_NON_ENTITY = re.compile(
    r"""^(
        [^A-Za-z]*\d[^A-Za-z]*                    # number, date, phone, zip: digits, no letters
      | \d{1,4}[-/.:]\d{1,2}([-/.:T\ ]\d{1,4})*.* # date or time with a suffix
      | (https?://|www\.).*                       # URL
      | [^@\s]+@[^@\s]+\.[^@\s]+                  # e-mail
      | [0-9a-f]{8}-[0-9a-f]{4}-.*                # UUID
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
_QUOTED = re.compile(r"""'([^']{2,})'|"([^"]{2,})\"""")


def name_tokens(name: str) -> list[str]:
    return [t.lower() for t in _NAME_TOKEN.findall(name)]


def eligible_column(column: CatalogColumn) -> bool:
    """Name and type filter: text-like, not a key, not an id/url/email/phone/date/address."""
    declared = column.type.upper()
    if column.primary_key or declared in _DATE_TYPES:
        return False
    if declared and not any(t in declared for t in ("CHAR", "CLOB", "TEXT")):
        return False
    return not _SKIP_TOKENS.intersection(name_tokens(column.name))


def keep_column(name: str, values: Sequence[str]) -> bool:
    """CHESS's size filter plus the content filter, on a column's distinct text values."""
    if not values:
        return False
    total = sum(len(v) for v in values)
    small_enough = (
        ("name" in name.lower() and total < NAME_COLUMN_MAX_CHARS)
        or (total < COLUMN_MAX_CHARS and total / len(values) < COLUMN_MAX_AVG_CHARS)
        or len(values) < SMALL_COLUMN_DISTINCT
    )
    non_entity = sum(bool(_NON_ENTITY.match(v.strip())) for v in values)
    return small_enough and non_entity <= NON_ENTITY_SHARE * len(values)


def search_strings(term: str) -> list[str]:
    """CHESS's search strings for one keyword: the keyword, the part before and after every
    space, and the right-hand side of an `=`; enclosing quotes removed, duplicates and blanks
    dropped."""
    out = [term]
    for i, ch in enumerate(term):
        if ch == " ":
            out += [term[:i], term[i + 1 :]]
    if "=" in term:
        out.append(term.split("=", 1)[1])
    return list(dict.fromkeys(s for s in map(_unquote, out) if s))


def _unquote(text: str) -> str:
    s = text.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"`":
        s = s[1:-1].strip()
    return s


def edit_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


class _IndexedColumn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    table: str
    column: str
    values: list[str]


class _IndexFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format_version: Literal[1] = 1
    db_id: str
    num_perm: int = NUM_PERM
    ngram: int = NGRAM
    scheme: str = SCHEME
    columns: list[_IndexedColumn]


@dataclass(frozen=True)
class _Candidate:
    value_id: int
    search: str
    edit: float


@dataclass(frozen=True)
class ValueIndex:
    """Distinct values of one database's searchable columns, with exact and LSH lookup."""

    db_id: str
    columns: tuple[tuple[str, str], ...]
    """(table, column) in catalog spelling; `value_columns` indexes into this."""
    values: tuple[str, ...]
    value_columns: npt.NDArray[np.int32]
    bands: BandIndex
    _exact: dict[str, list[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for i, v in enumerate(self.values):
            self._exact.setdefault(normalize(v), []).append(i)

    @classmethod
    def build(
        cls, catalog: Catalog, db_path: Path, *, policy: ScopePolicy | None = None
    ) -> ValueIndex:
        """Read the distinct values of every eligible column from the read-only database."""
        indexed: list[_IndexedColumn] = []
        with closing(_connect(db_path)) as conn:
            tenants = _tenant_count(conn, catalog, policy)
            for table in catalog.tables:
                for column in table.columns:
                    if not eligible_column(column):
                        continue
                    values = _column_values(conn, table, column, policy, tenants)
                    if values is not None and keep_column(column.name, values):
                        indexed.append(
                            _IndexedColumn(table=table.name, column=column.name, values=values)
                        )
        return cls._from_columns(catalog.db_id, indexed, None)

    @classmethod
    def _from_columns(
        cls, db_id: str, indexed: Sequence[_IndexedColumn], bands: BandIndex | None
    ) -> ValueIndex:
        values = tuple(v for c in indexed for v in c.values)
        owners = np.repeat(
            np.arange(len(indexed), dtype=np.int32), [len(c.values) for c in indexed]
        )
        if bands is None:
            bands = BandIndex.build(signatures(values))
        if bands.size != len(values):
            raise ValueError(
                f"value index of {db_id}: {bands.size} signatures, {len(values)} values"
            )
        return cls(
            db_id=db_id,
            columns=tuple((c.table, c.column) for c in indexed),
            values=values,
            value_columns=owners,
            bands=bands,
        )

    @classmethod
    def load(cls, db_id: str) -> ValueIndex:
        directory = database_dir(db_id)
        path = directory / "values.json"
        if not path.is_file():
            raise missing(path, dataset_of(db_id))
        stored = _IndexFile.model_validate_json(path.read_bytes())
        if (stored.num_perm, stored.ngram, stored.scheme) != (NUM_PERM, NGRAM, SCHEME):
            raise ValueError(f"{path} was built with other LSH parameters; rebuild it")
        return cls._from_columns(stored.db_id, stored.columns, BandIndex.load(directory))

    def save(self) -> None:
        directory = database_dir(self.db_id)
        directory.mkdir(parents=True, exist_ok=True)
        stored = _IndexFile(db_id=self.db_id, columns=list(self._columns()))
        self.bands.save(directory)
        (directory / "values.json").write_text(stored.model_dump_json(), encoding="utf-8")

    def _columns(self) -> Iterator[_IndexedColumn]:
        for i, (table, column) in enumerate(self.columns):
            ids = np.flatnonzero(self.value_columns == i)
            yield _IndexedColumn(table=table, column=column, values=[self.values[j] for j in ids])

    def column_values(self, table: str, column: str) -> list[str]:
        """Every indexed value of one column (empty when the column is not indexed)."""
        key = (table.lower(), column.lower())
        for i, (t, c) in enumerate(self.columns):
            if (t.lower(), c.lower()) == key:
                return [self.values[j] for j in np.flatnonzero(self.value_columns == i)]
        return []

    async def match(
        self, analysis: QuestionAnalysis, *, question: str, llm: EmbeddingLLM | None
    ) -> tuple[ValueMatches, list[CallMeta]]:
        """Values for the question's literals and keywords, per column, best first.

        Quoted strings in `question` are searched as well, in case the analysis reworded
        them. Without `llm` the embedding pass is skipped and the edit-similarity cut decides.
        """
        terms = [*analysis.literals, *analysis.keywords, *_quoted(question)]
        strings = list(dict.fromkeys(s for t in terms for s in search_strings(t)))
        exact: dict[int, None] = {}
        fuzzy: dict[int, _Candidate] = {}
        for s in strings:
            exact.update(dict.fromkeys(self._exact.get(normalize(s), ())))
            for vid, _ in self.bands.query(signature(s), LSH_TOP_N):
                score = edit_similarity(s, self.values[vid])
                best = fuzzy.get(vid)
                if score >= EDIT_THRESHOLD and (best is None or score > best.edit):
                    fuzzy[vid] = _Candidate(vid, s, score)
        survivors = _relative_cut(
            [c for c in fuzzy.values() if c.value_id not in exact],
            lambda c: c.edit,
            self.value_columns,
        )
        calls: list[CallMeta] = []
        if llm is not None and survivors:
            survivors, meta = await self._rerank(survivors, llm)
            calls.append(meta)
        else:
            survivors.sort(key=lambda c: (-c.edit, c.value_id))
        matches: ValueMatches = {}
        for vid in [*exact, *(c.value_id for c in survivors)]:
            found = matches.setdefault(self.columns[int(self.value_columns[vid])], [])
            if len(found) < MAX_VALUES_PER_COLUMN and self.values[vid] not in found:
                found.append(self.values[vid])
        return matches, calls

    async def _rerank(
        self, candidates: list[_Candidate], llm: EmbeddingLLM
    ) -> tuple[list[_Candidate], CallMeta]:
        texts = list(
            dict.fromkeys(
                [*(c.search for c in candidates), *(self.values[c.value_id] for c in candidates)]
            )
        )
        vectors, meta = await embed(llm, texts, purpose=PURPOSE)
        row = {t: i for i, t in enumerate(texts)}
        cosine = {
            c.value_id: float(vectors[row[c.search]] @ vectors[row[self.values[c.value_id]]])
            for c in candidates
        }
        kept = [c for c in candidates if cosine[c.value_id] >= EMBEDDING_THRESHOLD]
        ranked = _relative_cut(kept, lambda c: cosine[c.value_id], self.value_columns)
        ranked.sort(key=lambda c: (-cosine[c.value_id], c.value_id))
        return ranked, meta


def _relative_cut(
    candidates: Sequence[_Candidate],
    score: Callable[[_Candidate], float],
    value_columns: np.ndarray,
) -> list[_Candidate]:
    """Per column, the candidates scoring at least RELATIVE_CUT of the column's best."""
    best: dict[int, float] = {}
    for c in candidates:
        col = int(value_columns[c.value_id])
        best[col] = max(best.get(col, 0.0), score(c))
    return [
        c for c in candidates if score(c) >= RELATIVE_CUT * best[int(value_columns[c.value_id])]
    ]


def _quoted(question: str) -> list[str]:
    return [a or b for a, b in _QUOTED.findall(question)]


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _tenant_count(conn: sqlite3.Connection, catalog: Catalog, policy: ScopePolicy | None) -> int:
    """Tenants across all tenant-scoped tables of the catalog (0 without a policy)."""
    if policy is None:
        return 0
    tables = [t.name for t in catalog.tables if policy.is_tenant_scoped(t.name)]
    if not tables:
        return 0
    col = _ident(policy.tenant_column)
    union = " UNION ALL ".join(f"SELECT {col} AS tenant FROM {_ident(t)}" for t in tables)
    return int(conn.execute(f"SELECT COUNT(DISTINCT tenant) FROM ({union})").fetchone()[0])


def _column_values(
    conn: sqlite3.Connection,
    table: CatalogTable,
    column: CatalogColumn,
    policy: ScopePolicy | None,
    tenants: int,
) -> list[str] | None:
    """Distinct non-blank text values (None: the column must not be indexed at all)."""
    t, c = _ident(table.name), _ident(column.name)
    text = f"typeof({c}) = 'text' AND TRIM({c}) <> '' AND LENGTH({c}) <= {MAX_VALUE_CHARS}"
    if not table.samples_withheld:
        rows = conn.execute(f"SELECT DISTINCT {c} FROM {t} WHERE {text} ORDER BY 1").fetchall()
        return [r[0] for r in rows]
    if policy is None or not policy.is_tenant_scoped(table.name) or tenants == 0:
        return None
    (distinct,) = conn.execute(f"SELECT COUNT(DISTINCT {c}) FROM {t} WHERE {text}").fetchone()
    if distinct > VOCABULARY_MAX_DISTINCT:
        return None
    rows = conn.execute(
        f"SELECT {c} FROM {t} WHERE {text} GROUP BY {c} "
        f"HAVING COUNT(DISTINCT {_ident(policy.tenant_column)}) = ? ORDER BY 1",
        (tenants,),
    ).fetchall()
    return [r[0] for r in rows]
