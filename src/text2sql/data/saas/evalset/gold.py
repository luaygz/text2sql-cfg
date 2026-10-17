"""Mechanical checks on gold SQL: sentinel substitution, the explicit-scope proof, execution.

The authoring model never sees parameter syntax (the grammar has none). It writes the asking
tenant as `TENANT_SENTINEL` and the signed-in user as `USER_SENTINEL`; `substitute_sentinels`
turns them into `:tenant_id` / `:user_id`. `prove_explicit_scope` then checks with sqlglot that
every reference to a tenant table is filtered on its own tenant column in the same SELECT, so the
gold is right for any tenant without help from the scoping layer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Self

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.execution import (
    AccessPolicy,
    ExecutionError,
    ExecutionLimits,
    QueryResult,
    SandboxedExecutor,
)
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar
from text2sql.safety import TENANT_PARAM, USER_PARAM
from text2sql.safety.policy import ScopePolicy

TENANT_SENTINEL: Final = 987654321
USER_SENTINEL: Final = 987654322
MAX_GOLD_ROWS: Final = 100
"""Gold results stay below the LIMIT a tenant-mode answer may use, so set comparison is fair."""
GOLD_TIMEOUT_S: Final = 10.0
_WALL_CLOCK = (exp.CurrentDate, exp.CurrentTime, exp.CurrentTimestamp)


class GoldRejected(Exception):  # noqa: N818 - a verdict, not an error in this code
    """A gold candidate failed a mechanical check; `reason` is a stable label for the report."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def authoring_schema(full: DatabaseSchema, policy: ScopePolicy) -> DatabaseSchema:
    """The full schema with tenant and owner columns, minus secrets no gold may read."""
    return full.without_columns(policy.hidden_columns)


def authoring_grammar(schema: DatabaseSchema) -> SqlGrammar:
    return build_grammar(
        schema, GrammarOptions(mode=QueryMode.BENCHMARK, max_rows=1000, allow_abstain=True)
    )


def readable_columns(schema: DatabaseSchema) -> dict[str, frozenset[str]]:
    return {t.name.lower(): frozenset(c.lower() for c in t.column_names) for t in schema.tables}


def substitute_sentinels(sql: str, *, user_mode: bool) -> str:
    """Replace the sentinel ids with named parameters. A sentinel left anywhere else (inside a
    string, or the user sentinel outside user mode) means the model misused it."""
    out = _sentinel_pattern(TENANT_SENTINEL).sub(f":{TENANT_PARAM}", sql)
    if user_mode:
        out = _sentinel_pattern(USER_SENTINEL).sub(f":{USER_PARAM}", out)
    sentinels = {str(TENANT_SENTINEL), str(USER_SENTINEL)}
    markers = (*sentinels, f":{TENANT_PARAM}", f":{USER_PARAM}")
    for literal in _parse(out).find_all(exp.Literal):
        text = str(literal.this)
        misused = any(m in text for m in markers) if literal.is_string else text in sentinels
        if misused:
            raise GoldRejected("sentinel_misuse", f"sentinel id in the literal {literal.sql()}")
    return out


def prove_explicit_scope(sql: str, policy: ScopePolicy, *, user_mode: bool) -> None:
    """Every tenant-table reference has `<ref>.tenant_id = :tenant_id` among the top-level
    conjuncts of its own SELECT's WHERE or JOIN conditions (and, in user mode, every owner-table
    reference `<ref>.owner_user_id = :user_id`). Raises GoldRejected otherwise."""
    tree = _parse(sql)
    if tree.find(*_WALL_CLOCK) is not None:
        raise GoldRejected("wall_clock", "gold must not depend on the current date")
    allowed = {TENANT_PARAM, USER_PARAM} if user_mode else {TENANT_PARAM}
    for placeholder in tree.find_all(exp.Placeholder):
        if placeholder.name not in allowed:
            raise GoldRejected("stray_parameter", f"unexpected parameter {placeholder.sql()}")
    _no_literal_scope(tree, policy)
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name not in policy.tenant_tables:
            continue
        select = table.find_ancestor(exp.Select)
        if select is None:
            raise GoldRejected("unscoped_table", f"{table.sql()} is outside any SELECT")
        guards = [(policy.tenant_column, TENANT_PARAM)]
        if user_mode and name in policy.owner_tables:
            guards.append((policy.owner_column, USER_PARAM))
        conjuncts = _conjuncts(select)
        ref = table.alias_or_name.lower()
        alone = _source_count(select) == 1
        for column, param in guards:
            if not any(_is_guard(c, ref, column, param, alone=alone) for c in conjuncts):
                raise GoldRejected(
                    "unscoped_table", f"{table.sql()} has no `{ref}.{column} = :{param}` filter"
                )


def row_set(result: QueryResult) -> frozenset[tuple[object, ...]]:
    """Order-insensitive identity of a result, as BIRD's execution accuracy compares it."""
    return frozenset(result.rows)


def check_answer_result(result: QueryResult) -> None:
    """A usable gold answer: at least one row with a non-NULL value, and not truncated."""
    if result.truncated:
        raise GoldRejected("too_many_rows", f"more than {MAX_GOLD_ROWS} rows")
    if not result.rows:
        raise GoldRejected("empty_result", "the query returns no rows")
    if all(cell is None for row in result.rows for cell in row):
        raise GoldRejected("null_result", "every value in the result is NULL")


class GoldExecutor:
    """Read-only execution of gold SQL with bound parameters, through the sandbox."""

    def __init__(self, db_path: Path, schema: DatabaseSchema) -> None:
        self._executor = SandboxedExecutor(
            db_path,
            limits=ExecutionLimits(timeout_s=GOLD_TIMEOUT_S, max_rows=MAX_GOLD_ROWS),
            access=AccessPolicy(readable=readable_columns(schema)),
        )

    async def run(self, sql: str, params: Mapping[str, int]) -> QueryResult:
        try:
            return await self._executor.execute_async(sql, params)
        except ExecutionError as exc:
            raise GoldRejected("execution_error", str(exc)) from exc

    def close(self) -> None:
        self._executor.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _sentinel_pattern(value: int) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w.]){value}(?![\w.])")


def _parse(sql: str) -> exp.Expr:
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except SqlglotError as exc:
        raise GoldRejected("unparseable", str(exc)) from exc
    if len(statements) != 1 or statements[0] is None:
        raise GoldRejected("unparseable", "expected exactly one statement")
    return statements[0]


def _conjuncts(select: exp.Select) -> list[exp.Expr]:
    conditions: list[exp.Expr] = []
    where = select.args.get("where")
    if where is not None:
        conditions.append(where.this)
    for join in select.args.get("joins") or []:
        on = join.args.get("on")
        if on is not None:
            conditions.append(on)
    out: list[exp.Expr] = []
    for condition in conditions:
        out.extend(_flatten_and(condition))
    return out


def _flatten_and(node: exp.Expr) -> list[exp.Expr]:
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.And):
        return _flatten_and(node.left) + _flatten_and(node.right)
    return [node]


def _source_count(select: exp.Select) -> int:
    has_from = select.args.get("from_") is not None
    return int(has_from) + len(select.args.get("joins") or [])


def _is_guard(node: exp.Expr, ref: str, column: str, param: str, *, alone: bool) -> bool:
    if not isinstance(node, exp.EQ):
        return False
    for side, other in ((node.left, node.right), (node.right, node.left)):
        if (
            isinstance(side, exp.Column)
            and side.name.lower() == column
            and (side.table.lower() == ref or (not side.table and alone))
            and isinstance(other, exp.Placeholder)
            and other.name == param
        ):
            return True
    return False


def _no_literal_scope(tree: exp.Expr, policy: ScopePolicy) -> None:
    """The tenant column is only ever compared with `:tenant_id` or another tenant column."""
    for column in tree.find_all(exp.Column):
        if column.name.lower() != policy.tenant_column:
            continue
        parent = column.parent
        if not isinstance(parent, exp.EQ):
            raise GoldRejected("tenant_misuse", f"{parent.sql() if parent else column.sql()}")
        other = parent.right if parent.left is column else parent.left
        fine = isinstance(other, exp.Placeholder) and other.name == TENANT_PARAM
        fine = fine or (
            isinstance(other, exp.Column) and other.name.lower() == policy.tenant_column
        )
        if not fine:
            raise GoldRejected("tenant_misuse", parent.sql())
