"""Per-candidate, per-question and per-run evaluation records.

These are the only shapes the harness reads and writes: the runner builds them, `metrics`
aggregates them, `report` serialises them to `per_question.jsonl` and `results.json`, and
`regenerate_results_md` reads them back. Derived values (`pass_at_n`, `linking_recall`) are
computed from stored fields so a record can never disagree with itself.

Costs are list-price estimates of the token usage a question needed, including calls replayed
from the response cache, so an offline replay reports the same cost per question as the run
that paid for it. Money actually billed during a run lives in `SpendSummary.billed_usd`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from text2sql.config import ReasoningEffort

Dataset = Literal["bird_minidev", "bird_arcwise", "saas"]
Split = Literal["dev", "test", "all"]
SaasBucket = Literal["answerable", "tenant", "unanswerable", "adversarial"]
SafetyLayer = Literal["grammar", "validator", "executor", "scoping"]
SAFETY_LAYERS: tuple[SafetyLayer, ...] = ("grammar", "validator", "executor", "scoping")
"""Layers 1-4 in the numbering of the threat model."""

type JsonScalar = str | int | float | bool | None
type ColumnRef = tuple[str, str]
"""(table, column) using the schema's spelling."""


class ErrorLabel(StrEnum):
    """Failure taxonomy. The classifier chooses among the first eight (`taxonomy.ClassifierLabel`);
    rules assign the last three, and `gold_label_suspect` when the prediction equals the
    corrected gold."""

    WRONG_SCHEMA_ITEM = "wrong_table_or_column"
    WRONG_JOIN_PATH = "wrong_join_path"
    WRONG_AGGREGATION = "wrong_aggregation_or_grouping"
    WRONG_FILTER_VALUE = "wrong_filter_value"
    DATE_HANDLING = "date_handling"
    OUTPUT_COLUMNS = "extra_or_missing_output_columns"
    GOLD_SUSPECT = "gold_label_suspect"
    OTHER = "other"
    NO_SQL = "no_sql_produced"
    ABSTENTION = "abstention_error"
    FLOAT_OR_ROUNDING = "float_or_rounding"


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True)


class FailureLabel(_Record):
    label: ErrorLabel
    rationale: str
    source: Literal["classifier", "rule", "human"]
    model: str | None = None
    """Model that produced a classifier label."""


class SafetyEventRecord(_Record):
    """A query stopped by one safety layer (mirrors `text2sql.safety.SafetyEvent`)."""

    layer: SafetyLayer
    rule: str
    detail: str


class ResultPreview(_Record):
    """The first rows of a result set, for failure reports and the error classifier."""

    columns: list[str]
    rows: list[list[JsonScalar]]
    row_count: int = Field(ge=0)
    """Rows in the full result, not just the preview."""


class CandidateRecord(_Record):
    """One generated candidate after any repair passes."""

    strategy: str
    model: str
    effort: ReasoningEffort
    sql: str | None = None
    abstain_reason: str | None = None
    grammar_ok: bool
    """The API returned a tool call that re-parsed under the request grammar."""
    validator_error: str | None = None
    exec_error: str | None = None
    result_fingerprint: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    repairs: int = Field(default=0, ge=0)
    correct: bool | None = None
    """None when there is nothing to score against (no gold SQL and no abstention target)."""
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_s: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _sql_or_abstain(self) -> Self:
        if self.sql is not None and self.abstain_reason is not None:
            raise ValueError("a candidate either has SQL or abstains, not both")
        return self


class QuestionRecord(_Record):
    """Everything the harness knows about one question in one run."""

    dataset: Dataset
    split: Split
    question_id: str
    db_id: str
    question: str
    evidence: str | None = None
    gold_sql: str | None = None
    """None for questions whose correct behaviour is to abstain."""
    difficulty: str | None = None
    bucket: SaasBucket | None = None
    with_evidence: bool = False
    gold_suspect: bool = False
    """The gold label is known or suspected to be wrong (e.g. corrected in Arcwise-Plat-SQL)."""
    matches_arcwise_gold: bool | None = None
    """The final SQL returns the Arcwise-Plat-SQL gold's rows (BIRD's set comparison). None when
    the item has no Arcwise gold (SaaS, the Arcwise release itself) or there is no final SQL."""

    candidates: list[CandidateRecord] = Field(default_factory=list)
    selected_index: int | None = None
    final_sql: str | None = None
    correct: bool
    abstained: bool = False
    should_abstain: bool = False

    linked_columns: list[ColumnRef] | None = None
    """None when schema linking was off (the model saw the full schema)."""
    gold_columns: list[ColumnRef] | None = None
    gold_in_grammar: bool | None = None
    """Whether the normalised gold SQL parses under the full-schema grammar."""
    grammar_calls: int = Field(default=0, ge=0)
    grammar_rejections: int = Field(default=0, ge=0)
    """Grammar-tool calls that returned no usable tool call."""
    safety_events: list[SafetyEventRecord] = Field(default_factory=list)
    safety_violation: bool = False
    """An unsafe effect reached the database, e.g. another tenant's canary row in a result."""

    gold_preview: ResultPreview | None = None
    predicted_preview: ResultPreview | None = None
    rves_reward: float | None = None
    cost_usd: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    """Wall-clock time as recorded when the responses were first produced."""
    failure_label: FailureLabel | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pass_at_n(self) -> bool:
        """Oracle: at least one candidate is correct."""
        return any(c.correct is True for c in self.candidates)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def linking_recall(self) -> float | None:
        """Share of gold columns that schema linking kept (case-insensitive)."""
        if not self.gold_columns or self.linked_columns is None:
            return None
        gold = {(t.lower(), c.lower()) for t, c in self.gold_columns}
        linked = {(t.lower(), c.lower()) for t, c in self.linked_columns}
        return len(gold & linked) / len(gold)

    def candidate_errors(self) -> list[str]:
        """Why the selected candidate (or, with none selected, every candidate) went wrong."""
        chosen = (
            [self.candidates[self.selected_index]]
            if self.selected_index is not None
            else self.candidates
        )
        out: list[str] = []
        for c in chosen:
            if not c.grammar_ok:
                out.append(f"{c.strategy}: no valid grammar tool call")
            if c.validator_error:
                out.append(f"{c.strategy}: validator: {c.validator_error}")
            if c.exec_error:
                out.append(f"{c.strategy}: execution: {c.exec_error}")
            if c.abstain_reason:
                out.append(f"{c.strategy}: abstained: {c.abstain_reason}")
        return out

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.selected_index is not None and not 0 <= self.selected_index < len(self.candidates):
            raise ValueError(f"selected_index {self.selected_index} is out of range")
        if self.abstained and self.final_sql is not None:
            raise ValueError("an abstained question has no final SQL")
        if self.grammar_rejections > self.grammar_calls:
            raise ValueError("more grammar rejections than grammar calls")
        if (self.dataset == "saas") != (self.bucket is not None):
            raise ValueError("bucket is set exactly for SaaS questions")
        if self.dataset == "saas" and self.with_evidence:
            raise ValueError("SaaS questions have no evidence field")
        return self


class SpendSummary(_Record):
    billed_usd: float = Field(ge=0.0)
    """Money actually charged during this run; cache hits are free."""
    priced_usd: float = Field(ge=0.0)
    """List-price cost of every call's usage, cache hits included."""
    budget_usd: float = Field(gt=0.0)
    calls: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)


_SWEEP_FIELDS = ("n_candidates", "effort")


class RunRecord(_Record):
    """One evaluation run: a configuration applied to one dataset split.

    `overrides` are the settings changed on top of the preset `config_name`; they classify the
    run for RESULTS.md. No overrides: the preset itself. Only `n_candidates` or only `effort`:
    a point on the N or effort sweep. Anything else: an ablation row.
    """

    run_id: str
    git_sha: str
    """Commit of the code that produced the run; suffixed `-dirty` for uncommitted changes."""
    timestamp: datetime
    config_name: str
    config: dict[str, Any]
    overrides: dict[str, JsonScalar] = Field(default_factory=dict)
    n_candidates: int = Field(ge=1)
    effort: ReasoningEffort
    """Reasoning effort of the generator model."""
    dataset: Dataset
    split: Split
    with_evidence: bool
    questions_planned: int = Field(ge=0)
    partial: bool
    partial_reason: str | None = None
    spend: SpendSummary

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.partial != (self.partial_reason is not None):
            raise ValueError("a partial run needs a partial_reason, and only a partial run")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        for name in _SWEEP_FIELDS:
            if name in self.overrides and self.overrides[name] != getattr(self, name):
                raise ValueError(f"overrides[{name!r}] disagrees with the run's {name}")
        if self.dataset == "saas" and self.with_evidence:
            raise ValueError("SaaS runs have no evidence field")
        return self
