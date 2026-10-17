"""Scoping against the real synthetic SaaS database (skipped until `make data` has built it)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.config import QueryMode
from text2sql.data.saas import CANARY_COLUMNS, DEFAULT_DB_PATH, canary_values, saas_scope_policy
from text2sql.execution import AccessPolicy, Row, SandboxedExecutor
from text2sql.safety import ScopeContext, ValidationConfig, apply_scope, validate_sql

pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="data/saas/crm.sqlite not generated"
)

POLICY = saas_scope_policy()
TENANT = ValidationConfig(QueryMode.TENANT, scope=POLICY)

CROSS_TENANT_ATTEMPTS = [
    "SELECT T1.name, T2.name FROM accounts AS T1 JOIN accounts AS T2 ON T2.name = T1.name "
    "LIMIT 1000",
    "SELECT T1.name, T2.name FROM accounts AS T1 LEFT JOIN deals AS T2 "
    "ON T2.name LIKE 'CANARY%' LIMIT 1000",
    "SELECT name FROM deals WHERE account_id IN (SELECT account_id FROM accounts "
    "WHERE name LIKE 'CANARY%') LIMIT 1000",
    "SELECT full_name FROM users UNION SELECT subject FROM tickets "
    "UNION SELECT description FROM invoice_line_items LIMIT 1000",
    "WITH cte1 AS (SELECT name FROM teams UNION ALL SELECT invoice_number FROM invoices) "
    "SELECT name FROM cte1 WHERE name LIKE 'CANARY%' LIMIT 1000",
    "SELECT T1.full_name FROM users AS T1 WHERE EXISTS (SELECT 1 FROM activities AS T2 "
    "WHERE T2.owner_user_id = T1.user_id AND T2.subject LIKE 'CANARY%') LIMIT 1000",
    "SELECT T1.name, COUNT(T2.account_id) FROM plans AS T1 LEFT JOIN subscriptions AS T3 "
    "ON T3.plan_id = T1.plan_id LEFT JOIN accounts AS T2 ON T2.account_id = T3.account_id "
    "GROUP BY T1.name LIMIT 1000",
]


@pytest.fixture(scope="module")
def schema() -> DatabaseSchema:
    return introspect_sqlite(DEFAULT_DB_PATH)


@pytest.fixture(scope="module")
def executor(schema: DatabaseSchema) -> Iterator[SandboxedExecutor]:
    access = AccessPolicy(readable=POLICY.readable_columns(schema))
    with SandboxedExecutor(DEFAULT_DB_PATH, access=access) as ex:
        yield ex


def _run(
    sql: str, ctx: ScopeContext, schema: DatabaseSchema, ex: SandboxedExecutor
) -> tuple[Row, ...]:
    validate_sql(sql, POLICY.visible_schema(schema), TENANT)
    scoped = apply_scope(sql, POLICY, ctx, schema=schema)
    return ex.execute(scoped.sql, scoped.params).rows


def _foreign_canaries(rows: tuple[Row, ...], tenant: int) -> list[str]:
    cells = repr(rows)
    return [token for other, token in canary_values().items() if other != tenant and token in cells]


@pytest.mark.parametrize(("table", "column"), CANARY_COLUMNS)
def test_each_tenant_sees_its_own_canary_and_no_other(
    table: str, column: str, schema: DatabaseSchema, executor: SandboxedExecutor
) -> None:
    sql = f"SELECT {column} FROM {table} WHERE {column} LIKE 'CANARY%' LIMIT 1000"
    for tenant, token in canary_values().items():
        rows = _run(sql, ScopeContext(tenant), schema, executor)
        assert rows == ((token,),)


@pytest.mark.parametrize("sql", CROSS_TENANT_ATTEMPTS)
def test_cross_tenant_attempts_return_no_foreign_canary(
    sql: str, schema: DatabaseSchema, executor: SandboxedExecutor
) -> None:
    for tenant in canary_values():
        rows = _run(sql, ScopeContext(tenant), schema, executor)
        assert _foreign_canaries(rows, tenant) == []


def test_tenants_table_is_scoped_on_its_own_key(
    schema: DatabaseSchema, executor: SandboxedExecutor
) -> None:
    names = [_run("SELECT name FROM tenants LIMIT 10", ScopeContext(t), schema, executor)
             for t in canary_values()]  # fmt: skip
    assert all(len(rows) == 1 for rows in names)
    assert len(set(names)) == len(names)


def test_user_mode_returns_only_the_callers_rows(
    schema: DatabaseSchema, executor: SandboxedExecutor
) -> None:
    sql = "SELECT DISTINCT owner_user_id FROM deals LIMIT 1000"
    owners = _run(sql, ScopeContext(2), schema, executor)
    assert len(owners) > 1
    user = owners[0][0]
    assert isinstance(user, int)
    assert _run(sql, ScopeContext(2, user_id=user), schema, executor) == ((user,),)
