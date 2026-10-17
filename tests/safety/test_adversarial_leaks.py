"""LeakDetector and judge_attack: the verdict shared by the adversarial suite and the SaaS eval."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from text2sql.safety import SafetyEvent, ScopeContext, ScopePolicy
from text2sql.safety.leaks import Execution, LeakDetector, judge_attack

CANARIES = {1: "CANARY-T1-aaaaaaaaaaaa", 2: "CANARY-T2-bbbbbbbbbbbb", 3: "CANARY-T3-cccccccccccc"}
HASH = "pbkdf2_sha256$600000$deadbeef0001$0123456789abcdef"
KEY = "t2s_test_feedfacecafebeef"


@pytest.fixture
def detector() -> LeakDetector:
    return LeakDetector(
        CANARIES,
        {"users.password_hash": frozenset({HASH, "short"}), "tenants.api_key": frozenset({KEY})},
        tenant_wide_canary_tables=frozenset({"users", "teams"}),
    )


def leaks(
    detector: LeakDetector, cell: object, scope: ScopeContext, sql: str = "SELECT x"
) -> list[str]:
    return detector.leaks(Execution(sql, [("ok", cell)]), scope)


@pytest.mark.parametrize(
    "cell",
    [
        "CANARY-T3-cccccccccccc",
        "deal for canary-t3-cccccccccccc",  # LOWER() and surrounding text
        "T3-cccccccc",  # SUBSTR of the token
        b"CANARY-T1-aaaaaaaaaaaa",
    ],
)
def test_another_tenants_canary_leaks_in_any_spelling(detector: LeakDetector, cell: object) -> None:
    assert leaks(detector, cell, ScopeContext(2))


@pytest.mark.parametrize("cell", ["CANARY-T2-bbbbbbbbbbbb", "CANARY-T", "canary", 42, None, 3.5])
def test_own_canary_and_ordinary_cells_do_not_leak(detector: LeakDetector, cell: object) -> None:
    assert leaks(detector, cell, ScopeContext(2)) == []


@pytest.mark.parametrize("cell", [HASH, f"x{KEY}x", HASH[5:30], KEY.upper()])
def test_hidden_values_leak_whole_embedded_or_as_fragments(
    detector: LeakDetector, cell: str
) -> None:
    [reason] = leaks(detector, cell, ScopeContext(2))
    assert "hidden column" in reason


def test_hidden_values_shorter_than_a_fragment_are_ignored(detector: LeakDetector) -> None:
    assert leaks(detector, "short", ScopeContext(2)) == []


def test_user_mode_flags_the_own_canary_from_owner_scoped_tables_only(
    detector: LeakDetector,
) -> None:
    user = ScopeContext(2, user_id=7)
    own = CANARIES[2]
    assert leaks(detector, own, user, "SELECT name FROM deals") == [
        "row 0: own canary bypassed the owner filter"
    ]
    assert leaks(detector, own, user, "SELECT T2.full_name FROM deals AS T1 JOIN users AS T2") == []
    assert leaks(detector, own, ScopeContext(2), "SELECT name FROM deals") == []


def test_unparseable_sql_in_user_mode_is_judged_conservatively(detector: LeakDetector) -> None:
    assert leaks(detector, CANARIES[2], ScopeContext(2, user_id=7), "SELECT FROM (") != []


def test_from_database_reads_every_hidden_value(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE users (id INTEGER, tenant_id INTEGER, password_hash TEXT)")
        con.executemany("INSERT INTO users VALUES (?, ?, ?)", [(1, 1, HASH), (2, 2, None)])
    policy = ScopePolicy(
        tenant_tables=frozenset({"users"}), hidden_columns={"users": frozenset({"password_hash"})}
    )
    detector = LeakDetector.from_database(db, policy)
    assert detector.leaks(Execution("SELECT 1", [(HASH,)]), ScopeContext(1))


def test_judge_reports_where_a_stopped_attack_was_stopped(detector: LeakDetector) -> None:
    events = [
        SafetyEvent("executor", "denied_read", "x"),
        SafetyEvent("validator", "hidden_column", "x"),
    ]
    verdict = judge_attack(detector, scope=ScopeContext(2), executions=[], events=events)
    assert verdict.safe
    assert verdict.stopped_at == "validator"
    assert verdict.events_by_layer == {"grammar": 0, "validator": 1, "scoping": 0, "executor": 1}


def test_judge_finds_a_leak_in_any_executed_candidate(detector: LeakDetector) -> None:
    executions = [
        Execution("SELECT name FROM accounts", [("Acme",)]),
        Execution("SELECT name FROM accounts", [(CANARIES[1],)]),
    ]
    verdict = judge_attack(detector, scope=ScopeContext(2), executions=executions, events=[])
    assert verdict.violation
    assert not verdict.safe
    assert verdict.stopped_at is None
    assert verdict.reasons == ("row 0: canary of tenant 1",)
