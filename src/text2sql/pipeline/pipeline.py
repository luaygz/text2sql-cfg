"""The text-to-SQL pipeline (ADR-008 and ADR-014).

Stages for one request, each switched by `PipelineConfig`: question analysis, value retrieval,
schema linking, few-shot retrieval, grammars, candidate generation with guarded execution and
repair (optionally behind the cheap path), abstain/clarify, selection, and the answer.

Failures inside a stage degrade the request instead of failing it: a failed structured call
drops that stage's output (recorded in `PipelineTrace.warnings`), a failed grammar call drops
its candidate. `BudgetExceeded` and `CacheMiss` propagate, since a run cannot continue past
them, as does `FileNotFoundError` for a missing catalog or index.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cache

import structlog

from text2sql.catalog import render_matched_values, render_schema
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import PipelineConfig, QueryMode, Settings
from text2sql.data.saas import SAAS_DB_ID
from text2sql.generation import (
    GenerationContext,
    ScheduledCandidate,
    SchemaView,
    model_for,
    schedule,
)
from text2sql.grammar import SqlGrammar, build_grammar
from text2sql.llm import CallMeta, LLMClient, StructuredCallFailed
from text2sql.observability import span
from text2sql.pipeline import answer as answers
from text2sql.pipeline.candidates import CandidateEnv, effective_spec, first_of, run_candidate
from text2sql.pipeline.decide import (
    CHEAP_PATH_STRATEGIES,
    abstain_or_clarify,
    cheap_path_exit,
    executed_candidates,
    select,
)
from text2sql.pipeline.events import (
    EventCallback,
    EventSink,
    EventValue,
    collect_safety_events,
)
from text2sql.pipeline.resources import DatabaseResources, Dataset
from text2sql.pipeline.types import (
    Answer,
    CandidateTrace,
    GrammarInfo,
    PipelineTrace,
    Request,
    StageRecord,
)
from text2sql.retrieval import (
    DEFAULT_ANALYSIS_EFFORT,
    DEFAULT_LINKING_EFFORT,
    FewShotExample,
    FewShotIndex,
    LinkResult,
    QuestionAnalysis,
    ValueMatches,
    analyze_question,
    link_schema,
)
from text2sql.selection import Cluster, Selection, cluster_candidates
from text2sql.selection.judge import METHOD as JUDGE_METHOD
from text2sql.selection.unit_tests import METHOD as UNIT_TEST_METHOD

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class _Stage:
    """Collects one stage's calls and event payload while it runs."""

    calls: list[CallMeta] = field(default_factory=list)
    data: dict[str, EventValue] = field(default_factory=dict)
    critical_path_s: float | None = None
    """Set by stages whose calls run concurrently; otherwise their API latencies add up."""


@dataclass(slots=True)
class _Run:
    request: Request
    trace: PipelineTrace
    events: EventSink

    @property
    def evidence(self) -> str | None:
        return self.request.evidence if self.trace.config.use_evidence else None


@cache
def _fewshot_index(pool: Dataset) -> FewShotIndex:
    return FewShotIndex.load(pool)


class Pipeline:
    """One configuration over any number of databases. Not safe to share across event loops."""

    def __init__(
        self,
        llm: LLMClient,
        config: PipelineConfig,
        *,
        settings: Settings | None = None,
        resources: Iterable[DatabaseResources] = (),
    ) -> None:
        """`resources` are used as given (and not closed here); others load on first use."""
        self.llm = llm
        self.config = config
        self.settings = settings or llm.settings
        self._slots = schedule(config.strategies, config.n_candidates)
        self._cheap: list[ScheduledCandidate] = []
        if config.cheap_path:
            for name in CHEAP_PATH_STRATEGIES:
                slot = first_of(self._slots, name)
                if slot is None:
                    raise ValueError(
                        f"cheap_path needs {name!r} among the first {config.n_candidates} "
                        f"scheduled strategies of {config.name!r}"
                    )
                self._cheap.append(slot)
        self._rank: dict[str, int] = {}
        for position, name in enumerate(config.strategies):
            self._rank.setdefault(name, position)
        self._resources = {(r.db_id, r.mode): r for r in resources}
        self._owned: list[DatabaseResources] = []
        self._load_lock = asyncio.Lock()
        self._prefix_gates: dict[tuple[str, str, str], asyncio.Event] = {}

    def close(self) -> None:
        """Close the resources this pipeline loaded itself."""
        for resources in self._owned:
            resources.close()
        self._owned.clear()

    async def run(
        self, request: Request, *, on_event: EventCallback | None = None
    ) -> tuple[Answer, PipelineTrace]:
        _check_request(request)
        started = time.perf_counter()
        trace = PipelineTrace(request=request, config=self.config)
        state = _Run(request, trace, EventSink(on_event, started))
        try:
            with (
                collect_safety_events(trace.safety_events),
                span(
                    "pipeline.run",
                    preset=self.config.name,
                    db_id=request.db_id,
                    mode=request.mode.value,
                    question_id=request.question_id,
                ) as current,
            ):
                answer = await self._run(state)
                current.set(status=answer.status, cost_usd=trace.cost_usd)
        finally:
            trace.elapsed_s = time.perf_counter() - started
        return answer, trace

    async def _run(self, state: _Run) -> Answer:
        cfg = self.config
        with self._stage(state, "resources"):
            res = await self._resources_for(state.request)
        analysis = await self._analyze(state) if cfg.question_analysis else None
        matches: ValueMatches = {}
        if cfg.value_retrieval and analysis is not None:
            matches = await self._match_values(state, res, analysis)
        link: LinkResult | None = None
        if cfg.schema_linking and analysis is not None:
            link = await self._link(state, res, analysis, matches)
        fewshots: list[FewShotExample] = []
        if cfg.fewshot_k > 0 and analysis is not None:
            fewshots = await self._fewshots(state, res, analysis)
        env = self._environment(
            state, res, analysis=analysis, matches=matches, link=link, fewshots=fewshots
        )
        candidates = await self._candidates(state, env)
        return await self._decide(state, env, candidates)

    # Stages -----------------------------------------------------------------------------

    async def _resources_for(self, request: Request) -> DatabaseResources:
        key = (request.db_id, request.mode)
        async with self._load_lock:
            res = self._resources.get(key)
            if res is None:
                dataset: Dataset = "saas" if request.db_id == SAAS_DB_ID else "bird"
                res = await asyncio.to_thread(
                    DatabaseResources.load, request.db_id, dataset=dataset, mode=request.mode
                )
                self._resources[key] = res
                self._owned.append(res)
        return res

    async def _analyze(self, state: _Run) -> QuestionAnalysis | None:
        with self._stage(state, "analysis") as stage:
            try:
                result = await analyze_question(
                    self.llm,
                    question=state.request.question,
                    evidence=state.evidence,
                    model=self.settings.small_model,
                    effort=DEFAULT_ANALYSIS_EFFORT,
                )
            except StructuredCallFailed as exc:
                stage.calls.append(exc.meta)
                self._warn(
                    state, f"question analysis failed ({exc.reason}); dependent stages skipped"
                )
                return None
            stage.calls.append(result.meta)
            analysis = result.value
            stage.data.update(
                complexity=analysis.complexity,
                may_be_empty=analysis.may_be_empty,
                literals=list(analysis.literals),
                requested_outputs=list(analysis.requested_outputs),
            )
        state.trace.analysis = analysis
        return analysis

    async def _match_values(
        self, state: _Run, res: DatabaseResources, analysis: QuestionAnalysis
    ) -> ValueMatches:
        with self._stage(state, "values") as stage:
            index = await asyncio.to_thread(res.value_index)
            matches, calls = await index.match(
                analysis, question=state.request.question, llm=self.llm
            )
            stage.calls.extend(calls)
            stage.data.update(
                columns=[f"{t}.{c}" for t, c in matches],
                values=sum(len(v) for v in matches.values()),
            )
        state.trace.matches = matches
        return matches

    async def _link(
        self,
        state: _Run,
        res: DatabaseResources,
        analysis: QuestionAnalysis,
        matches: ValueMatches,
    ) -> LinkResult:
        """A failed selection pass links nothing on its own (link_schema keeps going), so this
        stage cannot fail short of a missing index."""
        with self._stage(state, "linking") as stage:
            link = await link_schema(
                self.llm,
                res.catalog,
                question=state.request.question,
                evidence=state.evidence,
                analysis=analysis,
                values=matches,
                model=self.settings.small_model,
                effort=DEFAULT_LINKING_EFFORT,
                columns=await asyncio.to_thread(res.column_index),
            )
            stage.calls.extend(link.calls)
            if link.calls:
                # One embedding call, then the two selection passes concurrently.
                embedding, *passes = link.calls
                stage.critical_path_s = embedding.api_latency_s + max(
                    (c.api_latency_s for c in passes), default=0.0
                )
            stage.data.update(tables=len(link.schema.tables), columns=len(link.columns))
        state.trace.link = link
        return link

    async def _fewshots(
        self, state: _Run, res: DatabaseResources, analysis: QuestionAnalysis
    ) -> list[FewShotExample]:
        with self._stage(state, "fewshots") as stage:
            index = await asyncio.to_thread(_fewshot_index, res.dataset)
            examples, calls = await index.retrieve(
                skeleton=analysis.skeleton, k=self.config.fewshot_k, llm=self.llm
            )
            stage.calls.extend(calls)
            stage.data.update(questions=[e.question for e in examples])
        state.trace.fewshots = list(examples)
        return list(examples)

    def _environment(
        self,
        state: _Run,
        res: DatabaseResources,
        *,
        analysis: QuestionAnalysis | None,
        matches: ValueMatches,
        link: LinkResult | None,
        fewshots: Sequence[FewShotExample],
    ) -> CandidateEnv:
        """The grammars stage: one grammar and one schema rendering per view."""
        with self._stage(state, "grammars"):
            # The model may only ever see visible columns, whatever linking returned.
            linked: DatabaseSchema | None = None
            if link is not None:
                linked = res.visible_schema.subset(
                    {t.name: t.column_names for t in link.schema.tables}
                )
            full_grammar = res.full_grammar
            linked_grammar = full_grammar if linked is None else build_grammar(linked, res.options)
            grammars: dict[SchemaView, SqlGrammar] = {
                "full": full_grammar,
                "linked": linked_grammar,
            }
            texts: dict[SchemaView, str] = {
                "full": res.full_schema_text,
                "linked": res.full_schema_text
                if linked is None
                else render_schema(res.catalog, subset=linked),
            }
            allowed: dict[SchemaView, DatabaseSchema | None] = {"full": None, "linked": linked}
            built_from: SchemaView = "full"
            if not full_grammar.size.fits_api_budget:
                load = f"estimated load {full_grammar.size.api_load:.2f}"
                if linked is not None:
                    # ADR-008: full-schema strategies keep the full schema in the prompt and
                    # use the widest grammar that fits, the linked one.
                    grammars["full"], allowed["full"], built_from = linked_grammar, linked, "linked"
                    self._warn(state, f"full grammar too large ({load}); using the linked one")
                else:
                    self._warn(state, f"full grammar too large ({load}) and linking is off")
            infos: dict[SchemaView, GrammarInfo] = {
                "full": GrammarInfo.of("full", grammars["full"], built_from),
                "linked": GrammarInfo.of(
                    "linked", linked_grammar, "linked" if linked is not None else "full"
                ),
            }
            state.trace.grammars = infos
            if state.events.enabled:
                for info in infos.values():
                    state.events.emit(
                        "grammars",
                        "info",
                        {
                            "view": info.view,
                            "fingerprint": info.fingerprint,
                            "chars": info.chars,
                            "api_load": info.api_load,
                            "fits_api_budget": info.fits_api_budget,
                            "built_from": info.built_from,
                        },
                    )
            context = GenerationContext(
                db_id=res.db_id,
                question=state.request.question,
                evidence=state.evidence,
                mode=res.mode,
                schema_text=texts,
                grammars=grammars,
                matched_values_text=render_matched_values(
                    res.catalog, matches, subset=res.visible_schema
                ),
                fewshots=tuple(fewshots),
                requested_outputs=tuple(analysis.requested_outputs) if analysis else (),
                bird_conventions=self.config.bird_conventions,
            )
        return CandidateEnv(
            llm=self.llm,
            settings=self.settings,
            config=self.config,
            resources=res,
            request=state.request,
            context=context,
            allowed=allowed,
            analysis=analysis,
            matches=matches,
        )

    async def _candidates(self, state: _Run, env: CandidateEnv) -> list[CandidateTrace]:
        if not self.config.cheap_path:
            with self._stage(state, "candidates") as stage:
                candidates = await self._generate(state, env, self._slots, 0, stage)
        else:
            with self._stage(state, "cheap_path") as stage:
                cheap = await self._generate(state, env, self._cheap, 0, stage)
                taken, reason = cheap_path_exit(cheap, env.analysis)
                stage.data.update(taken=taken, reason=reason)
            state.trace.cheap_path_taken = taken
            state.events.emit("cheap_path", "info", {"taken": taken, "reason": reason})
            candidates = cheap
            if not taken:
                rest = [s for s in self._slots if all(s is not c for c in self._cheap)]
                with self._stage(state, "candidates") as stage:
                    candidates = cheap + await self._generate(state, env, rest, len(cheap), stage)
        state.trace.candidates = candidates
        for c in candidates:
            for attempt in c.attempts:
                if attempt.grammar_failure and attempt.grammar_failure.startswith("api_rejected"):
                    self._warn(
                        state,
                        f"the API rejected the {c.schema_view} grammar: {attempt.grammar_failure}",
                    )
        return candidates

    async def _generate(
        self,
        state: _Run,
        env: CandidateEnv,
        slots: Sequence[ScheduledCandidate],
        first_index: int,
        stage: _Stage,
    ) -> list[CandidateTrace]:
        async def one(slot: ScheduledCandidate, index: int) -> CandidateTrace:
            key = self._prefix_key(env, slot)
            gate = self._prefix_gates.get(key) if key is not None else None
            if key is not None and gate is None:
                # First candidate on a prompt prefix shared across questions: it writes the
                # prompt cache, and the others on that prefix wait so they read it instead of
                # each paying the write (ADR-014). Later questions find the gate open.
                gate = self._prefix_gates[key] = asyncio.Event()
                try:
                    candidate = await run_candidate(env, slot, index)
                finally:
                    gate.set()
            else:
                waited = 0.0
                if gate is not None and not gate.is_set():
                    started = time.perf_counter()
                    await gate.wait()
                    waited = time.perf_counter() - started
                candidate = await run_candidate(env, slot, index)
                candidate.gate_wait_s = waited
            if state.events.enabled:
                state.events.emit("candidate", "info", _candidate_event(candidate))
            return candidate

        try:
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(one(slot, first_index + i)) for i, slot in enumerate(slots)
                ]
        except ExceptionGroup as failed:
            # The other candidates were cancelled; callers expect the error itself
            # (BudgetExceeded, CacheMiss), not a group.
            raise failed.exceptions[0] from failed
        candidates = [t.result() for t in tasks]
        for c in candidates:
            stage.calls.extend(c.calls)
        stage.critical_path_s = max((c.model_latency_s for c in candidates), default=0.0)
        stage.data.update(candidates=len(candidates), executed=sum(c.executed for c in candidates))
        return candidates

    async def _decide(
        self, state: _Run, env: CandidateEnv, candidates: Sequence[CandidateTrace]
    ) -> Answer:
        res, trace = env.resources, state.trace
        selection: Selection | None = None
        with self._stage(state, "selection") as stage:
            executed = executed_candidates(candidates)
            clusters = cluster_candidates(executed) if executed else []
            trace.clusters = clusters
            if state.events.enabled:
                state.events.emit("selection", "info", {"clusters": _clusters_event(clusters)})
            verdict = abstain_or_clarify(
                candidates, clusters, allow_abstain=res.options.allow_abstain
            )
            if verdict is None and executed:
                selection = await select(
                    self.llm,
                    self.settings,
                    self.config,
                    executed,
                    clusters,
                    question=state.request.question,
                    evidence=state.evidence,
                    schema_text=res.full_schema_text,
                    catalog=res.catalog,
                    schema=res.visible_schema,
                    strategy_rank=self._rank,
                    prefer_non_empty=env.analysis is None or not env.analysis.may_be_empty,
                )
                stage.calls.extend(selection.calls)
                stage.critical_path_s = _selection_latency(selection)
                trace.selection = selection
                if state.events.enabled:
                    state.events.emit("selection", "info", _selection_event(selection))
            stage.data.update(verdict=verdict.status if verdict else None, clusters=len(clusters))
        if verdict is not None:
            result = Answer(
                status=verdict.status,
                sql=None,
                preview=None,
                explanation=None,
                schema_elements=[],
                confidence=verdict.confidence,
                reason=verdict.reason,
            )
        elif selection is None or selection.index is None:
            result = Answer(
                status="failed",
                sql=None,
                preview=None,
                explanation=None,
                schema_elements=[],
                confidence=0.0,
                reason=_failure_reason(candidates),
            )
        else:
            result = await self._answered(state, env, candidates[selection.index], selection)
        with self._stage(state, "answer") as stage:
            stage.data.update(
                answer=result.model_dump(mode="json"),
                cost_usd=trace.cost_usd,
                billed_usd=trace.billed_usd,
                model_latency_s=trace.model_latency_s,
            )
        return result

    async def _answered(
        self, state: _Run, env: CandidateEnv, chosen: CandidateTrace, selection: Selection
    ) -> Answer:
        guarded = chosen.guarded
        if guarded is None:
            raise RuntimeError(f"selection picked candidate {chosen.index}, which never executed")
        elements = answers.schema_elements(guarded.sql, env.resources.visible_schema)
        explanation: str | None = None
        if self.config.explain:
            with self._stage(state, "explain") as stage:
                state.trace.prompt_tags.append(answers.explain_tag())
                try:
                    explained = await answers.explain(
                        self.llm,
                        self.settings,
                        question=state.request.question,
                        sql=guarded.sql,
                        elements=elements,
                    )
                except StructuredCallFailed as exc:
                    stage.calls.append(exc.meta)
                    self._warn(state, f"explanation failed ({exc.reason})")
                else:
                    stage.calls.append(explained.meta)
                    explanation = explained.value.explanation
        return Answer(
            status="answered",
            sql=guarded.sql,
            preview=answers.preview(guarded.result),
            explanation=explanation,
            schema_elements=elements,
            confidence=selection.vote_share,
            reason=None,
        )

    # Helpers ----------------------------------------------------------------------------

    @contextmanager
    def _stage(self, state: _Run, name: str) -> Iterator[_Stage]:
        state.events.emit(name, "started")
        stage = _Stage()
        started = time.perf_counter()
        with span(f"pipeline.{name}") as current:
            try:
                yield stage
            finally:
                latency = (
                    stage.critical_path_s
                    if stage.critical_path_s is not None
                    else sum(c.api_latency_s for c in stage.calls)
                )
                record = StageRecord(
                    name, time.perf_counter() - started, latency, tuple(stage.calls)
                )
                state.trace.stages.append(record)
                current.set(
                    calls=len(record.calls), cost_usd=record.cost_usd, model_latency_s=latency
                )
                state.events.emit(
                    name,
                    "finished",
                    {"cost_usd": record.cost_usd, "model_latency_s": latency, **stage.data},
                )

    def _prefix_key(
        self, env: CandidateEnv, slot: ScheduledCandidate
    ) -> tuple[str, str, str] | None:
        """Tools plus developer message 1 form the cached prefix; it is shared across questions
        only when the candidate's grammar is the database's full-schema grammar. The cache is
        also partitioned by model and reasoning effort."""
        if not self.config.grammar:
            return None
        spec = effective_spec(slot.strategy, self.config)
        fingerprint = env.resources.full_grammar.fingerprint
        if env.context.grammars[spec.schema_view].fingerprint != fingerprint:
            return None
        return fingerprint, model_for(spec, self.settings), spec.effort

    @staticmethod
    def _warn(state: _Run, message: str) -> None:
        log.warning(
            "pipeline_warning",
            message=message,
            db_id=state.request.db_id,
            question_id=state.request.question_id,
        )
        state.trace.warnings.append(message)


def _check_request(request: Request) -> None:
    if request.mode is QueryMode.TENANT and request.scope is None:
        raise ValueError("tenant mode needs the caller's ScopeContext")
    if request.mode is not QueryMode.TENANT and request.scope is not None:
        raise ValueError(f"{request.mode.value} mode does not scope queries")


def _selection_latency(selection: Selection) -> float:
    """The judge asks all its pairs at once; unit tests write the tests, then check them all
    at once. The vote makes no calls."""
    latencies = [c.api_latency_s for c in selection.calls]
    if not latencies:
        return 0.0
    if selection.method == JUDGE_METHOD:
        return max(latencies)
    if selection.method == UNIT_TEST_METHOD:
        return latencies[0] + max(latencies[1:], default=0.0)
    return sum(latencies)


def _failure_reason(candidates: Sequence[CandidateTrace]) -> str:
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.status] = counts.get(c.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in counts.items())
    return f"no candidate query executed ({summary})"


def _candidate_event(c: CandidateTrace) -> dict[str, EventValue]:
    rejection = c.rejection
    return {
        "index": c.index,
        "strategy": c.strategy,
        "model": c.model,
        "effort": c.effort,
        "sample": c.sample,
        "schema_view": c.schema_view,
        "sql": c.sql,
        "abstain_reason": c.abstain_reason,
        "grammar_ok": c.grammar_ok,
        "status": c.status,
        "error": c.exec_error
        or (rejection.detail if rejection else None)
        or c.final.grammar_failure,
        "layer": rejection.layer if rejection else None,
        "rule": rejection.rule if rejection else None,
        "row_count": c.row_count,
        "repairs": c.repairs,
        "cost_usd": c.cost_usd,
    }


def _clusters_event(clusters: Sequence[Cluster]) -> list[EventValue]:
    return [
        {
            "fingerprint": c.fingerprint,
            "members": list(c.members),
            "representative": c.representative,
        }
        for c in clusters
    ]


def _selection_event(selection: Selection) -> dict[str, EventValue]:
    return {
        "method": selection.method,
        "index": selection.index,
        "vote_share": selection.vote_share,
        "n_clusters": selection.n_clusters,
        "scores": {str(k): v for k, v in selection.scores.items()},
    }
