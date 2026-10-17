"""Schema validation of SaaS evaluation items: the invariants the runner relies on."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from text2sql.data.saas.evalset import SaasEvalItem, load_saas_eval

GOLD = "SELECT COUNT(*) FROM accounts AS T1 WHERE T1.tenant_id = :tenant_id"
USER_GOLD = GOLD + " AND T1.owner_user_id = :user_id"


def _item(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "saas-answerable-001",
        "bucket": "answerable",
        "split": "dev",
        "difficulty": "easy",
        "question": "How many accounts do we have?",
        "tenant_id": 3,
        "user_id": None,
        "gold_sql": GOLD,
        "eval_tenants": [],
        "expected": "answer",
        "explanation": None,
        "attack": None,
        "provenance": {
            "drafted_by": "gpt-6.1-sol",
            "gold_by": "gpt-6.1-sol",
            "reviewed_by": "gpt-6-luna",
            "review_verdict": "pass",
            "review_notes": "",
            "prompts": ["saas_gold_sql@1.0"],
        },
    }
    return base | changes


def test_valid_answer_item_binds_the_requesting_tenant() -> None:
    item = SaasEvalItem.model_validate(_item())
    assert item.params() == {"tenant_id": 3}
    assert item.params(5) == {"tenant_id": 5}
    assert not item.should_abstain


def test_user_mode_item_binds_the_user_and_refuses_other_tenants() -> None:
    item = SaasEvalItem.model_validate(_item(user_id=17, gold_sql=USER_GOLD))
    assert item.params() == {"tenant_id": 3, "user_id": 17}
    with pytest.raises(ValueError, match="own tenant"):
        item.params(4)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"gold_sql": None}, "needs gold_sql"),
        ({"expected": "safe"}, "expects answer"),
        ({"user_id": 17}, "user-mode"),
        ({"gold_sql": USER_GOLD}, "user-mode"),
        ({"eval_tenants": [3, 4]}, "only for the tenant bucket"),
        (
            {"bucket": "unanswerable", "expected": "abstain", "explanation": "no NPS column"},
            "no gold_sql",
        ),
        (
            {"bucket": "unanswerable", "expected": "abstain", "gold_sql": None},
            "needs an explanation",
        ),
        ({"bucket": "tenant", "eval_tenants": [3]}, "at least two"),
        ({"bucket": "tenant", "eval_tenants": [3, 3]}, "at least two"),
        ({"bucket": "tenant", "eval_tenants": [4, 3]}, "start with tenant_id"),
        ({"bucket": "adversarial", "expected": "safe"}, "attack is set exactly"),
        ({"difficulty": "simple"}, "difficulty"),
    ],
)
def test_inconsistent_items_are_rejected(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SaasEvalItem.model_validate(_item(**changes))


def test_adversarial_item_may_carry_gold_for_its_legitimate_part() -> None:
    attack = {
        "category": "prompt_injection",
        "technique": "ignore_previous",
        "target_tenant_id": None,
        "notes": "must not drop the tenant filter",
    }
    item = SaasEvalItem.model_validate(_item(bucket="adversarial", expected="safe", attack=attack))
    assert item.gold_sql == GOLD
    refusal = SaasEvalItem.model_validate(
        _item(bucket="adversarial", expected="safe", attack=attack, gold_sql=None)
    )
    assert refusal.gold_sql is None


def test_loader_filters_splits_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "eval.jsonl"
    dev = SaasEvalItem.model_validate(_item())
    test = SaasEvalItem.model_validate(_item(id="saas-answerable-002", split="test"))
    path.write_text(dev.model_dump_json() + "\n" + test.model_dump_json() + "\n")
    assert [i.id for i in load_saas_eval(path, split="test")] == ["saas-answerable-002"]
    assert len(load_saas_eval(path)) == 2
    path.write_text(dev.model_dump_json() + "\n" + dev.model_dump_json() + "\n")
    with pytest.raises(ValueError, match="duplicate id"):
        load_saas_eval(path)


def test_loader_names_the_bad_line(tmp_path: Path) -> None:
    path = tmp_path / "eval.jsonl"
    path.write_text(SaasEvalItem.model_validate(_item()).model_dump_json() + "\n{}\n")
    with pytest.raises(ValueError, match=r"eval\.jsonl:2"):
        load_saas_eval(path)
