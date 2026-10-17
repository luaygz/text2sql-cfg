"""Pairwise LLM judge over cluster representatives (CHASE-SQL Algorithm 3, prompted).

Every ordered pair of representatives is one call, so each unordered pair is asked twice with
the presentation order swapped and position bias cancels. Nothing is shuffled, which keeps
every request, and so the response cache, deterministic. A representative's score is its
number of pairwise wins; ties follow `vote.choose` (larger cluster first).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field

from text2sql.catalog import Catalog
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import ReasoningEffort
from text2sql.llm import CallMeta, LLMClient, Message, StructuredCallFailed
from text2sql.prompts import PromptTemplate, load_prompt
from text2sql.selection.clustering import Cluster, ExecutedCandidate
from text2sql.selection.rendering import evidence_text, render_result, schema_for
from text2sql.selection.vote import Selection, choose

PROMPT_NAME = "judge_pairwise"
METHOD = "judge"

log = structlog.get_logger(__name__)


class PairwiseVerdict(BaseModel):
    """Structured output of one comparison. The reason comes first so it is written before the
    choice."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(description="One sentence naming the decisive difference.")
    winner: Literal["A", "B"]


@dataclass(frozen=True)
class _Outcome:
    winner: int | None
    meta: CallMeta
    note: str


async def judge_select(
    llm: LLMClient,
    cands: Sequence[ExecutedCandidate],
    clusters: Sequence[Cluster],
    *,
    question: str,
    evidence: str | None,
    schema_text: str,
    model: str,
    effort: ReasoningEffort,
    catalog: Catalog | None = None,
    schema: DatabaseSchema | None = None,
    strategy_rank: Mapping[str, int] | None = None,
) -> Selection:
    """Round-robin of pairwise comparisons, both orders per pair: m(m-1) calls for m clusters,
    none when there are fewer than two.

    Each prompt shows the union of the schema elements the two queries read (rendered from
    `catalog` against `schema`), or `schema_text` when there is no catalog or extraction fails.
    A comparison whose call fails structurally awards no win; its cost is still returned.
    """
    reps = [cluster.representative for cluster in clusters]
    if len(reps) < 2:
        return choose(
            cands, clusters, dict.fromkeys(reps, 0.0), method=METHOD, strategy_rank=strategy_rank
        )
    by_index = {c.index: c for c in cands}
    template = load_prompt(PROMPT_NAME)
    schemas = {
        frozenset(pair): schema_for(
            [by_index[i].sql for i in pair], fallback=schema_text, catalog=catalog, schema=schema
        )
        for pair in combinations(reps, 2)
    }
    pairs = list(permutations(reps, 2))
    outcomes = await asyncio.gather(
        *(
            _compare(
                llm,
                template,
                by_index[a],
                by_index[b],
                question=question,
                evidence=evidence,
                schema_text=schemas[frozenset((a, b))],
                model=model,
                effort=effort,
            )
            for a, b in pairs
        )
    )
    wins = dict.fromkeys(reps, 0.0)
    for outcome in outcomes:
        if outcome.winner is not None:
            wins[outcome.winner] += 1
    return choose(
        cands,
        clusters,
        wins,
        method=METHOD,
        strategy_rank=strategy_rank,
        calls=[o.meta for o in outcomes],
        notes=[o.note for o in outcomes],
    )


async def _compare(
    llm: LLMClient,
    template: PromptTemplate,
    a: ExecutedCandidate,
    b: ExecutedCandidate,
    *,
    question: str,
    evidence: str | None,
    schema_text: str,
    model: str,
    effort: ReasoningEffort,
) -> _Outcome:
    case = template.render(
        "case",
        schema=schema_text,
        question=question,
        evidence=evidence_text(evidence),
        sql_a=a.sql,
        result_a=render_result(a),
        sql_b=b.sql,
        result_b=render_result(b),
    )
    messages = [
        Message("developer", template.render("instructions")),
        Message("user", case),
    ]
    label = f"A=#{a.index} B=#{b.index}"
    try:
        result = await llm.structured(
            model=model,
            messages=messages,
            output=PairwiseVerdict,
            effort=effort,
            purpose=f"selection.judge/{template.tag}",
        )
    except StructuredCallFailed as exc:
        log.warning("selection.judge_failed", pair=label, reason=exc.reason)
        return _Outcome(winner=None, meta=exc.meta, note=f"{label}: no verdict ({exc.reason})")
    verdict = result.value
    winner = a if verdict.winner == "A" else b
    return _Outcome(
        winner=winner.index,
        meta=result.meta,
        note=f"{label}: #{winner.index} wins: {verdict.reason}",
    )
