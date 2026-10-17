"""Unit-test selection (CHESS v3 Unit Tester).

One writer call sees every cluster and writes natural-language tests meant to separate them;
CHESS's fixed "only the best answer passes" test is always added. Then one checker call per
test judges all cluster representatives at once (CHESS found one-test-all-candidates better than
all-tests-one-candidate). A representative's score is the number of tests it passed; ties follow
`vote.choose` (larger cluster first). Candidates are shown in cluster order, largest first, with
no shuffling, so every request is deterministic and cacheable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, ConfigDict

from text2sql.catalog import Catalog
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import ReasoningEffort
from text2sql.llm import CallMeta, LLMClient, Message, StructuredCallFailed
from text2sql.prompts import PromptTemplate, load_prompt
from text2sql.selection.clustering import Cluster, ExecutedCandidate
from text2sql.selection.rendering import evidence_text, render_result, schema_for
from text2sql.selection.vote import Selection, choose

WRITER_PROMPT = "unit_tests_write"
CHECKER_PROMPT = "unit_tests_check"
METHOD = "unit_test"

log = structlog.get_logger(__name__)


class UnitTests(BaseModel):
    """Structured output of the writer call."""

    model_config = ConfigDict(extra="forbid")

    tests: list[str]


class CandidateVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: int
    passed: bool


class UnitTestVerdicts(BaseModel):
    """Structured output of one checker call: a verdict per candidate number shown."""

    model_config = ConfigDict(extra="forbid")

    verdicts: list[CandidateVerdict]


@dataclass(frozen=True)
class _Check:
    passed: frozenset[int]
    meta: CallMeta
    note: str


async def unit_test_select(
    llm: LLMClient,
    cands: Sequence[ExecutedCandidate],
    clusters: Sequence[Cluster],
    *,
    question: str,
    evidence: str | None,
    schema_text: str,
    writer_model: str,
    checker_model: str,
    effort: ReasoningEffort,
    n_tests: int = 3,
    catalog: Catalog | None = None,
    schema: DatabaseSchema | None = None,
    strategy_rank: Mapping[str, int] | None = None,
) -> Selection:
    """Write up to `n_tests` tests, add the fixed one, check each against every representative:
    at most n_tests + 2 calls for two or more clusters (no writer call when `n_tests` is 0),
    none otherwise.

    Prompts show the union of the schema elements the representatives read (rendered from
    `catalog` against `schema`), or `schema_text` when there is no catalog or extraction fails.
    A failed writer call leaves only the fixed test; a failed checker call passes nobody. Every
    call's cost is returned either way.
    """
    if n_tests < 0:
        raise ValueError(f"n_tests must be >= 0, got {n_tests}")
    reps = [cluster.representative for cluster in clusters]
    if len(reps) < 2:
        return choose(
            cands, clusters, dict.fromkeys(reps, 0.0), method=METHOD, strategy_rank=strategy_rank
        )
    by_index = {c.index: c for c in cands}
    shown = [by_index[i] for i in reps]
    writer = load_prompt(WRITER_PROMPT)
    checker = load_prompt(CHECKER_PROMPT)
    context = {
        "schema": schema_for(
            [c.sql for c in shown], fallback=schema_text, catalog=catalog, schema=schema
        ),
        "question": question,
        "evidence": evidence_text(evidence),
    }
    calls: list[CallMeta] = []
    tests: list[str] = []
    if n_tests > 0:
        written, meta = await _write_tests(
            llm,
            writer,
            clusters,
            shown,
            context,
            n_tests=n_tests,
            model=writer_model,
            effort=effort,
        )
        calls.append(meta)
        tests.extend(written)
    tests.append(checker.render("best_answer_test"))
    checks = await asyncio.gather(
        *(
            _check(llm, checker, shown, context, test, model=checker_model, effort=effort)
            for test in tests
        )
    )
    passed = dict.fromkeys(reps, 0.0)
    for check in checks:
        for index in check.passed:
            passed[index] += 1
    return choose(
        cands,
        clusters,
        passed,
        method=METHOD,
        strategy_rank=strategy_rank,
        calls=[*calls, *(c.meta for c in checks)],
        notes=[c.note for c in checks],
    )


async def _write_tests(
    llm: LLMClient,
    template: PromptTemplate,
    clusters: Sequence[Cluster],
    shown: Sequence[ExecutedCandidate],
    context: Mapping[str, str],
    *,
    n_tests: int,
    model: str,
    effort: ReasoningEffort,
) -> tuple[list[str], CallMeta]:
    blocks = "\n".join(
        template.render(
            "cluster",
            number=str(number),
            size=str(len(cluster.members)),
            sql=cand.sql,
            result=render_result(cand),
        )
        for number, (cluster, cand) in enumerate(zip(clusters, shown, strict=True), start=1)
    )
    messages = [
        Message("developer", template.render("instructions", n_tests=str(n_tests))),
        Message("user", template.render("case", clusters=blocks, **context)),
    ]
    try:
        result = await llm.structured(
            model=model,
            messages=messages,
            output=UnitTests,
            effort=effort,
            purpose=f"selection.unit_test.write/{template.tag}",
        )
    except StructuredCallFailed as exc:
        log.warning("selection.unit_test_write_failed", reason=exc.reason)
        return [], exc.meta
    tests = [t.strip() for t in result.value.tests if t.strip()]
    return tests[:n_tests], result.meta


async def _check(
    llm: LLMClient,
    template: PromptTemplate,
    shown: Sequence[ExecutedCandidate],
    context: Mapping[str, str],
    test: str,
    *,
    model: str,
    effort: ReasoningEffort,
) -> _Check:
    blocks = "\n".join(
        template.render("candidate", number=str(number), sql=cand.sql, result=render_result(cand))
        for number, cand in enumerate(shown, start=1)
    )
    messages = [
        Message("developer", template.render("instructions")),
        Message("user", template.render("case", candidates=blocks, test=test, **context)),
    ]
    try:
        result = await llm.structured(
            model=model,
            messages=messages,
            output=UnitTestVerdicts,
            effort=effort,
            purpose=f"selection.unit_test.check/{template.tag}",
        )
    except StructuredCallFailed as exc:
        log.warning("selection.unit_test_check_failed", reason=exc.reason)
        return _Check(frozenset(), exc.meta, f"{test} -> no verdicts ({exc.reason})")
    # The first verdict per candidate number counts; numbers that were not shown are ignored.
    verdicts: dict[int, bool] = {}
    for verdict in result.value.verdicts:
        verdicts.setdefault(verdict.candidate, verdict.passed)
    passed = frozenset(
        cand.index for number, cand in enumerate(shown, start=1) if verdicts.get(number, False)
    )
    listed = ", ".join(f"#{i}" for i in sorted(passed)) or "none"
    return _Check(passed, result.meta, f"{test} -> passed: {listed}")
