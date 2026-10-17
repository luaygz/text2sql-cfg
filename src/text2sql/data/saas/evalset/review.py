"""Stage 3: independent review by a second model (structured verdicts).

The reviewer is a different model from the drafter. It sees the schema with its notes, the
question, the gold SQL and the gold result for every tenant the item runs under, and answers a
fixed set of yes/no checks. The JSON payload is built with a fixed key order, so the request (and
its cache key) is stable across runs.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Final

from pydantic import BaseModel

from text2sql.config import ReasoningEffort
from text2sql.data.saas.evalset.drafting import Draft
from text2sql.data.saas.evalset.models import Difficulty
from text2sql.execution import QueryResult
from text2sql.llm import LLMClient, Message, Structured
from text2sql.prompts import PromptTemplate, load_prompt

PROMPT_NAME: Final = "saas_review"
PREVIEW_ROWS: Final = 10
_CELL_CHARS: Final = 200


class GoldVerdict(BaseModel):
    question_unambiguous: bool
    sql_answers_question: bool
    difficulty_label_correct: bool
    suggested_difficulty: Difficulty
    problems: str

    @property
    def passed(self) -> bool:
        return self.question_unambiguous and self.sql_answers_question


class UnanswerableVerdict(BaseModel):
    unanswerable: bool
    explanation_correct: bool
    plausible: bool
    difficulty_label_correct: bool
    suggested_difficulty: Difficulty
    problems: str

    @property
    def passed(self) -> bool:
        return self.unanswerable and self.explanation_correct and self.plausible


class AttackVerdict(BaseModel):
    attack_present: bool
    realistic: bool
    legit_question_faithful: bool
    difficulty_label_correct: bool
    suggested_difficulty: Difficulty
    problems: str

    @property
    def passed(self) -> bool:
        return self.attack_present and self.realistic and self.legit_question_faithful


type Verdict = GoldVerdict | UnanswerableVerdict | AttackVerdict


class Reviewer:
    def __init__(
        self, llm: LLMClient, *, schema_text: str, model: str, effort: ReasoningEffort
    ) -> None:
        self._llm = llm
        self._model = model
        self._effort = effort
        self._prompt = load_prompt(PROMPT_NAME)
        self._preamble = Message(
            "developer", self._prompt.render("preamble", schema=schema_text), cache_breakpoint=True
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def prompt(self) -> PromptTemplate:
        return self._prompt

    async def gold(
        self,
        draft: Draft,
        *,
        sql: str,
        results: Sequence[tuple[int, QueryResult]],
        production: bool = False,
        sample: int = 0,
    ) -> Structured[GoldVerdict]:
        """Review an answer item. `production`: the SQL is few-shot SQL without explicit
        tenant filters, which the product adds. Planted-row items carry the generator's
        guarantee that their newest row is unique, which the reviewer cannot see in a preview."""
        payload: dict[str, Any] = {
            "question": draft.gold_question or draft.question,
            "difficulty": draft.difficulty,
            "mode": _mode(draft),
            "sql_style": (
                "production: no tenant filter, the product adds it"
                if production
                else "gold: explicit :tenant_id filters"
            ),
            "sql": sql,
            "results": [_preview(tenant, result) for tenant, result in results],
        }
        if draft.planted_text is not None:
            payload["facts"] = self._prompt.render("planted_fact")
        return await self._call("gold", payload, GoldVerdict, sample)

    async def unanswerable(
        self, draft: Draft, *, probe: str, sample: int = 0
    ) -> Structured[UnanswerableVerdict]:
        payload = {
            "question": draft.question,
            "difficulty": draft.difficulty,
            "explanation": draft.explanation,
            "probe": probe,
        }
        return await self._call("unanswerable", payload, UnanswerableVerdict, sample)

    async def attack(self, draft: Draft, *, sample: int = 0) -> Structured[AttackVerdict]:
        assert draft.attack is not None
        payload = {
            "question": draft.question,
            "category": draft.attack.category,
            "technique": draft.attack.technique,
            "target_tenant_id": draft.attack.target_tenant_id,
            "asking_tenant_id": draft.tenant_id,
            "legit_question": draft.gold_question,
            "difficulty": draft.difficulty,
            "notes": draft.attack.notes,
        }
        return await self._call("adversarial", payload, AttackVerdict, sample)

    async def _call[T: BaseModel](
        self, kind: str, payload: dict[str, Any], output: type[T], sample: int
    ) -> Structured[T]:
        messages = [
            self._preamble,
            Message("developer", self._prompt.render(kind)),
            Message("user", json.dumps(payload, ensure_ascii=False, default=str)),
        ]
        return await self._llm.structured(
            model=self._model,
            messages=messages,
            output=output,
            effort=self._effort,
            purpose=f"saas_evalset.review.{kind}",
            sample=sample,
        )


def _mode(draft: Draft) -> str:
    if draft.persona is None:
        return "tenant: asked by an organisation"
    return f"user: asked by the signed-in user {draft.persona.full_name} ({draft.persona.role})"


def _preview(tenant_id: int, result: QueryResult) -> dict[str, Any]:
    rows = [[_cell(v) for v in row] for row in result.rows[:PREVIEW_ROWS]]
    return {
        "tenant_id": tenant_id,
        "columns": list(result.columns),
        "row_count": len(result.rows),
        "first_rows": rows,
    }


def _cell(value: object) -> object:
    if isinstance(value, str) and len(value) > _CELL_CHARS:
        return value[:_CELL_CHARS] + "..."
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return value
