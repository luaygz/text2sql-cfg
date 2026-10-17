"""QueryGuard: layer order, event logging and the contract with the pipeline.

Uses the small CRM fixture from conftest (three tenants, canary rows, `users.password_hash`
hidden). Paths that layers 1 and 2 make unreachable are exercised by switching those layers off
(grammar=None, or a validator patched to accept), the way the adversarial suite isolates layers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from safety_fixture import POLICY, canary

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.execution import ExecutionLimits, QueryFailed, QueryTimeout
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar
from text2sql.safety import (
    GuardRejection,
    GuardResult,
    QueryGuard,
    SafetyEventLog,
    ScopeContext,
    ScopedQuery,
    ScopeRule,
    ScopeViolation,
    access_policy,
)
from text2sql.safety import guard as guard_module

TENANT = ScopeContext(2)
OWN_DEALS = "SELECT DISTINCT title FROM deals WHERE title LIKE 'CANARY%' LIMIT 10"
HIDDEN = "SELECT password_hash FROM users LIMIT 5"


@pytest.fixture(scope="module")
def grammar(visible_schema: DatabaseSchema) -> SqlGrammar:
    return build_grammar(visible_schema, GrammarOptions(QueryMode.TENANT, max_rows=100))


@pytest.fixture
def log(tmp_path: Path) -> SafetyEventLog:
    return SafetyEventLog(tmp_path / "events.jsonl")


@pytest.fixture
def guard(crm_db: Path, full_schema: DatabaseSchema, log: SafetyEventLog) -> Iterator[QueryGuard]:
    with QueryGuard(
        db_path=crm_db,
        full_schema=full_schema,
        mode=QueryMode.TENANT,
        policy=POLICY,
        limits=ExecutionLimits(timeout_s=0.3),
        max_rows=100,
        event_log=log,
    ) as guard:
        yield guard


def run(
    guard: QueryGuard,
    sql: str,
    grammar: SqlGrammar | None,
    *,
    scope: ScopeContext | None = TENANT,
    allowed: DatabaseSchema | None = None,
    context: dict[str, str] | None = None,
) -> GuardResult:
    return asyncio.run(
        guard.run(sql, grammar=grammar, allowed=allowed, scope=scope, context=context or {})
    )


def rejection(
    guard: QueryGuard,
    sql: str,
    grammar: SqlGrammar | None,
    *,
    allowed: DatabaseSchema | None = None,
    context: dict[str, str] | None = None,
) -> GuardRejection:
    with pytest.raises(GuardRejection) as caught:
        run(guard, sql, grammar, allowed=allowed, context=context)
    return caught.value


def test_a_scoped_query_runs_with_the_guard_spliced_in_and_returns_only_own_rows(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog
) -> None:
    done = run(guard, OWN_DEALS, grammar)

    assert done.sql == OWN_DEALS
    assert ":tenant_id" in done.executed_sql
    assert done.params == {"tenant_id": 2}
    assert done.result.rows == ((canary(2),),)
    assert log.read() == []


def test_user_mode_binds_the_user_from_the_scope_context(
    guard: QueryGuard, grammar: SqlGrammar
) -> None:
    sql = "SELECT DISTINCT owner_user_id FROM deals LIMIT 10"
    done = run(guard, sql, grammar, scope=ScopeContext(2, user_id=21))
    assert done.params == {"tenant_id": 2, "user_id": 21}
    assert done.result.rows == ((21,),)


def test_the_grammar_stops_first_and_exactly_one_event_is_logged(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog
) -> None:
    sql = f"{HIDDEN}; DROP TABLE users"
    stop = rejection(guard, sql, grammar, context={"question_id": "q7", "strategy": "direct"})

    assert (stop.layer, stop.rule) == ("grammar", guard_module.GRAMMAR_RULE)
    [event] = log.read()
    assert (event.layer, event.rule, event.sql) == ("grammar", stop.rule, sql)
    assert event.context == {
        "question_id": "q7",
        "strategy": "direct",
        "mode": "tenant",
        "grammar": grammar.fingerprint[:12],
        "tenant_id": "2",
    }


def test_without_the_grammar_the_validator_stops_it(guard: QueryGuard, log: SafetyEventLog) -> None:
    stop = rejection(guard, HIDDEN, None)

    assert (stop.layer, stop.rule) == ("validator", "hidden_column")
    [event] = log.read()
    assert event.layer == "validator"
    assert event.context["grammar"] == "off"


def test_the_validator_checks_against_the_requests_allowlist(
    guard: QueryGuard, grammar: SqlGrammar, visible_schema: DatabaseSchema
) -> None:
    linked = visible_schema.subset({"accounts": None})
    stop = rejection(guard, OWN_DEALS, grammar, allowed=linked)
    assert (stop.layer, stop.rule) == ("validator", "unknown_table")


def test_a_scoping_failure_is_logged_and_raised(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object, **__: object) -> ScopedQuery:
        raise ScopeViolation(ScopeRule.UNGUARDED_TABLE, "deals is read without a guard")

    monkeypatch.setattr(guard_module, "apply_scope", refuse)
    stop = rejection(guard, OWN_DEALS, grammar)

    assert (stop.layer, stop.rule) == ("scoping", "unguarded_table")
    assert [(e.layer, e.rule) for e in log.read()] == [("scoping", "unguarded_table")]


def test_the_executor_still_denies_hidden_columns_when_every_earlier_layer_fails(
    guard: QueryGuard, log: SafetyEventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard_module, "validate_sql", lambda *_: None)
    monkeypatch.setattr(
        guard_module, "apply_scope", lambda sql, *_, **__: ScopedQuery(sql=sql, params={})
    )
    stop = rejection(guard, HIDDEN, None)

    assert (stop.layer, stop.rule) == ("executor", "denied_read")
    [event] = log.read()
    assert (event.layer, event.sql) == ("executor", HIDDEN)


def test_a_timeout_is_logged_and_propagates_for_the_repair_loop(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog
) -> None:
    joins = " ".join(f"INNER JOIN deals AS T{i} ON 1 = 1" for i in range(2, 10))
    with pytest.raises(QueryTimeout):
        run(guard, f"SELECT COUNT(*) FROM deals AS T1 {joins} LIMIT 1", grammar)
    assert [(e.layer, e.rule) for e in log.read()] == [("executor", guard_module.TIMEOUT_RULE)]


def test_an_ordinary_sqlite_error_propagates_without_a_safety_event(
    guard: QueryGuard, log: SafetyEventLog
) -> None:
    with pytest.raises(QueryFailed):
        run(guard, "SELECT title FROM deals LIMIT 5 OFFSET 99999999999999999999", None)
    assert log.read() == []


def test_tenant_mode_without_a_scope_context_is_a_caller_bug(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog
) -> None:
    with pytest.raises(ValueError, match="ScopeContext"):
        run(guard, OWN_DEALS, grammar, scope=None)
    assert log.read() == []


def test_an_abstention_never_reaches_execution(
    guard: QueryGuard, visible_schema: DatabaseSchema
) -> None:
    abstaining = build_grammar(
        visible_schema, GrammarOptions(QueryMode.TENANT, max_rows=100, allow_abstain=True)
    )
    with pytest.raises(ValueError, match="abstention"):
        run(guard, "ABSTAIN: the database has no such data", abstaining)


def test_a_grammar_built_for_another_mode_is_refused(
    guard: QueryGuard, visible_schema: DatabaseSchema
) -> None:
    benchmark = build_grammar(visible_schema, GrammarOptions(QueryMode.BENCHMARK))
    with pytest.raises(ValueError, match="grammar"):
        run(guard, OWN_DEALS, benchmark)


def test_tenant_mode_needs_a_policy_and_benchmark_mode_refuses_a_scope(
    crm_db: Path, full_schema: DatabaseSchema, log: SafetyEventLog
) -> None:
    def make(mode: QueryMode) -> QueryGuard:
        return QueryGuard(
            db_path=crm_db,
            full_schema=full_schema,
            mode=mode,
            policy=None,
            limits=ExecutionLimits(),
            max_rows=100,
            event_log=log,
        )

    with pytest.raises(ValueError, match="ScopePolicy"):
        make(QueryMode.TENANT)
    with make(QueryMode.BENCHMARK) as bird:
        with pytest.raises(ValueError, match="does not scope"):
            run(bird, "SELECT name FROM accounts", None)
        assert len(run(bird, "SELECT name FROM accounts", None, scope=None).result.rows) == 12


def test_access_policy_follows_mode_and_policy(full_schema: DatabaseSchema) -> None:
    assert access_policy(full_schema, mode=QueryMode.BENCHMARK, policy=None).readable is None

    tenant = access_policy(full_schema, mode=QueryMode.TENANT, policy=POLICY).readable
    production = access_policy(full_schema, mode=QueryMode.PRODUCTION, policy=POLICY).readable
    assert tenant is not None
    assert production is not None
    assert {"tenant_id", "owner_user_id"} <= tenant["deals"]
    assert "tenant_id" not in production["deals"]
    assert "password_hash" not in tenant["users"] | production["users"]
    assert tenant["plans"] == production["plans"] == {"id", "name", "monthly_price"}


def test_rejection_details_are_bounded(
    guard: QueryGuard, grammar: SqlGrammar, log: SafetyEventLog
) -> None:
    rejection(guard, "SELECT " + "x, " * 2000 + "title FROM deals LIMIT 5", grammar)
    rejection(guard, "SELECT " + "x, " * 2000 + "title FROM deals LIMIT 5", None)
    details = [e.detail for e in log.read()]
    assert len(details) == 2
    assert all(len(d) <= guard_module.MAX_DETAIL_CHARS for d in details)
