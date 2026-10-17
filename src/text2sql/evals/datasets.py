"""Evaluation items for the three result tables: original Mini-Dev, Arcwise-Plat-SQL and SaaS.

Original Mini-Dev gold is scored on the Mini-Dev database package; Arcwise-Plat-SQL gold on the
BIRD Dev release, where Jin et al. checked it (ADR-003). The pipeline itself always runs on the
Mini-Dev package, so an Arcwise item whose question and evidence Arcwise left unchanged sends the
exact request of the original item and replays its responses from the cache at no cost. Only
the 125 reworded items need new calls.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from text2sql.config import QueryMode
from text2sql.data.bird import BirdExample, bird_db_path, load_minidev, load_split
from text2sql.data.saas import DEFAULT_DB_PATH, SAAS_DB_ID
from text2sql.data.saas.evalset import SaasEvalItem, load_saas_eval
from text2sql.evals.records import Dataset, Split

SAMPLE_SEED = 20261016
"""Seed of the `--limit` sample, so a limited run always picks the same questions."""


@dataclass(frozen=True)
class BirdItem:
    question_id: str
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: str
    gold_db: Path
    """Database the gold and the predicted SQL are executed on for scoring."""
    alternate_gold: str | None
    """For an original Mini-Dev item, the Arcwise-Plat-SQL gold: if it returns a different
    result, the original label is suspect."""


@dataclass(frozen=True)
class SaasItem:
    item: SaasEvalItem
    db_path: Path

    @property
    def question_id(self) -> str:
        return self.item.id

    @property
    def db_id(self) -> str:
        return SAAS_DB_ID

    @property
    def tenants(self) -> tuple[int, ...]:
        """Tenants to ask the question for; the requesting tenant first."""
        return tuple(self.item.eval_tenants) or (self.item.tenant_id,)


type EvalItem = BirdItem | SaasItem


def query_mode(dataset: Dataset) -> QueryMode:
    return QueryMode.TENANT if dataset == "saas" else QueryMode.BENCHMARK


def load_items(dataset: Dataset, split: Split) -> list[EvalItem]:
    """Every item of one dataset split, in dataset order."""
    if dataset == "saas":
        return [SaasItem(item, DEFAULT_DB_PATH) for item in load_saas_eval(split=split)]
    examples = load_minidev() if split == "all" else load_split(split)
    if dataset == "bird_minidev":
        return [_original(e) for e in examples]
    return [_arcwise(e) for e in examples if e.has_arcwise]


def _original(example: BirdExample) -> BirdItem:
    return BirdItem(
        question_id=str(example.question_id),
        db_id=example.db_id,
        question=example.question,
        evidence=example.evidence,
        gold_sql=example.gold_sql,
        difficulty=example.difficulty,
        gold_db=bird_db_path(example.db_id, "minidev"),
        alternate_gold=example.gold_sql_arcwise,
    )


def _arcwise(example: BirdExample) -> BirdItem:
    gold, question, evidence = (
        example.gold_sql_arcwise,
        example.question_arcwise,
        example.evidence_arcwise,
    )
    if gold is None or question is None or evidence is None:
        raise ValueError(f"question {example.question_id} has no Arcwise-Plat-SQL label")
    if not example.arcwise_inputs_changed:
        question, evidence = example.question, example.evidence
    return BirdItem(
        question_id=str(example.question_id),
        db_id=example.db_id,
        question=question,
        evidence=evidence,
        gold_sql=gold,
        difficulty=example.difficulty,
        gold_db=bird_db_path(example.db_id, "dev"),
        alternate_gold=None,
    )


def sample_items(items: Sequence[EvalItem], limit: int | None) -> list[EvalItem]:
    """A seeded sample of `limit` items (all of them for None), kept in dataset order."""
    if limit is None or limit >= len(items):
        return list(items)
    if limit < 1:
        raise ValueError(f"limit must be positive, got {limit}")
    picked = sorted(random.Random(SAMPLE_SEED).sample(range(len(items)), limit))
    return [items[i] for i in picked]
