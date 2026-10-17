"""Evaluation runner: send one dataset split through the pipeline, score it and write the report.

`run_eval` is the entry point behind `text2sql eval` and `make eval`, in three steps:

- `plan_run` fixes the questions (a seeded sample under `--limit`) and the configuration: a
  preset plus `--set` overrides. Running the held-out test split, or `all`, which contains it,
  needs `allow_test=True` and is appended to `runs/held_out_runs.jsonl` before anything runs.
- `execute_plan` asks and scores questions concurrently under a semaphore, against one
  `RunBudget`. When the budget refuses a call, no new question starts, the ones in flight
  finish, and the run is marked partial with the reason. Failures are then labelled by the
  taxonomy classifier, through the same client and budget.
- `finish_run` writes the report directory and regenerates RESULTS.md.

Every model call goes through the response cache, so `offline=True` replays a recorded run
without an API key; `text2sql.evals.reproduce` uses the same `execute_plan` to check that
committed reports still come out identical.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Protocol, Self

import structlog

from text2sql.config import (
    PRESETS,
    PipelineConfig,
    ReasoningEffort,
    Settings,
    apply_overrides,
    get_settings,
)
from text2sql.data.saas import saas_scope_policy
from text2sql.evals.datasets import (
    SAMPLE_SEED,
    EvalItem,
    SaasItem,
    load_items,
    query_mode,
    sample_items,
)
from text2sql.evals.records import (
    Dataset,
    JsonScalar,
    QuestionRecord,
    RunRecord,
    SpendSummary,
    Split,
)
from text2sql.evals.report import (
    REPORTS_DIR,
    RESULTS_MD,
    current_git_sha,
    regenerate_results_md,
    write_report,
)
from text2sql.evals.scoring import (
    AttackJudge,
    RunContext,
    SchemaResources,
    TraceView,
    score_bird,
    score_saas,
)
from text2sql.evals.taxonomy import label_failures
from text2sql.generation import STRATEGIES
from text2sql.llm import BudgetExceeded, LLMClient, RunBudget, RunSpend
from text2sql.observability import start_run
from text2sql.pipeline import Answer, DatabaseResources, Pipeline, Request
from text2sql.pipeline import Dataset as DatabaseKind
from text2sql.safety.leaks import LeakDetector, judge_attack

log = structlog.get_logger(__name__)

RECORD_KEYS = {"generator_effort": "effort"}
"""Pipeline settings that `RunRecord` (and so RESULTS.md's sweep detection) names differently."""


class HeldOutSplitError(PermissionError):
    """The test split was requested without `allow_test`."""


class RunAbortedError(RuntimeError):
    """The run stopped before any question was scored, so there is nothing to report."""


@dataclass(frozen=True)
class RunPlan:
    dataset: Dataset
    split: Split
    preset: str
    config: PipelineConfig
    overrides: Mapping[str, JsonScalar]
    """Settings changed on top of the preset, in `RunRecord` spelling and typed."""
    with_evidence: bool
    items: Sequence[EvalItem]
    limit: int | None = None
    concurrency: int = 8

    @property
    def context(self) -> RunContext:
        return RunContext(self.dataset, self.split, self.with_evidence)


@dataclass(frozen=True)
class RunOutcome:
    questions: list[QuestionRecord]
    """Scored questions in dataset order; fewer than planned when the run stopped early."""
    stop_reason: str | None


class EvalSystem(Protocol):
    """What a run evaluates: the pipeline, plus the per-database facts that scoring needs."""

    async def ask(self, request: Request) -> tuple[Answer, TraceView]: ...
    def resources(self, db_id: str) -> SchemaResources: ...
    @property
    def judge(self) -> AttackJudge | None: ...
    def close(self) -> None: ...


type SystemFactory = Callable[[LLMClient, RunPlan, Settings], EvalSystem]


class PipelineSystem:
    """The real pipeline over preloaded databases; SaaS runs also get the leak judge."""

    def __init__(
        self,
        pipeline: Pipeline,
        resources: Mapping[str, DatabaseResources],
        judge: AttackJudge | None,
    ) -> None:
        self._pipeline = pipeline
        self._resources = resources
        self._judge = judge

    @classmethod
    def open(cls, llm: LLMClient, plan: RunPlan, settings: Settings) -> Self:
        kind: DatabaseKind = "saas" if plan.dataset == "saas" else "bird"
        mode = query_mode(plan.dataset)
        resources = {
            db_id: DatabaseResources.load(db_id, dataset=kind, mode=mode, evaluation=True)
            for db_id in sorted({item.db_id for item in plan.items})
        }
        judge: AttackJudge | None = None
        if plan.dataset == "saas":
            (saas,) = resources.values()
            detector = LeakDetector.from_database(saas.db_path, saas.policy or saas_scope_policy())
            judge = partial(judge_attack, detector)
        pipeline = Pipeline(llm, plan.config, settings=settings, resources=resources.values())
        return cls(pipeline, resources, judge)

    async def ask(self, request: Request) -> tuple[Answer, TraceView]:
        return await self._pipeline.run(request)

    def resources(self, db_id: str) -> SchemaResources:
        return self._resources[db_id]

    @property
    def judge(self) -> AttackJudge | None:
        return self._judge

    def close(self) -> None:
        self._pipeline.close()
        for resources in self._resources.values():
            resources.close()


def plan_run(
    *,
    dataset: Dataset,
    split: Split,
    preset: str,
    overrides: Mapping[str, str] | None = None,
    limit: int | None = None,
    with_evidence: bool = True,
    allow_test: bool = False,
    concurrency: int = 8,
) -> RunPlan:
    if split != "dev" and not allow_test:
        raise HeldOutSplitError(
            f"split {split!r} includes the held-out test questions; the protocol allows one "
            "test run, after the last dev round. Pass allow_test (--allow-test) to run it."
        )
    if concurrency < 1:
        raise ValueError(f"concurrency must be positive, got {concurrency}")
    with_evidence = with_evidence and dataset != "saas"
    config, recorded = configure(preset, overrides or {}, with_evidence=with_evidence)
    return RunPlan(
        dataset=dataset,
        split=split,
        preset=preset,
        config=config,
        overrides=recorded,
        with_evidence=with_evidence,
        items=sample_items(load_items(dataset, split), limit),
        limit=limit,
        concurrency=concurrency,
    )


def configure(
    preset: str, overrides: Mapping[str, str], *, with_evidence: bool
) -> tuple[PipelineConfig, dict[str, JsonScalar]]:
    """The preset with `overrides` applied, and the overrides as `RunRecord` records them:
    typed, and with RESULTS.md's names (`generator_effort` is the effort sweep's `effort`)."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; known: {', '.join(sorted(PRESETS))}")
    if "use_evidence" in overrides:
        raise ValueError("evidence is a run setting, not an override: use with_evidence")
    config = apply_overrides(PRESETS[preset], overrides)
    config = config.model_copy(update={"use_evidence": with_evidence})
    recorded = {RECORD_KEYS.get(k, k): _json_scalar(getattr(config, k)) for k in overrides}
    return config, recorded


async def execute_plan(
    plan: RunPlan,
    *,
    llm: LLMClient,
    settings: Settings,
    open_system: SystemFactory = PipelineSystem.open,
    label: Callable[[QuestionRecord], bool] = lambda _: True,
) -> RunOutcome:
    """Ask and score every planned question, then label the failures `label` selects."""
    system = open_system(llm, plan, settings)
    try:
        questions, stop_reason = await _ask_all(plan, system)
    finally:
        system.close()
    return RunOutcome(await _label(llm, questions, label), stop_reason)


async def _ask_all(plan: RunPlan, system: EvalSystem) -> tuple[list[QuestionRecord], str | None]:
    gate = asyncio.Semaphore(plan.concurrency)
    stop_reasons: list[str] = []

    async def one(item: EvalItem) -> QuestionRecord | None:
        async with gate:
            if stop_reasons:
                return None
            try:
                record = await score_item(item, system, plan.context)
            except BudgetExceeded as exc:
                stop_reasons.append(f"budget exceeded: {exc}")
                log.warning("eval.stopped", question_id=item.question_id, reason=str(exc))
                return None
        log.info(
            "eval.question",
            question_id=record.question_id,
            correct=record.correct,
            cost_usd=record.cost_usd,
        )
        return record

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(one(item)) for item in plan.items]
    except ExceptionGroup as failed:
        raise failed.exceptions[0] from failed
    questions = [q for task in tasks if (q := task.result()) is not None]
    return questions, stop_reasons[0] if stop_reasons else None


async def score_item(item: EvalItem, system: EvalSystem, run: RunContext) -> QuestionRecord:
    resources = system.resources(item.db_id)
    if isinstance(item, SaasItem):
        if system.judge is None:
            raise ValueError("SaaS items need an attack judge")
        return await score_saas(item, system.ask, resources, run, system.judge)
    return await score_bird(item, system.ask, resources, run)


async def _label(
    llm: LLMClient, questions: list[QuestionRecord], wanted: Callable[[QuestionRecord], bool]
) -> list[QuestionRecord]:
    picked = [i for i, q in enumerate(questions) if not q.correct and wanted(q)]
    try:
        labelled = await label_failures(llm, [questions[i] for i in picked])
    except BudgetExceeded as exc:
        log.warning("eval.unlabelled", failures=len(picked), reason=str(exc))
        return questions
    out = list(questions)
    for i, record in zip(picked, labelled, strict=True):
        out[i] = record
    return out


def finish_run(
    plan: RunPlan,
    outcome: RunOutcome,
    *,
    run_id: str,
    started: datetime,
    spend: RunSpend,
    settings: Settings,
    reports_dir: Path = REPORTS_DIR,
    results_md: Path = RESULTS_MD,
    git_sha: str | None = None,
) -> Path:
    """Write the run's report directory, regenerate RESULTS.md and return the directory.

    `git_sha` is the commit the run started at (taken now when not given). If HEAD has moved
    since, the code may have changed under the run, so the SHA is recorded as `-dirty`.
    """
    if not outcome.questions:
        raise RunAbortedError(f"no question was scored: {outcome.stop_reason or 'empty plan'}")
    run = RunRecord(
        run_id=run_id,
        git_sha=_run_sha(git_sha),
        timestamp=started,
        config_name=plan.preset,
        config=run_config(plan, settings),
        overrides=dict(plan.overrides),
        n_candidates=plan.config.n_candidates,
        effort=generator_effort(plan.config),
        dataset=plan.dataset,
        split=plan.split,
        with_evidence=plan.with_evidence,
        questions_planned=len(plan.items),
        partial=outcome.stop_reason is not None,
        partial_reason=outcome.stop_reason,
        spend=spend_summary(spend),
    )
    directory = write_report(run, outcome.questions, reports_dir=reports_dir)
    regenerate_results_md(reports_dir=reports_dir, output=results_md)
    return directory


def run_config(plan: RunPlan, settings: Settings) -> dict[str, object]:
    """What `RunRecord.config` stores: enough to replay the run with `reproduce`."""
    return {
        "pipeline": plan.config.model_dump(mode="json"),
        "generator_model": settings.generator_model,
        "small_model": settings.small_model,
        "embedding_model": settings.embedding_model,
        "small_effort": settings.small_effort,
        "service_tier": settings.service_tier,
        "limit": plan.limit,
        "sample_seed": SAMPLE_SEED,
    }


def generator_effort(config: PipelineConfig) -> ReasoningEffort:
    """The override if set, else the effort of the first generator-tier strategy scheduled."""
    if config.generator_effort is not None:
        return config.generator_effort
    specs = [STRATEGIES[name] for name in config.strategies]
    chosen = next((s for s in specs if s.model_tier == "generator"), specs[0])
    return chosen.effort


def spend_summary(spend: RunSpend) -> SpendSummary:
    models = spend.by_model.values()
    return SpendSummary(
        billed_usd=spend.cost_usd,
        priced_usd=spend.cost_usd + sum(m.priced_cache_hits_usd for m in models),
        budget_usd=spend.run_cap_usd,
        calls=sum(m.api_calls + m.cache_hits for m in models),
        cache_hits=sum(m.cache_hits for m in models),
        input_tokens=sum(m.input_tokens for m in models),
        cached_tokens=sum(m.cached_tokens for m in models),
        output_tokens=sum(m.output_tokens for m in models),
        reasoning_tokens=sum(m.reasoning_tokens for m in models),
    )


def record_held_out_run(settings: Settings, run_id: str, plan: RunPlan, started: datetime) -> None:
    """Append a test-split run to runs/held_out_runs.jsonl, before it starts, so that even an
    aborted run that never writes a report leaves a trace."""
    entry = {
        "run_id": run_id,
        "timestamp": started.isoformat(),
        "git_sha": current_git_sha(),
        "dataset": plan.dataset,
        "split": plan.split,
        "preset": plan.preset,
        "overrides": dict(plan.overrides),
        "with_evidence": plan.with_evidence,
        "questions": len(plan.items),
    }
    path = settings.runs_dir / "held_out_runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


async def run_eval(
    *,
    dataset: Dataset,
    split: Split,
    preset: str,
    overrides: Mapping[str, str] | None = None,
    limit: int | None = None,
    with_evidence: bool = True,
    offline: bool = False,
    allow_test: bool = False,
    concurrency: int = 8,
) -> Path:
    """Evaluate `preset` (plus `overrides`) on a dataset split; return the report directory.

    Prints the run's spend when it ends, also when it fails. Raises HeldOutSplitError for the
    test split without `allow_test`, CacheMiss offline when a response was never recorded, and
    RunAbortedError when the budget stopped the run before the first question finished.
    """
    plan = plan_run(
        dataset=dataset,
        split=split,
        preset=preset,
        overrides=overrides,
        limit=limit,
        with_evidence=with_evidence,
        allow_test=allow_test,
        concurrency=concurrency,
    )
    base = get_settings()
    # The flag can switch replay on, never off: OFFLINE=true in the environment still holds.
    settings = base.model_copy(update={"offline": offline or base.offline})
    run_id = start_run()
    started = datetime.now(UTC)
    start_sha = current_git_sha()
    if plan.split != "dev":
        record_held_out_run(settings, run_id, plan, started)
    budget = RunBudget.from_settings(settings, run_id=run_id)
    try:
        async with LLMClient(settings, budget=budget) as llm:
            outcome = await execute_plan(plan, llm=llm, settings=settings)
    finally:
        print(budget.summary().render())
    if outcome.stop_reason is not None:
        print(
            f"partial run: {len(outcome.questions)}/{len(plan.items)} questions; "
            f"{outcome.stop_reason}"
        )
    return finish_run(
        plan,
        outcome,
        run_id=run_id,
        started=started,
        spend=budget.summary(),
        settings=settings,
        git_sha=start_sha,
    )


def _run_sha(start_sha: str | None) -> str:
    """The commit a run started at, marked `-dirty` if HEAD moved before it finished."""
    end_sha = current_git_sha()
    if start_sha is None or start_sha == end_sha:
        return end_sha
    print(f"warning: HEAD moved during the run ({start_sha[:7]} -> {end_sha[:7]})")
    return start_sha if start_sha.endswith("-dirty") else f"{start_sha}-dirty"


def _json_scalar(value: object) -> JsonScalar:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, tuple | list):
        return ",".join(str(v) for v in value)
    raise TypeError(f"cannot record override value {value!r}")
