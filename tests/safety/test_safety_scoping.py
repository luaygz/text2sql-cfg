"""Layer 4: the guard rewrite, its independent proof, and cross-tenant canary checks."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from safety_fixture import POLICY, TENANTS, foreign_canaries, query, user_ids

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.execution import AccessPolicy, SandboxedExecutor
from text2sql.safety import (
    ScopeContext,
    ScopeRule,
    ScopeViolation,
    ValidationConfig,
    apply_scope,
    validate_sql,
    verify_scope,
)

TENANT = ValidationConfig(QueryMode.TENANT, scope=POLICY)
CONTEXTS = [ScopeContext(t) for t in TENANTS] + [
    ScopeContext(t, user_id=user_ids(t)[0]) for t in TENANTS
]


def scope(sql: str, schema: DatabaseSchema) -> str:
    return apply_scope(sql, POLICY, ScopeContext(1), schema=schema).sql


# -- the rewrite -------------------------------------------------------------------------------


def test_unscoped_tables_are_left_alone(full_schema: DatabaseSchema) -> None:
    sql = "SELECT name FROM plans WHERE monthly_price > 10 LIMIT 5"
    scoped = apply_scope(sql, POLICY, ScopeContext(1), schema=full_schema)
    assert (scoped.sql, scoped.params) == (sql, {})


def test_guard_replaces_only_the_table_name(full_schema: DatabaseSchema) -> None:
    scoped = apply_scope(
        "SELECT T1.name FROM accounts AS T1 WHERE T1.name = 'accounts' LIMIT 5",
        POLICY,
        ScopeContext(2),
        schema=full_schema,
    )
    assert scoped.sql == (
        'SELECT T1.name FROM (SELECT "id", "owner_user_id", "name", "plan_id", "country" '
        'FROM "accounts" WHERE "accounts"."tenant_id" = :tenant_id) AS T1 '
        "WHERE T1.name = 'accounts' LIMIT 5"
    )
    assert scoped.params == {"tenant_id": 2}


def test_unaliased_table_keeps_its_name(full_schema: DatabaseSchema) -> None:
    sql = scope("SELECT accounts.name FROM accounts LIMIT 5", full_schema)
    assert sql.endswith(') AS "accounts" LIMIT 5')


def test_guards_never_project_scope_or_hidden_columns(full_schema: DatabaseSchema) -> None:
    sql = scope("SELECT name FROM users LIMIT 5", full_schema)
    assert '"tenant_id" = :tenant_id' in sql
    assert "password_hash" not in sql
    assert '"tenant_id",' not in sql


def test_user_mode_filters_owner_tables_only(full_schema: DatabaseSchema) -> None:
    ctx = ScopeContext(1, user_id=11)
    scoped = apply_scope(
        "SELECT T1.title, T2.name FROM deals AS T1 JOIN users AS T2 ON T2.id = T1.owner_user_id "
        "LIMIT 5",
        POLICY,
        ctx,
        schema=full_schema,
    )
    assert scoped.params == {"tenant_id": 1, "user_id": 11}
    assert scoped.sql.count(":user_id") == 1
    assert scoped.sql.count(":tenant_id") == 2
    users_only = apply_scope("SELECT name FROM users LIMIT 5", POLICY, ctx, schema=full_schema)
    assert users_only.params == {"tenant_id": 1}


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT "name" FROM "accounts" LIMIT 5',
        "SELECT name FROM `accounts` LIMIT 5",
        "SELECT name FROM [accounts] LIMIT 5",
        "SELECT name FROM 'accounts' LIMIT 5",
        "SELECT ACCOUNTS.name FROM ACCOUNTS LIMIT 5",
    ],
)
def test_any_identifier_spelling_is_guarded(
    sql: str, crm_db: Path, full_schema: DatabaseSchema
) -> None:
    scoped = apply_scope(sql, POLICY, ScopeContext(3), schema=full_schema)
    assert query(crm_db, scoped.sql, scoped.params) == [
        ("Acme",),
        ("CANARY-T3",),
        ("Globex",),
        ("Initech",),
    ]


def test_scoped_table_missing_from_schema_is_refused(full_schema: DatabaseSchema) -> None:
    partial = full_schema.subset({"accounts": None})
    with pytest.raises(ScopeViolation) as info:
        scope("SELECT title FROM deals LIMIT 5", partial)
    assert info.value.rule == ScopeRule.UNKNOWN_TABLE
    assert info.value.layer == "scoping"


@pytest.mark.parametrize(
    ("sql", "rule"),
    [
        ("SELECT FROM WHERE", ScopeRule.UNPARSEABLE),
        ("SELECT 1; SELECT 2", ScopeRule.UNPARSEABLE),
        ("DELETE FROM deals", ScopeRule.UNPARSEABLE),
        ("SELECT title FROM main.deals LIMIT 5", ScopeRule.UNGUARDED_TABLE),
        ("SELECT title FROM (deals) LIMIT 5", ScopeRule.UNGUARDED_TABLE),
        ("SELECT title FROM deals INDEXED BY ix LIMIT 5", ScopeRule.UNGUARDED_TABLE),
        ("SELECT name FROM plans WHERE id IN deals LIMIT 5", ScopeRule.UNGUARDED_TABLE),
        ("WITH deals AS (SELECT 1 AS x) SELECT x FROM deals LIMIT 5", ScopeRule.SHADOWED_TABLE),
        ("SELECT title FROM deals WHERE amount = :tenant_id LIMIT 5", ScopeRule.STRAY_PARAMETER),
        ("SELECT title FROM deals WHERE amount = ? LIMIT 5", ScopeRule.STRAY_PARAMETER),
        ("SELECT title FROM deals WHERE amount = @x LIMIT 5", ScopeRule.STRAY_PARAMETER),
        ("SELECT title FROM deals WHERE amount = $x LIMIT 5", ScopeRule.STRAY_PARAMETER),
    ],
)
def test_references_that_cannot_be_guarded_are_refused(
    sql: str, rule: ScopeRule, full_schema: DatabaseSchema
) -> None:
    """The validator rejects all of these first; the scoping layer must not rely on that."""
    with pytest.raises(ScopeViolation) as info:
        scope(sql, full_schema)
    assert info.value.rule == rule


def test_model_cannot_choose_the_tenant_even_without_the_validator(
    crm_db: Path, full_schema: DatabaseSchema
) -> None:
    # The guard does not expose tenant_id, so naming it outside the guard cannot even compile.
    scoped = apply_scope(
        "SELECT title FROM deals WHERE tenant_id = 2 OR 1 = 1 LIMIT 1000",
        POLICY,
        ScopeContext(1),
        schema=full_schema,
    )
    assert scoped.params == {"tenant_id": 1}
    with pytest.raises(sqlite3.OperationalError, match="no such column: tenant_id"):
        query(crm_db, scoped.sql, scoped.params)


def test_scope_context_only_accepts_integer_identities() -> None:
    for bad in ("1", 1.0, True, None):
        with pytest.raises(TypeError):
            ScopeContext(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ScopeContext(1, user_id="7")  # type: ignore[arg-type]


# -- the proof ---------------------------------------------------------------------------------

GUARD = 'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id'


@pytest.mark.parametrize(
    "tampered",
    [
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = 2',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :user_id',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = ?',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id OR 1 = 1',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id AND 1 = 1',
        'SELECT "title" FROM "deals" WHERE ("deals"."tenant_id" = :tenant_id)',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id '
        'AND "deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" WHERE "deals"."owner_user_id" = :tenant_id',
        'SELECT "title" FROM "deals" WHERE "accounts"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" WHERE main."deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" WHERE :tenant_id = "deals"."tenant_id"',
        'SELECT * FROM "deals" WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "tenant_id" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "deals"."title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" AS d WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM main."deals" WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" JOIN plans ON 1 WHERE "deals"."tenant_id" = :tenant_id',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id GROUP BY "title"',
        'SELECT "title" FROM "deals" WHERE "deals"."tenant_id" = :tenant_id LIMIT 5',
        'SELECT "title" FROM "deals"',
    ],
)
def test_proof_rejects_tampered_guards(tampered: str) -> None:
    with pytest.raises(ScopeViolation) as info:
        verify_scope(f"SELECT T1.title FROM ({tampered}) AS T1 LIMIT 5", POLICY, user_mode=False)
    assert info.value.rule == ScopeRule.UNGUARDED_TABLE


def test_proof_rejects_hidden_columns_in_a_guard() -> None:
    guard = 'SELECT "name", "password_hash" FROM "users" WHERE "users"."tenant_id" = :tenant_id'
    with pytest.raises(ScopeViolation):
        verify_scope(f"SELECT T1.name FROM ({guard}) AS T1 LIMIT 5", POLICY, user_mode=False)


def test_proof_checks_the_owner_predicate_against_the_mode() -> None:
    tenant_only = f"SELECT T1.title FROM ({GUARD}) AS T1 LIMIT 5"
    verify_scope(tenant_only, POLICY, user_mode=False)
    with pytest.raises(ScopeViolation):
        verify_scope(tenant_only, POLICY, user_mode=True)
    with_owner = tenant_only.replace(
        ":tenant_id", ':tenant_id AND "deals"."owner_user_id" = :user_id'
    )
    verify_scope(with_owner, POLICY, user_mode=True)
    with pytest.raises(ScopeViolation):
        verify_scope(with_owner, POLICY, user_mode=False)


def test_proof_rejects_parameters_outside_guards() -> None:
    sql = f"SELECT T1.title FROM ({GUARD}) AS T1 WHERE T1.title = :tenant_id LIMIT 5"
    with pytest.raises(ScopeViolation) as info:
        verify_scope(sql, POLICY, user_mode=False)
    assert info.value.rule == ScopeRule.STRAY_PARAMETER


def test_proof_accepts_unqualified_guard_columns() -> None:
    verify_scope(
        'SELECT T1.title FROM (SELECT "title" FROM deals WHERE tenant_id = :tenant_id) AS T1',
        POLICY,
        user_mode=False,
    )


# -- cross-tenant attempts on the fixture database ---------------------------------------------

ADVERSARIAL = [
    "SELECT name FROM accounts WHERE name LIKE 'CANARY%' LIMIT 1000",
    "SELECT title, amount FROM deals WHERE 1 = 1 OR title LIKE 'CANARY%' LIMIT 1000",
    "SELECT T1.name, T2.title FROM accounts AS T1 JOIN deals AS T2 ON T2.account_id = T1.id "
    "LIMIT 1000",
    # same account names in every tenant: an unscoped name join pairs rows across tenants
    "SELECT T1.id, T2.id FROM accounts AS T1 JOIN accounts AS T2 ON T2.name = T1.name LIMIT 1000",
    "SELECT T1.title, T2.title FROM deals AS T1 JOIN deals AS T2 ON T2.amount > T1.amount "
    "LIMIT 1000",
    # LEFT JOIN with the scoped table on either side, and on a non-key condition
    "SELECT T1.name, T2.title FROM accounts AS T1 LEFT JOIN deals AS T2 "
    "ON T2.account_id = T1.id LIMIT 1000",
    "SELECT T1.name, T2.title FROM accounts AS T1 LEFT JOIN deals AS T2 "
    "ON T2.title LIKE 'CANARY%' LIMIT 1000",
    "SELECT T1.name, COUNT(T2.id) AS c1 FROM plans AS T1 LEFT JOIN accounts AS T2 "
    "ON T2.plan_id = T1.id GROUP BY T1.name LIMIT 1000",
    "SELECT T2.name, T1.name FROM accounts AS T1 LEFT JOIN plans AS T2 ON T2.id = T1.plan_id "
    "LIMIT 1000",
    "SELECT name FROM accounts WHERE id IN (SELECT account_id FROM deals WHERE amount > 0) "
    "LIMIT 1000",
    "SELECT name FROM plans WHERE id IN (SELECT plan_id FROM accounts WHERE name LIKE 'CANARY%') "
    "LIMIT 1000",
    "SELECT T1.name FROM accounts AS T1 WHERE EXISTS "
    "(SELECT 1 FROM deals AS T2 WHERE T2.account_id = T1.id AND T2.title LIKE 'CANARY%') "
    "LIMIT 1000",
    "SELECT T1.title FROM deals AS T1 WHERE T1.amount = "
    "(SELECT MAX(T2.amount) FROM deals AS T2 WHERE T2.stage = T1.stage) LIMIT 1000",
    "SELECT (SELECT COUNT(*) FROM deals) AS c1, (SELECT SUM(amount) FROM deals) AS c2 "
    "FROM plans LIMIT 1",
    "SELECT name FROM accounts UNION SELECT title FROM deals UNION SELECT name FROM users "
    "LIMIT 1000",
    "SELECT name FROM plans UNION ALL SELECT name FROM accounts LIMIT 1000",
    "SELECT name FROM accounts EXCEPT SELECT name FROM plans LIMIT 1000",
    "WITH cte1 AS (SELECT id, name FROM accounts), cte2 AS (SELECT account_id, title FROM deals) "
    "SELECT T1.name, T2.title FROM cte1 AS T1 JOIN cte2 AS T2 ON T2.account_id = T1.id "
    "LIMIT 1000",
    "WITH cte1 AS (SELECT name FROM accounts UNION SELECT title FROM deals) "
    "SELECT name FROM cte1 LIMIT 1000",
    "SELECT T1.c1 FROM (SELECT T2.name AS c1 FROM (SELECT name FROM accounts) AS T2) AS T1 "
    "LIMIT 1000",
    "SELECT COUNT(*), SUM(amount), MAX(amount), MIN(title) FROM deals LIMIT 1",
    "SELECT stage, COUNT(*), AVG(amount) FROM deals GROUP BY stage HAVING COUNT(*) > 0 LIMIT 1000",
    "SELECT T1.name, COUNT(T2.id) FROM users AS T1 LEFT JOIN deals AS T2 "
    "ON T2.owner_user_id = T1.id GROUP BY T1.name LIMIT 1000",
    "SELECT name, email FROM users LIMIT 1000",
    "SELECT T1.name FROM users AS T1 JOIN accounts AS T2 ON T2.owner_user_id = T1.id "
    "WHERE T2.name LIKE 'CANARY%' LIMIT 1000",
]


@pytest.mark.parametrize("sql", ADVERSARIAL)
@pytest.mark.parametrize("ctx", CONTEXTS, ids=str)
def test_scoped_results_equal_the_identity_oracle(
    sql: str,
    ctx: ScopeContext,
    crm_db: Path,
    full_schema: DatabaseSchema,
    visible_schema: DatabaseSchema,
    oracle_db: Callable[[ScopeContext], Path],
) -> None:
    validate_sql(sql, visible_schema, TENANT)
    scoped = apply_scope(sql, POLICY, ctx, schema=full_schema)
    verify_scope(scoped.sql, POLICY, user_mode=ctx.user_id is not None)
    got = query(crm_db, scoped.sql, scoped.params)
    assert got == query(oracle_db(ctx), sql)
    assert foreign_canaries(got, ctx.tenant_id) == []


def test_canary_queries_do_leak_without_scoping(crm_db: Path) -> None:
    """Sanity check of the oracle test: the same SQL unscoped returns other tenants' canaries."""
    leaking = [q for q in ADVERSARIAL if foreign_canaries(query(crm_db, q), tenant=1)]
    assert len(leaking) >= len(ADVERSARIAL) // 2


def test_scoped_queries_run_under_the_sandboxed_executor(
    crm_db: Path, full_schema: DatabaseSchema, oracle_db: Callable[[ScopeContext], Path]
) -> None:
    """The guards read only columns the strict authorizer allows (no password_hash)."""
    access = AccessPolicy(readable=POLICY.readable_columns(full_schema))
    ctx = ScopeContext(2, user_id=user_ids(2)[0])
    with SandboxedExecutor(crm_db, access=access) as executor:
        for sql in ADVERSARIAL:
            scoped = apply_scope(sql, POLICY, ctx, schema=full_schema)
            result = executor.execute(scoped.sql, scoped.params)
            assert sorted(result.rows, key=repr) == query(oracle_db(ctx), sql)
