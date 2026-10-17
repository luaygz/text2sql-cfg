"""Layer 4: tenant and user scoping (docs/adr/002-tenant-scoping.md).

`apply_scope` replaces every reference to a tenant-scoped table with a guarded derived table:

    deals AS T1   ->   (SELECT "id", "title", ... FROM deals
                        WHERE deals."tenant_id" = :tenant_id) AS T1

Because the guard stands in for the table itself, the filter applies wherever the table appears
(joins on either side of a LEFT JOIN, subqueries, CTEs, set operations, self-joins) and cannot
change join semantics: the query behaves as if the database held only the caller's rows. Guards
project only visible columns, so the tenant column and hidden columns are unreachable outside the
guard, and the executor's column-level authorizer never sees a read of a hidden column.

The guard is spliced into the original text at the table name's source span; the rest of the
query is byte-for-byte what the validator accepted. Identity values travel only as bound
parameters taken from `ScopeContext`, never from the model or the SQL text.

`verify_scope` does not trust `apply_scope`: it re-parses the result and proves that every scoped
table reference is the sole source of a guard that filters on exactly the expected parameters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from sqlglot import exp

from text2sql.catalog.schema import DatabaseSchema
from text2sql.safety.errors import ScopeViolation
from text2sql.safety.parsing import SqlSyntaxError, fold, parse_sql
from text2sql.safety.policy import ScopeContext, ScopePolicy

TENANT_PARAM: Final = "tenant_id"
USER_PARAM: Final = "user_id"


class ScopeRule(StrEnum):
    """Stable rejection ids of the scoping layer."""

    UNPARSEABLE = "unparseable"
    UNKNOWN_TABLE = "unknown_table"
    """A scoped table is missing from the schema, so its guard's columns are unknown."""
    SHADOWED_TABLE = "shadowed_table"
    UNGUARDED_TABLE = "unguarded_table"
    STRAY_PARAMETER = "stray_parameter"


@dataclass(frozen=True, slots=True)
class ScopedQuery:
    sql: str
    """Uses the named parameters `:tenant_id` and, in user mode, `:user_id`."""
    params: dict[str, int]
    """Exactly the parameters `sql` uses, bound server-side from `ScopeContext`."""


def apply_scope(
    sql: str, policy: ScopePolicy, ctx: ScopeContext, *, schema: DatabaseSchema
) -> ScopedQuery:
    """Guard every scoped table in `sql`, then prove the result with `verify_scope`.

    `schema` is the full database schema (not the model's visible one): guards project every
    column the policy does not hide. Owner-scoped tables are filtered by user as well when
    `ctx.user_id` is set.
    """
    tree = _parse_query(sql)
    user_mode = ctx.user_id is not None
    tables = {fold(t.name): t for t in schema.tables}
    edits: list[tuple[int, int, str]] = []
    params: dict[str, int] = {}
    for table in tree.find_all(exp.Table):
        if not policy.is_tenant_scoped(table.name) or not _splicable(table):
            continue  # anything left unguarded is rejected by verify_scope below
        known = tables.get(fold(table.name))
        if known is None:
            raise ScopeViolation(ScopeRule.UNKNOWN_TABLE, f"{table.name} is not in the schema")
        hidden = policy.hidden_for(known.name)
        columns = [_quote(c.name) for c in known.columns if fold(c.name) not in hidden]
        owner_id = ctx.user_id if policy.is_owner_scoped(known.name) else None
        guard = _guard(_quote(known.name), columns, policy, owner=owner_id is not None)
        # Replace only the table name; an alias the model wrote keeps naming the guard.
        start, end = table.this.meta["start"], table.this.meta["end"] + 1
        edits.append((start, end, guard if table.alias else f"{guard} AS {_quote(table.name)}"))
        params[TENANT_PARAM] = ctx.tenant_id
        if owner_id is not None:
            params[USER_PARAM] = owner_id
    for start, end, text in sorted(edits, reverse=True):
        sql = sql[:start] + text + sql[end:]
    verify_scope(sql, policy, user_mode=user_mode)
    return ScopedQuery(sql=sql, params=params)


def verify_scope(sql: str, policy: ScopePolicy, *, user_mode: bool) -> None:
    """Prove that every read of a scoped table goes through a guard; raise `ScopeViolation`.

    A guard is a SELECT whose only source is the bare table, whose projection is plain visible
    columns, and whose WHERE is exactly `<table>.<tenant_column> = :tenant_id`, plus
    `<table>.<owner_column> = :user_id` for owner tables in user mode. Bind parameters anywhere
    else, CTEs named like scoped tables and `expr IN table` are rejected.
    """
    tree = _parse_query(sql)
    for cte in tree.find_all(exp.CTE):
        if policy.is_tenant_scoped(cte.alias):
            raise ScopeViolation(ScopeRule.SHADOWED_TABLE, f"CTE {cte.alias} shadows a table")
    guard_params: set[int] = set()
    for table in tree.find_all(exp.Table):
        if policy.is_tenant_scoped(table.name):
            guard_params.update(_prove_guard(table, policy, user_mode=user_mode))
    for node in tree.walk():
        if isinstance(node, (exp.Placeholder, exp.Parameter)) and id(node) not in guard_params:
            raise ScopeViolation(ScopeRule.STRAY_PARAMETER, f"{node.sql()} is outside a guard")
        if isinstance(node, exp.Identifier) and not node.quoted and node.name.startswith("$"):
            raise ScopeViolation(ScopeRule.STRAY_PARAMETER, f"{node.name} is outside a guard")
        if isinstance(node, exp.In) and node.args.get("field") is not None:
            raise ScopeViolation(ScopeRule.UNGUARDED_TABLE, f"{node.sql()} reads a bare table")


def _parse_query(sql: str) -> exp.Expression:
    try:
        statements = parse_sql(sql).statements
    except SqlSyntaxError as exc:
        raise ScopeViolation(ScopeRule.UNPARSEABLE, str(exc)) from exc
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
        raise ScopeViolation(ScopeRule.UNPARSEABLE, "expected exactly one SELECT statement")
    return statements[0]


def _splicable(table: exp.Table) -> bool:
    """A plain `name [AS alias]` FROM/JOIN source whose name has a known source span."""
    return (
        isinstance(table.parent, (exp.From, exp.Join))
        and table.arg_key == "this"
        and _present_args(table) <= {"this", "alias"}
        and isinstance(table.this, exp.Identifier)
        and "start" in table.this.meta
    )


def _guard(name: str, columns: Sequence[str], policy: ScopePolicy, *, owner: bool) -> str:
    conditions = [f"{name}.{_quote(policy.tenant_column)} = :{TENANT_PARAM}"]
    if owner:
        conditions.append(f"{name}.{_quote(policy.owner_column)} = :{USER_PARAM}")
    return f"(SELECT {', '.join(columns)} FROM {name} WHERE {' AND '.join(conditions)})"


def _prove_guard(table: exp.Table, policy: ScopePolicy, *, user_mode: bool) -> set[int]:
    """Check one scoped table reference; return the ids of its guard's parameter nodes."""
    select = table.parent.parent if isinstance(table.parent, exp.From) else None
    if not (
        isinstance(select, exp.Select)
        and table.arg_key == "this"
        and select.args.get("from_") is table.parent
        and _present_args(table) == {"this"}
        and _present_args(select) == {"expressions", "from_", "where"}
    ):
        raise ScopeViolation(ScopeRule.UNGUARDED_TABLE, f"{table.sql()} is read without a guard")
    hidden = policy.hidden_for(table.name)
    for item in select.expressions:
        if not (isinstance(item, exp.Column) and not item.table and fold(item.name) not in hidden):
            raise ScopeViolation(
                ScopeRule.UNGUARDED_TABLE, f"guard of {table.name} projects {item.sql()}"
            )
    expected = {fold(policy.tenant_column): TENANT_PARAM}
    if user_mode and policy.is_owner_scoped(table.name):
        expected[fold(policy.owner_column)] = USER_PARAM
    condition = select.args["where"].this
    conjuncts = (
        list(condition.flatten(unnest=False)) if isinstance(condition, exp.And) else [condition]
    )
    found: dict[str, str] = {}
    for conjunct in conjuncts:
        if not (
            isinstance(conjunct, exp.EQ)
            and isinstance(conjunct.this, exp.Column)
            and fold(conjunct.this.table) in {"", fold(table.name)}
            and not conjunct.this.args.get("db")
            and isinstance(conjunct.expression, exp.Placeholder)
        ):
            raise ScopeViolation(
                ScopeRule.UNGUARDED_TABLE, f"guard of {table.name} has condition {conjunct.sql()}"
            )
        found[fold(conjunct.this.name)] = conjunct.expression.name
    if len(conjuncts) != len(expected) or found != expected:
        raise ScopeViolation(
            ScopeRule.UNGUARDED_TABLE,
            f"guard of {table.name} must filter exactly on {expected}, found {found}",
        )
    return {id(conjunct.expression) for conjunct in conjuncts}


def _present_args(node: exp.Expr) -> set[str]:
    return {key for key, value in node.args.items() if value is not None and value != []}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
