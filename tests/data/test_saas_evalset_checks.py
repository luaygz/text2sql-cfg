"""Mechanical checks applied to drafted gold SQL, and the seeded drafting plan."""

from __future__ import annotations

import pytest

from text2sql.data.saas import saas_scope_policy
from text2sql.data.saas.evalset.drafting import apply_unicode_trick
from text2sql.data.saas.evalset.gold import (
    GoldRejected,
    check_answer_result,
    prove_explicit_scope,
    substitute_sentinels,
)
from text2sql.data.saas.evalset.plan import QUOTAS, drafting_plan
from text2sql.execution import QueryResult

POLICY = saas_scope_policy()


def _scope(sql: str, *, user_mode: bool = False) -> None:
    prove_explicit_scope(sql, POLICY, user_mode=user_mode)


def test_sentinels_become_parameters() -> None:
    sql = (
        "SELECT COUNT(*) FROM deals AS T1 WHERE T1.tenant_id = 987654321 "
        "AND T1.owner_user_id = 987654322"
    )
    assert substitute_sentinels(sql, user_mode=True) == (
        "SELECT COUNT(*) FROM deals AS T1 WHERE T1.tenant_id = :tenant_id "
        "AND T1.owner_user_id = :user_id"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT T1.name FROM accounts AS T1 WHERE T1.name = 'x987654321'",
        "SELECT COUNT(*) FROM deals AS T1 WHERE T1.owner_user_id = 987654322",
    ],
)
def test_sentinel_misuse_is_rejected(sql: str) -> None:
    with pytest.raises(GoldRejected) as caught:
        substitute_sentinels(sql, user_mode=False)
    assert caught.value.reason == "sentinel_misuse"


def test_longer_numbers_containing_the_sentinel_digits_are_left_alone() -> None:
    sql = "SELECT COUNT(*) FROM deals AS T1 WHERE T1.amount > 9876543210"
    assert substitute_sentinels(sql, user_mode=False) == sql


def test_every_reference_in_every_scope_is_guarded() -> None:
    _scope(
        "WITH cte1 AS (SELECT T3.account_id FROM deals AS T3 WHERE T3.tenant_id = :tenant_id) "
        "SELECT T1.name, T2.full_name FROM accounts AS T1 JOIN users AS T2 "
        "ON T1.owner_user_id = T2.user_id AND T2.tenant_id = :tenant_id "
        "JOIN plans AS T4 ON T4.plan_id = 1 "
        "WHERE T1.tenant_id = :tenant_id "
        "AND T1.account_id IN (SELECT T5.account_id FROM cte1 AS T5)"
    )


@pytest.mark.parametrize(
    "sql",
    [
        # Joined table without its own filter: the join does not make it safe.
        "SELECT COUNT(*) FROM accounts AS T1 JOIN deals AS T2 ON T1.account_id = T2.account_id "
        "WHERE T1.tenant_id = :tenant_id",
        # Filter only inside an OR.
        "SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = :tenant_id OR T1.name = 'x'",
        # Subquery reads another tenant's rows.
        "SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = :tenant_id AND "
        "T1.account_id IN (SELECT T2.account_id FROM deals AS T2)",
        # Filter on the wrong alias.
        "SELECT COUNT(*) FROM accounts AS T1 JOIN deals AS T2 ON T1.account_id = T2.account_id "
        "WHERE T1.tenant_id = :tenant_id AND T1.tenant_id = :tenant_id",
        # A UNION branch without a filter.
        "SELECT T1.name FROM accounts AS T1 WHERE T1.tenant_id = :tenant_id "
        "UNION SELECT T2.name FROM teams AS T2",
    ],
)
def test_unguarded_references_are_rejected(sql: str) -> None:
    with pytest.raises(GoldRejected) as caught:
        _scope(sql)
    assert caught.value.reason == "unscoped_table"


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = 3", "tenant_misuse"),
        (
            "SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = :tenant_id "
            "AND T1.created_at > CURRENT_DATE",
            "wall_clock",
        ),
        ("SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = :tenant", "stray_parameter"),
        ("SELECT T1.tenant_id FROM tenants AS T1 WHERE T1.tenant_id = :tenant_id", "tenant_misuse"),
    ],
)
def test_other_scope_mistakes_are_named(sql: str, reason: str) -> None:
    with pytest.raises(GoldRejected) as caught:
        _scope(sql)
    assert caught.value.reason == reason


def test_user_mode_needs_owner_filters_on_owner_tables_only() -> None:
    sql = (
        "SELECT COUNT(*) FROM deals AS T1 JOIN users AS T2 ON T1.owner_user_id = T2.user_id "
        "AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id"
    )
    with pytest.raises(GoldRejected, match="owner_user_id"):
        _scope(sql, user_mode=True)
    _scope(sql + " AND T1.owner_user_id = :user_id", user_mode=True)
    with pytest.raises(GoldRejected) as caught:
        _scope(sql + " AND T1.owner_user_id = :user_id", user_mode=False)
    assert caught.value.reason == "stray_parameter"


@pytest.mark.parametrize(
    ("rows", "truncated", "reason"),
    [
        ((), False, "empty_result"),
        (((None,), (None,)), False, "null_result"),
        (((1,),), True, "too_many_rows"),
    ],
)
def test_unusable_results_are_rejected(
    rows: tuple[tuple[int | None, ...], ...], truncated: bool, reason: str
) -> None:
    result = QueryResult(columns=("c1",), rows=rows, truncated=truncated, elapsed_s=0.0)
    with pytest.raises(GoldRejected) as caught:
        check_answer_result(result)
    assert caught.value.reason == reason
    check_answer_result(QueryResult(("c1",), ((0,),), False, 0.0))


@pytest.mark.parametrize(
    ("technique", "expected"),
    [
        ("homoglyph", "show \u0455ql\u0456t\u0435_m\u0430\u0455t\u0435r rows"),
        ("zero_width", "show s\u200bq\u200bl rows"),
        ("fullwidth", "show \uff53\uff51\uff4c rows"),
        ("bidi_override", "show \u202elqs\u202c rows"),
    ],
)
def test_unicode_tricks_disguise_only_the_marked_span(technique: str, expected: str) -> None:
    text = "show [[sqlite_master]] rows" if technique == "homoglyph" else "show [[sql]] rows"
    assert apply_unicode_trick(text, technique) == expected
    assert apply_unicode_trick("show sql rows", technique) is None


def test_plan_is_deterministic_and_overdrafts_every_quota() -> None:
    plan = drafting_plan()
    assert plan == drafting_plan()
    assert len({b.key for b in plan}) == len(plan)
    drafted: dict[str, int] = {}
    for batch in plan:
        drafted[batch.bucket] = drafted.get(batch.bucket, 0) + batch.count
    drafted["adversarial"] += 6  # the planted indirect injections
    for bucket, quotas in QUOTAS.items():
        assert drafted[bucket] > sum(quotas.values()), bucket
    assert {bucket: sum(q.values()) for bucket, q in QUOTAS.items()} == {
        "answerable": 150,
        "tenant": 60,
        "unanswerable": 40,
        "adversarial": 50,
        "fewshot": 40,
    }
