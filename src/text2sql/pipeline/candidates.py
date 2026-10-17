"""One candidate: generate, pass through the guard, repair, and record every attempt.

Repair triggers (ADR-014): an SQLite error or timeout, a layer-2 (validator) rejection, an empty
result when question analysis says the question expects rows, and, with `literal_check`, a
compared string its column does not hold while close values are stored (`literals.py`). The
literal check wins over the empty-result trigger, since it names a likely cause. Rejections by
the scoping layer or the executor's authorizer are not repaired: they are safety stops, and
feeding them back would let the model probe the guard. A failed grammar call ends the candidate;
nothing is retried as free text.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from text2sql.catalog.schema import DatabaseSchema, quote_identifier
from text2sql.config import PipelineConfig, QueryMode, Settings
from text2sql.execution import ExecutionError, QueryTimeout
from text2sql.generation import (
    GenerationContext,
    RepairKind,
    ScheduledCandidate,
    SchemaView,
    StrategySpec,
    generate_candidate,
    generate_json_candidate,
    model_for,
    prompt_tags,
    repair_candidate,
    repair_feedback,
)
from text2sql.grammar import GrammarOutput
from text2sql.grammar.model import ABSTAIN_PREFIX
from text2sql.llm import CallMeta, GrammarCallFailed, LLMClient, StructuredCallFailed
from text2sql.observability import span
from text2sql.pipeline.literals import literal_mismatches, mismatch_detail, sql_string
from text2sql.pipeline.resources import DatabaseResources
from text2sql.pipeline.types import Attempt, CandidateTrace, Rejection, Request
from text2sql.retrieval import QuestionAnalysis, ValueMatches
from text2sql.safety import SafetyEvent
from text2sql.safety.guard import GuardRejection
from text2sql.selection import has_top_level_order_by, result_fingerprint

MAX_EVENT_DETAIL = 500
"""Same cut as the guard's event details."""
MAX_HINT_COLUMNS = 8
MAX_HINT_VALUES = 5
_HINTED: frozenset[RepairKind] = frozenset({"error", "empty"})
"""Repairs that get value hints: validator feedback is about names, and value feedback already
lists the stored values."""


@dataclass(frozen=True, slots=True)
class CandidateEnv:
    """What every candidate of one request shares."""

    llm: LLMClient
    settings: Settings
    config: PipelineConfig
    resources: DatabaseResources
    request: Request
    context: GenerationContext
    allowed: Mapping[SchemaView, DatabaseSchema | None]
    """Layer-2 allowlist per view: the linked schema for linked grammars, None (visible) else."""
    analysis: QuestionAnalysis | None
    matches: ValueMatches


@dataclass(frozen=True, slots=True)
class _Repair:
    kind: RepairKind
    detail: str


def effective_spec(spec: StrategySpec, config: PipelineConfig) -> StrategySpec:
    """`spec` with the configured generator effort; the small model keeps its own."""
    if config.generator_effort is None or spec.model_tier != "generator":
        return spec
    return spec.model_copy(update={"effort": config.generator_effort})


async def run_candidate(env: CandidateEnv, slot: ScheduledCandidate, index: int) -> CandidateTrace:
    spec = effective_spec(slot.strategy, env.config)
    model = model_for(spec, env.settings)
    trace = CandidateTrace(
        index=index,
        strategy=spec.name,
        model=model,
        effort=spec.effort,
        sample=slot.sample,
        schema_view=spec.schema_view,
        prompt_tags=prompt_tags(spec),
    )
    with span(
        "pipeline.candidate", index=index, strategy=spec.name, sample=slot.sample, model=model
    ) as current:
        if env.config.grammar:
            await _grammar_candidate(env, spec, trace)
        else:
            await _json_candidate(env, spec, trace)
        current.set(status=trace.status, repairs=trace.repairs, cost_usd=trace.cost_usd)
    return trace


async def _grammar_candidate(env: CandidateEnv, spec: StrategySpec, trace: CandidateTrace) -> None:
    try:
        call = await generate_candidate(
            env.llm, spec, env.context, model=trace.model, sample=trace.sample
        )
    except GrammarCallFailed as exc:
        trace.attempts.append(_grammar_failed(env, trace, 0, exc))
        return
    number = 0
    while True:
        attempt, repair = await _check(
            env, trace, number=number, meta=call.meta, output=call.output, kind="grammar"
        )
        if repair is None or not env.config.repair or number >= env.config.max_repairs:
            trace.attempts.append(attempt)
            return
        hints = value_hints(attempt.sql or "", env.matches) if repair.kind in _HINTED else []
        feedback = repair_feedback(kind=repair.kind, detail=repair.detail, value_hints=hints)
        trace.attempts.append(replace(attempt, feedback=feedback, repair_kind=repair.kind))
        number += 1
        try:
            # `call` carries the whole conversation so far, so each repair continues the last.
            call = await repair_candidate(
                env.llm, spec, env.context, call, feedback, model=trace.model, attempt=number
            )
        except GrammarCallFailed as exc:
            trace.attempts.append(_grammar_failed(env, trace, number, exc))
            return


async def _json_candidate(env: CandidateEnv, spec: StrategySpec, trace: CandidateTrace) -> None:
    """The grammar-off ablation: plain JSON output, then guard layers 2-4 (no repair)."""
    try:
        text, meta = await generate_json_candidate(
            env.llm, spec, env.context, model=trace.model, sample=trace.sample
        )
    except StructuredCallFailed as exc:
        trace.attempts.append(
            Attempt(
                0,
                exc.meta,
                "grammar_failed",
                output="json",
                grammar_failure=f"{exc.reason}: {exc.detail}",
            )
        )
        return
    abstains = env.resources.options.allow_abstain and text.startswith(ABSTAIN_PREFIX)
    output = (
        GrammarOutput("abstain", text.removeprefix(ABSTAIN_PREFIX))
        if abstains
        else GrammarOutput("sql", text)
    )
    attempt, _ = await _check(env, trace, number=0, meta=meta, output=output, kind="json")
    trace.attempts.append(attempt)


async def _check(
    env: CandidateEnv,
    trace: CandidateTrace,
    *,
    number: int,
    meta: CallMeta,
    output: GrammarOutput,
    kind: Literal["grammar", "json"],
) -> tuple[Attempt, _Repair | None]:
    """Run one output through the guard; the attempt, and why to repair it (None: don't)."""
    if output.kind == "abstain":
        return Attempt(number, meta, "abstained", kind, abstain_reason=output.text), None
    sql = output.text
    view = trace.schema_view
    started = time.perf_counter()
    try:
        guarded = await env.resources.guard.run(
            sql,
            grammar=env.context.grammars[view] if kind == "grammar" else None,
            allowed=env.allowed[view],
            scope=env.request.scope,
            context=_event_context(env, trace, number),
        )
    except GuardRejection as exc:
        rejected = Attempt(
            number,
            meta,
            "guard_rejected",
            kind,
            sql=sql,
            rejection=Rejection(exc.layer, exc.rule, exc.detail),
            exec_s=time.perf_counter() - started,
        )
        repair = (
            _Repair("validator", f"{exc.rule}: {exc.detail}") if exc.layer == "validator" else None
        )
        return rejected, repair
    except QueryTimeout as exc:
        timeout = env.resources.limits.timeout_s
        failed = Attempt(
            number,
            meta,
            "timeout",
            kind,
            sql=sql,
            exec_error=str(exc),
            exec_s=time.perf_counter() - started,
        )
        return failed, _Repair("error", f"the query did not finish within {timeout:g} s")
    except ExecutionError as exc:
        failed = Attempt(
            number,
            meta,
            "exec_error",
            kind,
            sql=sql,
            exec_error=str(exc),
            exec_s=time.perf_counter() - started,
        )
        return failed, _Repair("error", str(exc))
    ordered = has_top_level_order_by(sql)
    rows = guarded.result.rows
    executed = Attempt(
        number,
        meta,
        "ok" if rows else "empty",
        kind,
        sql=sql,
        guarded=guarded,
        fingerprint=result_fingerprint(rows, ordered=ordered),
        ordered=ordered,
        exec_s=time.perf_counter() - started,
    )
    return executed, await _result_repair(env, trace, number, sql, empty=not rows)


async def _result_repair(
    env: CandidateEnv, trace: CandidateTrace, number: int, sql: str, *, empty: bool
) -> _Repair | None:
    """Why to repair a query that executed: a compared value its column does not hold, else an
    empty result where the analysis expects rows."""
    if _checks_literals(env, number):
        with span("pipeline.literal_check", candidate=trace.index, attempt=number) as current:
            mismatches = await literal_mismatches(
                sql, env.resources.visible_schema, env.resources.db_path, env.matches
            )
            current.set(mismatches=len(mismatches))
        if mismatches:
            return _Repair("value", mismatch_detail(mismatches))
    expects_rows = env.analysis is not None and not env.analysis.may_be_empty
    return _Repair("empty", "") if empty and expects_rows else None


def _checks_literals(env: CandidateEnv, number: int) -> bool:
    """Whether attempt `number` gets the literal check: only when a repair could follow it (the
    lookups cost a table scan per missing literal), and never in tenant mode, where the lookups
    would read other tenants' rows."""
    cfg = env.config
    return (
        cfg.literal_check
        and cfg.repair
        and number < cfg.max_repairs
        and env.resources.mode is not QueryMode.TENANT
    )


def _grammar_failed(
    env: CandidateEnv, trace: CandidateTrace, number: int, exc: GrammarCallFailed
) -> Attempt:
    if exc.reason == "local_parse":
        # The API's tool input did not re-parse under the request grammar: layer 1 stopped it
        # before the guard ever saw it.
        env.resources.event_log.record(
            SafetyEvent(
                "grammar",
                exc.reason,
                exc.detail[:MAX_EVENT_DETAIL],
                sql=exc.raw_input,
                context=_event_context(env, trace, number),
            )
        )
    return Attempt(
        number, exc.meta, "grammar_failed", grammar_failure=f"{exc.reason}: {exc.detail}"
    )


def _event_context(env: CandidateEnv, trace: CandidateTrace, number: int) -> dict[str, str]:
    context = {
        "db_id": env.request.db_id,
        "strategy": trace.strategy,
        "candidate": str(trace.index),
        "attempt": str(number),
    }
    if env.request.question_id is not None:
        context["question_id"] = env.request.question_id
    return context


def value_hints(sql: str, matches: ValueMatches) -> list[str]:
    """Retrieved values of the matched columns the failing query names (ADR-008 stage 7)."""
    lowered = sql.lower()
    hints: list[str] = []
    for (table, column), values in matches.items():
        if not values or column.lower() not in lowered:
            continue
        shown = ", ".join(sql_string(v) for v in values[:MAX_HINT_VALUES])
        hints.append(f"{quote_identifier(table)}.{quote_identifier(column)} has values {shown}")
        if len(hints) == MAX_HINT_COLUMNS:
            break
    return hints


def first_of(slots: Sequence[ScheduledCandidate], strategy: str) -> ScheduledCandidate | None:
    return next((s for s in slots if s.strategy.name == strategy), None)
