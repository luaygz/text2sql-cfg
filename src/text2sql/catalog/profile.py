"""Column statistics for the catalog, from one read-only scan per table.

Every column's null count, distinct count and most frequent values are tallied in a single
pass with `collections.Counter`. One pass matters on BIRD: in wide tables such as
`european_football_2.Match`, the numeric columns sit behind long XML text columns in each record,
so every per-column SQL query (`GROUP BY`, `COUNT(DISTINCT)`) re-reads those overflow pages; a
query per column took about 9 s on that table against about 1 s for one scan.

Tables larger than `ProfileOptions.max_rows` are scanned on a systematic rowid sample
(`rowid % step = 0`), which bounds time and memory by the sample size. Sampled distinct counts
are lower bounds and sampled null rates are estimates; `TableProfile.profiled_rows` says how
many rows the numbers came from.
"""

from __future__ import annotations

import heapq
import math
import sqlite3
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from text2sql.catalog.model import SampleValue
from text2sql.catalog.schema import Table

_FETCH_ROWS = 2_000

type _Value = SampleValue | bytes | None


@dataclass(frozen=True, slots=True)
class ProfileOptions:
    max_rows: int = 100_000
    """Tables with more rows are profiled on a systematic sample of about this many rows."""
    sample_values: int = 5
    max_value_chars: int = 80
    """Longer text samples are cut and end with an ellipsis."""


DEFAULT_PROFILE_OPTIONS = ProfileOptions()


@dataclass(frozen=True, slots=True)
class ColumnStats:
    distinct_count: int
    null_rate: float | None
    """`None` for an empty table."""
    samples: tuple[SampleValue, ...]


@dataclass(frozen=True, slots=True)
class TableProfile:
    row_count: int
    profiled_rows: int
    columns: Mapping[str, ColumnStats]
    """Keyed by the exact column name from the schema."""


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    return sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    count: int = conn.execute(f"SELECT COUNT(*) FROM main.{_q(table)}").fetchone()[0]
    return count


def profile_table(
    conn: sqlite3.Connection, table: Table, options: ProfileOptions = DEFAULT_PROFILE_OPTIONS
) -> TableProfile:
    source = f"main.{_q(table.name)}"
    row_count = count_rows(conn, table.name)
    query = f"SELECT {', '.join(_q(c.name) for c in table.columns)} FROM {source}"
    if row_count > options.max_rows and _has_rowid(conn, source):
        query += f" WHERE rowid % {math.ceil(row_count / options.max_rows)} = 0"

    counters: list[Counter[_Value]] = [Counter() for _ in table.columns]
    profiled = 0
    cursor = conn.execute(query)
    while chunk := cursor.fetchmany(_FETCH_ROWS):
        profiled += len(chunk)
        for counter, values in zip(counters, zip(*chunk, strict=True), strict=True):
            counter.update(values)

    columns: dict[str, ColumnStats] = {}
    for column, counter in zip(table.columns, counters, strict=True):
        nulls = counter.pop(None, 0)
        blob = "BLOB" in column.type.upper()
        columns[column.name] = ColumnStats(
            distinct_count=len(counter),
            null_rate=None if profiled == 0 else round(nulls / profiled, 4),
            samples=() if blob else _top_values(counter, options),
        )
    return TableProfile(row_count=row_count, profiled_rows=profiled, columns=columns)


def _top_values(counter: Counter[_Value], options: ProfileOptions) -> tuple[SampleValue, ...]:
    """Most frequent non-blank, non-blob values; ties broken by value (SQLite order)."""
    candidates: list[tuple[SampleValue, int]] = []
    for value, n in counter.items():
        if isinstance(value, int | float) or (isinstance(value, str) and value.strip()):
            candidates.append((value, n))
    # Over-fetch: truncation can merge distinct long strings into the same sample.
    ranked = heapq.nsmallest(options.sample_values * 2, candidates, key=_rank)
    out: list[SampleValue] = []
    for value, _ in ranked:
        v = _truncate(value, options.max_value_chars)
        if v not in out:
            out.append(v)
        if len(out) == options.sample_values:
            break
    return tuple(out)


def _rank(item: tuple[SampleValue, int]) -> tuple[int, bool, SampleValue]:
    value, n = item
    return -n, isinstance(value, str), value


def _truncate(value: SampleValue, limit: int) -> SampleValue:
    if isinstance(value, str) and len(value) > limit:
        return value[: limit - 1] + "…"
    return value


def _has_rowid(conn: sqlite3.Connection, source: str) -> bool:
    try:
        conn.execute(f"SELECT rowid FROM {source} LIMIT 0")
    except sqlite3.OperationalError:  # WITHOUT ROWID table: scan it whole
        return False
    return True


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
