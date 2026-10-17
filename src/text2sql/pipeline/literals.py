"""The literal check: strings a query compares a column with that the column does not hold.

The model writes a value as the evidence spells it ('legal', 'strength') when the database stores
another spelling ('Legal', 'Strength'); the query runs and returns nothing or a wrong count. In
the round-0 review that was 8 of 109 failures. OpenSearch-SQL aligns values with the database
after generation; here the check runs after a candidate executed and reports each mismatch to one
repair turn (ADR-014), which decides whether the stored value is the one the question means.

Only a bare column compared with string literals is checked: `=`, `!=`/`<>`, `IN (...)` and
`LIKE` without wildcards, wherever the comparison sits (WHERE, ON, CASE WHEN). The column is
resolved to its base table through aliases, derived tables and CTEs. Columns without TEXT
affinity (INTEGER, REAL, DATE, DATETIME in BIRD) are skipped. A literal counts as missing only
when no row matches it under the query's own operator, and it is reported only when the column
holds something close: the same text up to ASCII case and surrounding spaces, or values the value
retrieval stage found for the question's words in that column.

The lookups are built here from schema names, take the literal as a bound parameter, and run on
a read-only connection of their own under a budget of SQLite steps (`text2sql.sqlite_budget`, so
the outcome does not depend on machine load); model text never reaches them as SQL.
They can read any visible column, so tenant mode, where rows belong to tenants, never runs them.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import sqlglot
import structlog
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.schema import MappingSchema

from text2sql.catalog.schema import Column, DatabaseSchema, Table, quote_identifier
from text2sql.retrieval import ValueMatches
from text2sql.sqlite_budget import step_budget, steps_for

log = structlog.get_logger(__name__)

MAX_LITERALS = 10
"""Comparisons checked per query, in query order."""
MAX_STORED = 3
"""Stored values named per mismatch."""
LOOKUP_BUDGET_S = 2.0
"""SQLite work, in reference-machine seconds, for every lookup of one query; the comparisons left
when it runs out are skipped."""
LIKE_WILDCARDS = frozenset("%_")

Similarity = Literal["case", "retrieved"]


@dataclass(frozen=True, slots=True)
class ComparedLiteral:
    """A string literal compared with a base-table column (names in schema spelling)."""

    table: str
    column: str
    literal: str
    like: bool
    """Compared with `LIKE` (no wildcards: ASCII-case-insensitive equality), else `=`, `!=` or
    `IN`."""


@dataclass(frozen=True, slots=True)
class ValueMismatch:
    compared: ComparedLiteral
    stored: tuple[str, ...]
    """Up to MAX_STORED values of the column close to the literal."""
    similarity: Similarity
    """`case`: the literal's text up to case and surrounding spaces; `retrieved`: values that
    value retrieval matched to words of the question or evidence."""

    def describe(self) -> str:
        """One observation line, e.g. "cards.status has no value 'legal'. Stored values that
        differ from it only in case or surrounding spaces: 'Legal'." """
        c = self.compared
        column = f"{quote_identifier(c.table)}.{quote_identifier(c.column)}"
        if self.similarity == "case":
            kind = "differ from it only in case or surrounding spaces"
        else:
            kind = "match words in the question or evidence"
        values = ", ".join(sql_string(v) for v in self.stored)
        literal = sql_string(c.literal)
        return f"{column} has no value {literal}. Stored values that {kind}: {values}."


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def mismatch_detail(mismatches: Sequence[ValueMismatch]) -> str:
    """The `detail` of a `value` repair: one observation per line."""
    return "\n".join(f"- {m.describe()}" for m in mismatches)


async def literal_mismatches(
    sql: str, schema: DatabaseSchema, db_path: Path, matches: ValueMatches
) -> list[ValueMismatch]:
    """`compared_literals` of `sql`, then `find_mismatches` on the database, off the event loop."""
    return await asyncio.to_thread(_mismatches, sql, schema, db_path, matches)


def _mismatches(
    sql: str, schema: DatabaseSchema, db_path: Path, matches: ValueMatches
) -> list[ValueMismatch]:
    compared = compared_literals(sql, schema)
    return find_mismatches(db_path, compared, matches) if compared else []


def compared_literals(sql: str, schema: DatabaseSchema) -> list[ComparedLiteral]:
    """The first MAX_LITERALS distinct string comparisons of `sql` with TEXT columns of `schema`.

    SQL that sqlglot cannot parse or qualify yields none: the check is skipped, not failed.
    """
    mapping = MappingSchema(
        {t.name: dict.fromkeys(t.column_names, "TEXT") for t in schema.tables}, dialect="sqlite"
    )
    try:
        tree = qualify(
            sqlglot.parse_one(sql, dialect="sqlite"),
            schema=mapping,
            dialect="sqlite",
            validate_qualify_columns=False,
            quote_identifiers=False,
            identify=False,
        )
        scopes = traverse_scope(tree)
    except SqlglotError as exc:
        log.info("pipeline.literal_check.unresolved", error=str(exc)[:200])
        return []
    found: dict[ComparedLiteral, None] = {}
    for scope in scopes:
        for column in scope.columns:
            strings = _compared_strings(column)
            target = _resolve(scope, column.table, column.name, schema) if strings else None
            if target is None or not _text_affinity(target[1].type):
                continue
            table, col = target
            for text, like in strings:
                found.setdefault(ComparedLiteral(table.name, col.name, text, like))
    return list(found)[:MAX_LITERALS]


def find_mismatches(
    db_path: Path,
    compared: Sequence[ComparedLiteral],
    matches: ValueMatches,
    *,
    budget_s: float = LOOKUP_BUDGET_S,
) -> list[ValueMismatch]:
    """A mismatch for each compared literal that no row matches while its column holds close
    values.

    A lookup that fails or runs past `budget_s` is skipped: a missed check costs nothing, while
    a wrong trigger costs a repair call.
    """
    found: list[ValueMismatch] = []
    steps = steps_for(budget_s) if budget_s > 0 else 0
    with closing(_connect(db_path)) as conn, step_budget(conn, steps) as budget:
        for checked, item in enumerate(compared):
            if budget.used >= budget.steps:
                log.info("pipeline.literal_check.out_of_time", skipped=len(compared) - checked)
                break
            try:
                mismatch = _lookup(conn, item, matches)
            except sqlite3.Error as exc:
                log.info(
                    "pipeline.literal_check.lookup_failed",
                    table=item.table,
                    column=item.column,
                    error=str(exc),
                )
                continue
            if mismatch is not None:
                found.append(mismatch)
    return found


def _lookup(
    conn: sqlite3.Connection, item: ComparedLiteral, matches: ValueMatches
) -> ValueMismatch | None:
    table, column = _ident(item.table), _ident(item.column)
    operator = "LIKE" if item.like else "="
    exists = f"SELECT 1 FROM {table} WHERE {column} {operator} ? LIMIT 1"
    if conn.execute(exists, (item.literal,)).fetchone() is not None:
        return None
    variants = (
        f"SELECT DISTINCT {column} FROM {table} "
        f"WHERE lower(trim({column})) = lower(trim(?)) LIMIT {MAX_STORED}"
    )
    case = tuple(str(row[0]) for row in conn.execute(variants, (item.literal,)))
    if case:
        return ValueMismatch(item, case, "case")
    retrieved = _retrieved(matches, item)
    return ValueMismatch(item, retrieved, "retrieved") if retrieved else None


def _retrieved(matches: ValueMatches, item: ComparedLiteral) -> tuple[str, ...]:
    key = (item.table.lower(), item.column.lower())
    for (table, column), values in matches.items():
        if (table.lower(), column.lower()) == key:
            return tuple(values[:MAX_STORED])
    return ()


def _compared_strings(column: exp.Column) -> list[tuple[str, bool]]:
    """(literal, is LIKE) for each string `column` is compared with by its parent node."""
    parent = column.parent
    if isinstance(parent, exp.EQ | exp.NEQ):
        other = parent.expression if parent.this is column else parent.this
        return [(other.this, False)] if _is_string(other) else []
    if isinstance(parent, exp.In) and parent.this is column:
        return [(e.this, False) for e in parent.expressions if _is_string(e)]
    if isinstance(parent, exp.Like) and parent.this is column:
        pattern = parent.expression
        # Under ESCAPE a `%` or `_` can be a plain character; such patterns are left alone.
        if isinstance(parent.parent, exp.Escape) or not _is_string(pattern):
            return []
        return [] if LIKE_WILDCARDS & set(pattern.this) else [(pattern.this, True)]
    return []


def _is_string(node: exp.Expression | None) -> bool:
    return isinstance(node, exp.Literal) and node.is_string


def _resolve(
    scope: Scope | None, alias: str, name: str, schema: DatabaseSchema
) -> tuple[Table, Column] | None:
    """The base column `alias.name` reads: through outer scopes (correlated subqueries) and
    through derived tables and CTEs whose output is a bare column. None for anything computed."""
    while scope is not None:
        source = scope.sources.get(alias)
        if isinstance(source, exp.Table):
            table = schema.table(source.name)
            column = table.column(name) if table else None
            return (table, column) if table and column else None
        if isinstance(source, Scope):
            return _derived_output(source, name, schema)
        scope = scope.parent
    return None


def _derived_output(scope: Scope, name: str, schema: DatabaseSchema) -> tuple[Table, Column] | None:
    select = scope.expression
    if not isinstance(select, exp.Select):
        return None  # a UNION's output column comes from several queries
    for projection in select.selects:
        if projection.alias_or_name == name:
            inner = projection.unalias()
            if isinstance(inner, exp.Column):
                return _resolve(scope, inner.table, inner.name, schema)
            return None
    return None


def _text_affinity(declared: str) -> bool:
    """SQLite's affinity rules 1 and 2: INT anywhere wins, then CHAR, CLOB or TEXT."""
    upper = declared.upper()
    return "INT" not in upper and any(word in upper for word in ("CHAR", "CLOB", "TEXT"))


def _connect(db_path: Path) -> sqlite3.Connection:
    # No statement cache, so the step budget does not depend on earlier lookups.
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True, cached_statements=0)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
