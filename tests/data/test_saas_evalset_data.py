"""The committed SaaS evaluation set and few-shot pool, checked on a freshly generated database.

These are the guarantees the dataset card makes: bucket sizes, gold that executes for every tenant
an item runs under, tenant items whose answers differ, no gold for unanswerable items, explicit
tenant filters in every gold query, and a few-shot pool disjoint from the evaluation questions.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import get_args

import pytest

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.data.saas import load_saas_schema, planted_injections, saas_scope_policy
from text2sql.data.saas.evalset import (
    AttackCategory,
    FewShotItem,
    SaasEvalItem,
    load_fewshot_pool,
    load_saas_eval,
)
from text2sql.data.saas.evalset.gold import (
    MAX_GOLD_ROWS,
    authoring_schema,
    prove_explicit_scope,
    readable_columns,
)
from text2sql.data.saas.generate import generate_database
from text2sql.execution import AccessPolicy, ExecutionLimits, QueryResult, SandboxedExecutor
from text2sql.grammar import GrammarOptions, build_grammar
from text2sql.safety import ScopeContext, apply_scope

SPEC = {"answerable": 150, "tenant": 60, "unanswerable": 40, "adversarial": 50}
POLICY = saas_scope_policy()


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("saas_evalset") / "crm.sqlite"
    generate_database(path)
    return path


@pytest.fixture(scope="module")
def full_schema(db: Path) -> DatabaseSchema:
    return load_saas_schema(db)


@pytest.fixture(scope="module")
def executor(db: Path, full_schema: DatabaseSchema) -> Iterator[SandboxedExecutor]:
    readable = readable_columns(authoring_schema(full_schema, POLICY))
    with SandboxedExecutor(
        db,
        limits=ExecutionLimits(timeout_s=10.0, max_rows=MAX_GOLD_ROWS),
        access=AccessPolicy(readable=readable),
    ) as ex:
        yield ex


@pytest.fixture(scope="module")
def items() -> list[SaasEvalItem]:
    return load_saas_eval()


@pytest.fixture(scope="module")
def pool() -> list[FewShotItem]:
    return load_fewshot_pool()


def _usable(result: QueryResult) -> bool:
    has_value = any(cell is not None for row in result.rows for cell in row)
    return bool(result.rows) and has_value and not result.truncated


def _words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


def test_bucket_sizes_match_the_targets(items: list[SaasEvalItem]) -> None:
    counts: Counter[str] = Counter(i.bucket for i in items)
    for bucket, target in SPEC.items():
        assert abs(counts[bucket] - target) <= 0.05 * target, (bucket, counts[bucket])


def test_every_bucket_has_a_held_out_share(items: list[SaasEvalItem]) -> None:
    for bucket in SPEC:
        splits = Counter(i.split for i in items if i.bucket == bucket)
        share = splits["test"] / (splits["test"] + splits["dev"])
        assert 0.25 <= share <= 0.35, (bucket, splits)


def test_gold_executes_for_every_tenant_an_item_runs_under(
    items: list[SaasEvalItem], executor: SandboxedExecutor
) -> None:
    for item in items:
        if item.gold_sql is None:
            continue
        for tenant in item.eval_tenants or [item.tenant_id]:
            result = executor.execute(item.gold_sql, item.params(tenant))
            assert _usable(result), (item.id, tenant)


def test_tenant_items_have_different_answers_per_tenant(
    items: list[SaasEvalItem], executor: SandboxedExecutor
) -> None:
    for item in items:
        if item.bucket != "tenant":
            continue
        assert item.gold_sql is not None
        answers = [
            frozenset(executor.execute(item.gold_sql, item.params(t)).rows)
            for t in item.eval_tenants
        ]
        assert len(set(answers)) == len(answers), item.id


def test_gold_filters_every_tenant_table_explicitly(items: list[SaasEvalItem]) -> None:
    for item in items:
        if item.gold_sql is not None:
            prove_explicit_scope(item.gold_sql, POLICY, user_mode=item.user_id is not None)


def test_unanswerable_items_have_no_gold_and_say_why(items: list[SaasEvalItem]) -> None:
    unanswerable = [i for i in items if i.bucket == "unanswerable"]
    assert unanswerable
    for item in unanswerable:
        assert item.gold_sql is None and item.should_abstain
        assert item.explanation and len(item.explanation) > 20, item.id


def test_adversarial_items_cover_every_attack_category(items: list[SaasEvalItem]) -> None:
    attacks = [i for i in items if i.bucket == "adversarial"]
    categories = {i.attack.category for i in attacks if i.attack is not None}
    assert categories == set(get_args(AttackCategory))
    for item in attacks:
        assert item.attack is not None and item.expected == "safe"
        if item.attack.category == "cross_tenant" and item.attack.target_tenant_id is not None:
            assert item.attack.target_tenant_id != item.tenant_id, item.id
        if item.attack.technique in {"homoglyph", "zero_width", "fullwidth", "bidi_override"}:
            assert not item.question.isascii(), item.id


def test_indirect_injection_gold_returns_the_planted_value(
    items: list[SaasEvalItem], executor: SandboxedExecutor
) -> None:
    planted = {(p.tenant_id, p.text) for p in planted_injections()}
    indirect = [i for i in items if i.attack and i.attack.category == "indirect_injection"]
    assert indirect
    for item in indirect:
        assert item.gold_sql is not None
        cells = {c for row in executor.execute(item.gold_sql, item.params()).rows for c in row}
        assert any(text in cells for tenant, text in planted if tenant == item.tenant_id), item.id


def test_user_mode_items_belong_to_a_user_of_their_tenant(
    items: list[SaasEvalItem], db: Path
) -> None:
    user_items = [i for i in items if i.user_id is not None]
    assert user_items
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        for item in user_items:
            row = conn.execute(
                "SELECT tenant_id FROM users WHERE user_id = ?", (item.user_id,)
            ).fetchone()
            assert row == (item.tenant_id,), item.id


def test_questions_are_not_repeated(items: list[SaasEvalItem]) -> None:
    normalized = Counter(" ".join(sorted(_words(i.question))) for i in items)
    assert max(normalized.values()) == 1


def test_fewshot_pool_is_disjoint_from_the_eval_set(
    pool: list[FewShotItem], items: list[SaasEvalItem]
) -> None:
    assert 38 <= len(pool) <= 42
    eval_words = [_words(i.question) for i in items]
    for example in pool:
        words = _words(example.question)
        overlap = max(len(words & w) / len(words | w) for w in eval_words)
        assert overlap < 0.6, example.id


def test_fewshot_sql_is_tenant_mode_sql_that_scopes_and_runs(
    pool: list[FewShotItem], full_schema: DatabaseSchema, executor: SandboxedExecutor
) -> None:
    visible = POLICY.visible_schema(full_schema)
    grammar = build_grammar(visible, GrammarOptions(mode=QueryMode.TENANT, max_rows=200))
    for example in pool:
        assert grammar.accepts(example.sql), example.id
        scoped = apply_scope(
            example.sql, POLICY, ScopeContext(tenant_id=1, user_id=None), schema=full_schema
        )
        executor.execute(scoped.sql, scoped.params)
