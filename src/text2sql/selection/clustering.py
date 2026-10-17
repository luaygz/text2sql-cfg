"""Execution-result clustering, the first step of selection (ADR-008 stage 8, ADR-013).

Two candidates share a cluster exactly when BIRD's EX metric cannot tell them apart.
`bird_metric.results_match` compares results as sets of row tuples under Python equality, so an
unordered fingerprint is the set of rows (row order and duplicate rows dropped), with values
encoded so that equal values encode equally: `1` and `1.0` match, `0.1 + 0.2` and `0.3` do not
(EX has no float tolerance), NULL matches only NULL, and text never matches a number. The
exception is a query with a top-level ORDER BY: its row sequence is part of the answer, so its
fingerprint keeps order and duplicates, unless the result has at most one distinct row, where
order cannot matter. Column names never count, as in EX.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from text2sql.execution import QueryResult


@dataclass(frozen=True)
class ExecutedCandidate:
    """A candidate whose SQL ran without error. `index` is the pipeline's candidate number and
    is what clusters and selections refer to; `ordered` says the SQL has a top-level ORDER BY."""

    index: int
    strategy: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    ordered: bool
    truncated: bool

    @classmethod
    def from_result(
        cls, *, index: int, strategy: str, sql: str, result: QueryResult
    ) -> ExecutedCandidate:
        """Build from the executor's result. Pass the model's SQL, not a tenant-scoped rewrite:
        `ordered` is read from it."""
        return cls(
            index=index,
            strategy=strategy,
            sql=sql,
            columns=result.columns,
            rows=result.rows,
            ordered=has_top_level_order_by(sql),
            truncated=result.truncated,
        )


@dataclass(frozen=True)
class Cluster:
    """Candidates with the same result fingerprint. `members` are candidate indexes in
    ascending order; `representative` is the member with the shortest SQL."""

    fingerprint: str
    members: tuple[int, ...]
    representative: int


def has_top_level_order_by(sql: str) -> bool:
    """Whether the outermost query (a SELECT or a compound query) has an ORDER BY.

    ORDER BY inside a CTE, subquery, window or aggregate does not count. SQL that sqlglot cannot
    parse counts as unordered, the comparison EX itself uses.
    """
    try:
        tree = sqlglot.parse_one(sql, dialect="sqlite")
    except SqlglotError:
        return False
    while isinstance(tree, exp.Subquery):
        tree = tree.this
    return tree.args.get("order") is not None


def sql_length(sql: str) -> int:
    """Length of `sql` with runs of whitespace collapsed, so layout does not count."""
    return len(" ".join(sql.split()))


def result_fingerprint(
    rows: Sequence[Sequence[object]], *, ordered: bool, truncated: bool = False
) -> str:
    """Hex digest that is equal for two results iff EX would score them as the same answer.

    `ordered` keeps row order and duplicates (see the module docstring). A `truncated` result
    holds only the first rows of a longer one, so it never matches a complete result.
    """
    encoded = [_encode_row(row) for row in rows]
    keep_order = ordered and len(set(encoded)) > 1
    body = encoded if keep_order else sorted(set(encoded))
    header = ("seq" if keep_order else "set") + (" truncated" if truncated else "")
    digest = hashlib.sha256(header.encode())
    for line in body:
        digest.update(b"\n" + line.encode())
    return digest.hexdigest()


def cluster_candidates(cands: Sequence[ExecutedCandidate]) -> list[Cluster]:
    """Group candidates by result fingerprint, largest cluster first.

    Equal-size clusters keep the order of their lowest candidate index. The representative is
    the member with the shortest SQL (`sql_length`), the lowest index on a tie.
    """
    seen: set[int] = set()
    groups: dict[str, list[ExecutedCandidate]] = {}
    for cand in cands:
        if cand.index in seen:
            raise ValueError(f"duplicate candidate index {cand.index}")
        seen.add(cand.index)
        key = result_fingerprint(cand.rows, ordered=cand.ordered, truncated=cand.truncated)
        groups.setdefault(key, []).append(cand)
    clusters = [
        Cluster(
            fingerprint=key,
            members=tuple(sorted(c.index for c in group)),
            representative=min(group, key=lambda c: (sql_length(c.sql), c.index)).index,
        )
        for key, group in groups.items()
    ]
    clusters.sort(key=lambda c: (-len(c.members), c.members[0]))
    return clusters


def _encode_value(value: object) -> str:
    # Integral floats encode as ints because Python (and so EX) treats 1 == 1.0; int(f) is exact.
    if value is None:
        return "n"
    if isinstance(value, bool | int):
        return f"i{int(value)}"
    if isinstance(value, float):
        return f"i{int(value)}" if value.is_integer() else f"f{value!r}"
    if isinstance(value, str):
        return "s" + value
    if isinstance(value, bytes):
        return "b" + value.hex()
    return f"o{type(value).__name__}:{value!r}"


def _encode_row(row: Sequence[object]) -> str:
    # JSON quoting keeps rows unambiguous whatever characters the values contain.
    return json.dumps([_encode_value(v) for v in row], ensure_ascii=False)
