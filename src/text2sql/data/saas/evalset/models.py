"""Item types of the SaaS evaluation set and few-shot pool, and their JSONL loaders.

Gold SQL is written against the full schema and filters every tenant table explicitly with the
named parameter `:tenant_id` (and every owner table with `:user_id` for user-mode items), so it
can be executed for any tenant without the scoping layer. `SaasEvalItem.params` binds them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from text2sql.config import REPO_ROOT
from text2sql.safety.scoping import TENANT_PARAM, USER_PARAM

EVAL_PATH = REPO_ROOT / "data" / "saas" / "eval.jsonl"
FEWSHOT_PATH = REPO_ROOT / "data" / "saas" / "fewshot_pool.jsonl"

Bucket = Literal["answerable", "tenant", "unanswerable", "adversarial"]
Difficulty = Literal["easy", "medium", "hard"]
Expected = Literal["answer", "abstain", "safe"]
Split = Literal["dev", "test"]
AttackCategory = Literal[
    "prompt_injection",
    "cross_tenant",
    "write_ddl",
    "system_catalog",
    "sql_smuggling",
    "comment_unicode",
    "hidden_column",
    "indirect_injection",
]

EXPECTED_BY_BUCKET: dict[Bucket, Expected] = {
    "answerable": "answer",
    "tenant": "answer",
    "unanswerable": "abstain",
    "adversarial": "safe",
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _Identified(_Frozen):
    id: str


class Attack(_Frozen):
    category: AttackCategory
    technique: str
    """Short label of the trick, e.g. `role_play`, `homoglyph`, `stacked_statement`."""
    target_tenant_id: int | None
    """The other tenant a cross-tenant request names (by id or company name), if any."""
    notes: str
    """What a safe system must not do for this item."""


class Provenance(_Frozen):
    drafted_by: str
    """Model that wrote the question."""
    gold_by: str | None
    """Model that wrote the gold SQL through the grammar tool; None without gold."""
    reviewed_by: str
    review_verdict: Literal["pass", "fixed"]
    """`fixed`: passed only after a repair of the gold SQL or a difficulty relabel."""
    review_notes: str
    prompts: list[str]
    """`name@version` of every prompt template involved."""


class SaasEvalItem(_Identified):
    bucket: Bucket
    split: Split
    difficulty: Difficulty
    question: str
    tenant_id: int
    """The requesting tenant (`ScopeContext.tenant_id`)."""
    user_id: int | None
    """Set for user-mode items (`ScopeContext.user_id`); the gold also filters owners."""
    gold_sql: str | None
    """SQLite with `:tenant_id` (and `:user_id`) parameters; None when no answer is expected."""
    eval_tenants: list[int]
    """Tenant bucket: every tenant to run the question under (tenant_id first); gold results
    differ pairwise. Empty for the other buckets."""
    expected: Expected
    explanation: str | None
    """Unanswerable items: why a correct system abstains."""
    attack: Attack | None
    provenance: Provenance

    @property
    def should_abstain(self) -> bool:
        return self.expected == "abstain"

    def params(self, tenant_id: int | None = None) -> dict[str, int]:
        """Bound parameters of `gold_sql` for `tenant_id` (default: the requesting tenant)."""
        tenant = self.tenant_id if tenant_id is None else tenant_id
        if self.user_id is not None and tenant != self.tenant_id:
            raise ValueError(f"{self.id}: a user-mode item only runs under its own tenant")
        bound = {TENANT_PARAM: tenant}
        if self.user_id is not None:
            bound[USER_PARAM] = self.user_id
        return bound

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        problems: list[str] = []
        if self.expected != EXPECTED_BY_BUCKET[self.bucket]:
            problems.append(f"bucket {self.bucket} expects {EXPECTED_BY_BUCKET[self.bucket]}")
        if self.expected == "answer" and self.gold_sql is None:
            problems.append("an answer item needs gold_sql")
        if self.expected == "abstain" and (self.gold_sql is not None or not self.explanation):
            problems.append("an unanswerable item has no gold_sql and needs an explanation")
        if (self.attack is not None) != (self.bucket == "adversarial"):
            problems.append("attack is set exactly for adversarial items")
        if self.bucket == "tenant":
            if len(set(self.eval_tenants)) != len(self.eval_tenants) or len(self.eval_tenants) < 2:
                problems.append("a tenant item needs at least two distinct eval_tenants")
            elif self.eval_tenants[0] != self.tenant_id:
                problems.append("eval_tenants must start with tenant_id")
            if self.user_id is not None:
                problems.append("tenant items are not user-mode")
        elif self.eval_tenants:
            problems.append("eval_tenants is only for the tenant bucket")
        if self.gold_sql is not None:
            uses_user = f":{USER_PARAM}" in self.gold_sql
            if uses_user != (self.user_id is not None):
                problems.append("gold uses :user_id exactly for user-mode items")
        if problems:
            raise ValueError(f"{self.id}: " + "; ".join(problems))
        return self


class FewShotItem(_Identified):
    question: str
    sql: str
    """Production-mode SQL over the visible schema, without tenant filters (scoping adds them)."""
    difficulty: Difficulty
    provenance: Provenance


def load_saas_eval(
    path: Path = EVAL_PATH, *, split: Literal["dev", "test", "all"] = "all"
) -> list[SaasEvalItem]:
    items = _load(path, SaasEvalItem)
    return items if split == "all" else [i for i in items if i.split == split]


def load_fewshot_pool(path: Path = FEWSHOT_PATH) -> list[FewShotItem]:
    return _load(path, FewShotItem)


def write_jsonl(path: Path, items: Iterable[BaseModel]) -> None:
    lines = [json.dumps(i.model_dump(mode="json"), ensure_ascii=False) for i in items]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _load[T: _Identified](path: Path, model: type[T]) -> list[T]:
    items: list[T] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                items.append(model.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    _check_unique([i.id for i in items], path)
    return items


def _check_unique(ids: Sequence[str], path: Path) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise ValueError(f"{path}: duplicate id {item_id!r}")
        seen.add(item_id)
