"""Decisions after the candidates ran: cheap-path exit, abstain or clarify, and selection.

Abstain and clarify exist only where the grammar admits `ABSTAIN:` (production and tenant
modes); benchmark runs always pick a query when one executed. The clarify threshold (no result
shared by more than a third of the executed candidates) is a starting point to tune on the SaaS
dev questions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from text2sql.catalog import Catalog
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import PipelineConfig, Settings
from text2sql.llm import LLMClient
from text2sql.pipeline.types import CandidateTrace
from text2sql.retrieval import QuestionAnalysis
from text2sql.selection import (
    Cluster,
    ExecutedCandidate,
    Selection,
    cluster_candidates,
    judge_select,
    majority_vote,
    unit_test_select,
)

CHEAP_PATH_STRATEGIES = ("small_linked", "direct_full")
CLARIFY_MAX_SHARE = 1 / 3
"""Ask to clarify when no result is shared by more than this share of executed candidates."""


@dataclass(frozen=True, slots=True)
class Verdict:
    status: Literal["abstained", "clarify"]
    reason: str
    confidence: float


def executed_candidates(candidates: Sequence[CandidateTrace]) -> list[ExecutedCandidate]:
    """The candidates selection may choose from: executed, empty results included."""
    out: list[ExecutedCandidate] = []
    for c in candidates:
        if c.guarded is not None:
            out.append(
                ExecutedCandidate.from_result(
                    index=c.index, strategy=c.strategy, sql=c.guarded.sql, result=c.guarded.result
                )
            )
    return out


def cheap_path_exit(
    cheap: Sequence[CandidateTrace], analysis: QuestionAnalysis | None
) -> tuple[bool, str]:
    """Whether the two cheap candidates settle the question, and why (not)."""
    if analysis is None:
        return False, "no question analysis"
    if analysis.complexity != "easy":
        return False, f"question is {analysis.complexity}"
    if any(c.status != "ok" or c.repairs for c in cheap):
        return False, "a cheap candidate did not execute cleanly with rows"
    if len(cluster_candidates(executed_candidates(cheap))) != 1:
        return False, "the cheap candidates disagree"
    return True, "both cheap candidates agree on an easy question"


def abstain_or_clarify(
    candidates: Sequence[CandidateTrace], clusters: Sequence[Cluster], *, allow_abstain: bool
) -> Verdict | None:
    """Abstain when most candidates abstain (or abstentions are all there is); clarify when
    the executed candidates scatter over results with no clear plurality."""
    if not allow_abstain:
        return None
    produced = [c for c in candidates if c.status != "grammar_failed"]
    abstained = [c for c in produced if c.status == "abstained"]
    executed = sum(len(c.members) for c in clusters)
    if abstained and (2 * len(abstained) > len(produced) or executed == 0):
        # Most common reason; ties go to the earliest candidate in schedule order.
        reason, _ = Counter(c.abstain_reason or "" for c in abstained).most_common(1)[0]
        return Verdict("abstained", reason or "unanswerable", len(abstained) / len(produced))
    if len(clusters) > 1:
        top = max(len(c.members) for c in clusters)
        if top / executed <= CLARIFY_MAX_SHARE:
            return Verdict(
                "clarify",
                f"{executed} candidate queries returned {len(clusters)} different results",
                top / executed,
            )
    return None


def first_selection(
    executed: Sequence[ExecutedCandidate], clusters: Sequence[Cluster]
) -> Selection:
    """The earliest executed candidate in schedule order (the baseline's selector)."""
    chosen = min(c.index for c in executed)
    cluster = next(c for c in clusters if chosen in c.members)
    return Selection(
        index=chosen,
        method="first",
        vote_share=len(cluster.members) / len(executed),
        n_clusters=len(clusters),
        scores={},
        calls=(),
    )


async def select(
    llm: LLMClient,
    settings: Settings,
    config: PipelineConfig,
    executed: Sequence[ExecutedCandidate],
    clusters: Sequence[Cluster],
    *,
    question: str,
    evidence: str | None,
    schema_text: str,
    catalog: Catalog,
    schema: DatabaseSchema,
    strategy_rank: Mapping[str, int],
    prefer_non_empty: bool,
) -> Selection:
    """Apply the configured selector; the judge and unit tests only run when the vote is split
    and its winner holds less than `config.judge_threshold` of the votes."""
    if config.selector == "first":
        return first_selection(executed, clusters)
    vote = majority_vote(
        executed, clusters, strategy_rank=strategy_rank, prefer_non_empty=prefer_non_empty
    )
    if config.selector == "vote" or len(clusters) < 2 or vote.vote_share >= config.judge_threshold:
        return vote
    if config.selector == "judge":
        return await judge_select(
            llm,
            executed,
            clusters,
            question=question,
            evidence=evidence,
            schema_text=schema_text,
            model=settings.generator_model,
            effort=settings.generator_effort,
            catalog=catalog,
            schema=schema,
            strategy_rank=strategy_rank,
        )
    return await unit_test_select(
        llm,
        executed,
        clusters,
        question=question,
        evidence=evidence,
        schema_text=schema_text,
        writer_model=settings.generator_model,
        checker_model=settings.small_model,
        effort=settings.generator_effort,
        catalog=catalog,
        schema=schema,
        strategy_rank=strategy_rank,
    )
