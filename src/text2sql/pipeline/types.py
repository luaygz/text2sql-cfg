"""Request, answer and the trace of one pipeline run.

The trace is what the eval runner turns into `CandidateRecord`s and a `QuestionRecord`. Every
LLM call is attributed to exactly one stage, so `PipelineTrace.calls` is the flat list of stage
calls and per-stage cost needs no second bookkeeping.

Latency has two readings. `elapsed_s` is wall time in this process. `model_latency_s` is the
critical path over the API latency recorded with each response (sequential stages add up,
concurrent candidates take the slowest), without local execution time, so a replay from the
response cache reports the same latency as the run that produced the responses.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from text2sql.config import PipelineConfig, QueryMode, ReasoningEffort
from text2sql.evals.records import ResultPreview
from text2sql.execution import QueryResult
from text2sql.generation import RepairKind, SchemaView
from text2sql.grammar import SqlGrammar
from text2sql.llm import CallMeta
from text2sql.retrieval import FewShotExample, LinkResult, QuestionAnalysis, ValueMatches
from text2sql.safety import Layer, SafetyEvent, ScopeContext
from text2sql.safety.guard import GuardResult
from text2sql.selection import Cluster, Selection


@dataclass(frozen=True, slots=True)
class Request:
    question: str
    evidence: str | None
    db_id: str
    mode: QueryMode
    scope: ScopeContext | None = None
    """The authenticated caller; required in tenant mode, never taken from the question."""
    question_id: str | None = None


AnswerStatus = Literal["answered", "abstained", "clarify", "failed"]


class Answer(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: AnswerStatus
    sql: str | None
    """The chosen query as the model wrote it (the trace also has the scoped, executed text)."""
    preview: ResultPreview | None
    explanation: str | None
    schema_elements: list[str]
    """`table.column` for every base column the query reads."""
    confidence: float = Field(ge=0.0, le=1.0)
    """Share of the executed candidates that agree with the answer (or that abstained)."""
    reason: str | None
    """Why the pipeline abstained, asked to clarify, or failed."""


CandidateStatus = Literal[
    "ok", "empty", "exec_error", "timeout", "guard_rejected", "abstained", "grammar_failed"
]
"""`ok`: executed with rows. `empty`: executed, no rows. `exec_error`/`timeout`: SQLite failed
or ran out of time. `guard_rejected`: a safety layer refused it. `grammar_failed`: the API
returned no usable tool call or refused the grammar (grammar-off ablation: no usable JSON)."""


@dataclass(frozen=True, slots=True)
class Rejection:
    layer: Layer
    rule: str
    detail: str


@dataclass(frozen=True, slots=True)
class Attempt:
    """One generation call (the first, or a repair) and what the guard made of its output."""

    number: int
    """0 for the first call, n for the n-th repair."""
    meta: CallMeta
    status: CandidateStatus
    output: Literal["grammar", "json"] = "grammar"
    sql: str | None = None
    abstain_reason: str | None = None
    grammar_failure: str | None = None
    """`<reason>: <detail>` of a GrammarCallFailed."""
    rejection: Rejection | None = None
    exec_error: str | None = None
    guarded: GuardResult | None = None
    fingerprint: str | None = None
    """`text2sql.selection.result_fingerprint` of the result."""
    ordered: bool = False
    exec_s: float = 0.0
    feedback: str | None = None
    """What the next repair call was told about this attempt."""
    repair_kind: RepairKind | None = None
    """Why the next repair call was made (`value`: a compared string the column does not hold);
    None when no repair followed this attempt."""

    @property
    def executed(self) -> bool:
        return self.guarded is not None


@dataclass(slots=True)
class CandidateTrace:
    """A scheduled candidate and its attempts. The final state is the last attempt that
    executed, else the last one that produced output, else the last one."""

    index: int
    """Position in `PipelineTrace.candidates`; also the index selection refers to."""
    strategy: str
    model: str
    effort: ReasoningEffort
    sample: int
    schema_view: SchemaView
    prompt_tags: tuple[str, ...] = ()
    attempts: list[Attempt] = field(default_factory=list)
    gate_wait_s: float = 0.0
    """Wall time spent waiting for another candidate to warm the shared prompt cache; left out
    of `model_latency_s`, since it happens once per prompt prefix and process."""

    @property
    def final(self) -> Attempt:
        executed = [a for a in self.attempts if a.executed]
        if executed:
            return executed[-1]
        produced = [a for a in self.attempts if a.sql is not None or a.abstain_reason is not None]
        return produced[-1] if produced else self.attempts[-1]

    @property
    def status(self) -> CandidateStatus:
        return self.final.status

    @property
    def executed(self) -> bool:
        return self.final.executed

    @property
    def sql(self) -> str | None:
        return self.final.sql

    @property
    def abstain_reason(self) -> str | None:
        return self.final.abstain_reason

    @property
    def grammar_ok(self) -> bool:
        return self.final.grammar_failure is None

    @property
    def rejection(self) -> Rejection | None:
        return self.final.rejection

    @property
    def validator_error(self) -> str | None:
        return _layer_error(self.final.rejection, "validator")

    @property
    def scoping_error(self) -> str | None:
        return _layer_error(self.final.rejection, "scoping")

    @property
    def exec_error(self) -> str | None:
        """SQLite error, timeout, or a layer-3 denial."""
        return self.final.exec_error or _layer_error(self.final.rejection, "executor")

    @property
    def guarded(self) -> GuardResult | None:
        return self.final.guarded

    @property
    def executed_sql(self) -> str | None:
        guarded = self.final.guarded
        return guarded.executed_sql if guarded else None

    @property
    def params(self) -> Mapping[str, int]:
        guarded = self.final.guarded
        return guarded.params if guarded else {}

    @property
    def result(self) -> QueryResult | None:
        guarded = self.final.guarded
        return guarded.result if guarded else None

    @property
    def ordered(self) -> bool:
        return self.final.ordered

    @property
    def fingerprint(self) -> str | None:
        return self.final.fingerprint

    @property
    def row_count(self) -> int | None:
        result = self.result
        return len(result.rows) if result else None

    @property
    def repairs(self) -> int:
        return len(self.attempts) - 1

    @property
    def calls(self) -> tuple[CallMeta, ...]:
        return tuple(a.meta for a in self.attempts)

    @property
    def grammar_calls(self) -> int:
        return sum(a.output == "grammar" for a in self.attempts)

    @property
    def grammar_failures(self) -> int:
        return sum(a.output == "grammar" and a.grammar_failure is not None for a in self.attempts)

    @property
    def cost_usd(self) -> float:
        return sum(a.meta.priced_usd for a in self.attempts)

    @property
    def model_latency_s(self) -> float:
        return sum(a.meta.api_latency_s for a in self.attempts)

    @property
    def exec_s(self) -> float:
        return sum(a.exec_s for a in self.attempts)


def _layer_error(rejection: Rejection | None, layer: Layer) -> str | None:
    if rejection is None or rejection.layer != layer:
        return None
    return f"{rejection.rule}: {rejection.detail}"


@dataclass(frozen=True, slots=True)
class GrammarInfo:
    view: SchemaView
    fingerprint: str
    chars: int
    api_load: float
    fits_api_budget: bool
    built_from: SchemaView
    """`linked` for the full view when the full-schema grammar did not fit and fell back."""

    @classmethod
    def of(cls, view: SchemaView, grammar: SqlGrammar, built_from: SchemaView) -> GrammarInfo:
        size = grammar.size
        return cls(
            view, grammar.fingerprint, size.chars, size.api_load, size.fits_api_budget, built_from
        )


@dataclass(frozen=True, slots=True)
class StageRecord:
    name: str
    elapsed_s: float
    model_latency_s: float
    calls: tuple[CallMeta, ...]

    @property
    def cost_usd(self) -> float:
        return sum(c.priced_usd for c in self.calls)


@dataclass(slots=True)
class PipelineTrace:
    request: Request
    config: PipelineConfig
    analysis: QuestionAnalysis | None = None
    matches: ValueMatches = field(default_factory=dict)
    link: LinkResult | None = None
    fewshots: list[FewShotExample] = field(default_factory=list)
    grammars: dict[SchemaView, GrammarInfo] = field(default_factory=dict)
    candidates: list[CandidateTrace] = field(default_factory=list)
    clusters: list[Cluster] = field(default_factory=list)
    selection: Selection | None = None
    safety_events: list[SafetyEvent] = field(default_factory=list)
    cheap_path_taken: bool = False
    stages: list[StageRecord] = field(default_factory=list)
    prompt_tags: list[str] = field(default_factory=list)
    """Templates used outside candidate generation (candidates carry their own)."""
    warnings: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0

    @property
    def linked_columns(self) -> frozenset[tuple[str, str]] | None:
        """None when schema linking was off and the model saw the full schema."""
        return self.link.columns if self.link is not None else None

    @property
    def calls(self) -> tuple[CallMeta, ...]:
        return tuple(c for s in self.stages for c in s.calls)

    @property
    def grammar_calls(self) -> int:
        return sum(c.grammar_calls for c in self.candidates)

    @property
    def grammar_failures(self) -> int:
        return sum(c.grammar_failures for c in self.candidates)

    @property
    def cost_usd(self) -> float:
        """List-price cost of every call, cache hits included."""
        return sum(c.priced_usd for c in self.calls)

    @property
    def billed_usd(self) -> float:
        """Money charged by this run (0 for calls served from the response cache)."""
        return sum(c.cost_usd for c in self.calls)

    @property
    def model_latency_s(self) -> float:
        return sum(s.model_latency_s for s in self.stages)

    def stage(self, name: str) -> StageRecord | None:
        return next((s for s in self.stages if s.name == name), None)
