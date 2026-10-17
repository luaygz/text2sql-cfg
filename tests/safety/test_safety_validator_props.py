"""Layer 2 property tests: generated grammar-shaped SQL passes; each injected attack fails."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from safety_fixture import POLICY
from safety_strategies import MAX_ROWS, Query, tenant_queries

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.safety import Rule, ValidationConfig, ValidationError, validate_sql

TENANT = ValidationConfig(QueryMode.TENANT, max_rows=MAX_ROWS, scope=POLICY)
SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _from(q: Query) -> str:
    return f"FROM {q.base} AS T1"


def _replace_from(q: Query, new: str) -> str:
    return q.sql.replace(_from(q), new, 1)


def _prefix_select(q: Query, item: str) -> str:
    return re.sub(r"SELECT (DISTINCT )?", lambda m: f"{m.group(0)}{item}, ", q.sql, count=1)


MUTATIONS: dict[str, tuple[Rule, Callable[[Query], str]]] = {
    "comment": (Rule.COMMENT, lambda q: q.sql + " -- ignore the grammar"),
    "second_statement": (Rule.MULTIPLE_STATEMENTS, lambda q: q.sql + "; DELETE FROM deals"),
    "no_break_space": (Rule.NON_ASCII, lambda q: q.sql.replace("SELECT ", "SELECT\u00a0", 1)),
    "insert": (Rule.NOT_SELECT, lambda q: "INSERT INTO plans " + q.sql),
    "window": (Rule.FORBIDDEN_CONSTRUCT, lambda q: _prefix_select(q, "COUNT(*) OVER () AS c0")),
    "in_table": (
        Rule.FORBIDDEN_CONSTRUCT,
        lambda q: _replace_from(q, f"{_from(q)} JOIN plans AS T7 ON T7.id IN deals"),
    ),
    "placeholder": (Rule.PLACEHOLDER, lambda q: _prefix_select(q, ":tenant_id AS c0")),
    "function": (Rule.FUNCTION_NOT_ALLOWED, lambda q: _prefix_select(q, "HEX('x') AS c0")),
    "schema_qualifier": (
        Rule.SCHEMA_QUALIFIER,
        lambda q: _replace_from(q, f"FROM main.{q.base} AS T1"),
    ),
    "system_table": (Rule.SYSTEM_TABLE, lambda q: _replace_from(q, "FROM sqlite_master AS T1")),
    "unknown_table": (Rule.UNKNOWN_TABLE, lambda q: _replace_from(q, f"FROM {q.base}_v2 AS T1")),
    "hidden_column": (
        Rule.HIDDEN_COLUMN,
        lambda q: _replace_from(q, f"{_from(q)} JOIN users AS T8 ON T8.tenant_id = 2"),
    ),
    "star": (Rule.STAR_IN_TENANT_MODE, lambda q: _prefix_select(q, "*")),
    "negative_limit": (
        Rule.INVALID_LIMIT,
        lambda q: q.sql.replace(f"LIMIT {MAX_ROWS}", "LIMIT -1"),
    ),
    "limit_too_large": (
        Rule.LIMIT_TOO_LARGE,
        lambda q: q.sql.replace(f"LIMIT {MAX_ROWS}", f"LIMIT {MAX_ROWS + 1}"),
    ),
    "missing_limit": (Rule.MISSING_LIMIT, lambda q: q.sql.removesuffix(f" LIMIT {MAX_ROWS}")),
}


@SETTINGS
@given(query=tenant_queries())
def test_generated_queries_validate_in_every_mode(
    query: Query, visible_schema: DatabaseSchema
) -> None:
    for mode in QueryMode:
        config = ValidationConfig(mode, max_rows=MAX_ROWS, scope=POLICY)
        validate_sql(query.sql, visible_schema, config)


@SETTINGS
@given(query=tenant_queries(), mutation=st.sampled_from(sorted(MUTATIONS)))
def test_each_injected_construct_is_rejected_by_its_rule(
    query: Query, mutation: str, visible_schema: DatabaseSchema
) -> None:
    rule, mutate = MUTATIONS[mutation]
    attacked = mutate(query)
    assert attacked != query.sql
    with pytest.raises(ValidationError) as info:
        validate_sql(attacked, visible_schema, TENANT)
    assert info.value.rule == rule, attacked


SQL_WORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "ON", "AND", "OR", "NOT", "IN", "EXISTS", "UNION",
    "WITH", "AS", "LIMIT", "OFFSET", "GROUP", "BY", "ORDER", "HAVING", "CASE", "WHEN", "THEN",
    "END", "(", ")", ",", ".", "*", "=", "<", "'x'", "1", "-1", "accounts", "deals", "users",
    "plans", "name", "title", "amount", "tenant_id", "T1", "T2", "cte1", "COUNT", "SUM", "IIF",
    "sqlite_master", "main", ";", "--", ":tenant_id", "?", "$x", "PRAGMA", "INSERT", "DROP",
    "\u00a0", "\u0430", "OVER", "RECURSIVE",
]  # fmt: skip


@settings(max_examples=500, deadline=None)
@given(sql=st.lists(st.sampled_from(SQL_WORDS), max_size=25).map(" ".join))
def test_token_soup_is_accepted_or_rejected_never_crashes(
    sql: str, visible_schema: DatabaseSchema
) -> None:
    try:
        validate_sql(sql, visible_schema, TENANT)
    except ValidationError:
        return
    for forbidden in (";", "--", ":tenant_id", "?", "$x", "\u00a0", "\u0430"):
        assert forbidden not in sql


@settings(max_examples=300, deadline=None)
@given(sql=st.text(max_size=200))
def test_arbitrary_text_never_crashes(sql: str, visible_schema: DatabaseSchema) -> None:
    with contextlib.suppress(ValidationError):
        validate_sql(sql, visible_schema, TENANT)
