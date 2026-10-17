"""Evaluation metrics over question records, and gold-column extraction for linking recall.

Per-question correctness is decided upstream (BIRD's set comparison in `bird_metric`, or the
abstention target for SaaS); this module only aggregates. Every proportion carries a percentile
bootstrap interval and a Wilson interval as a cross-check. Definitions are in ADR-009.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence

import numpy as np
import sqlglot
from pydantic import BaseModel, ConfigDict
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.schema import MappingSchema

from text2sql.catalog.schema import DatabaseSchema
from text2sql.evals.bird_metric import rves_score
from text2sql.evals.records import SAFETY_LAYERS, ColumnRef, QuestionRecord
from text2sql.evals.stats import (
    DEFAULT_RESAMPLES,
    DEFAULT_SEED,
    bootstrap_paired_difference,
    bootstrap_proportion,
    mcnemar_exact,
    wilson_interval,
)

DIFFICULTY_ORDER = ("simple", "moderate", "challenging", "easy", "medium", "hard")
"""BIRD levels, then SaaS levels; anything else sorts after these alphabetically."""
UNKNOWN = "unknown"


class _Summary(BaseModel):
    model_config = ConfigDict(frozen=True)


class Rate(_Summary):
    k: int
    n: int
    value: float
    ci_low: float
    """95% percentile bootstrap."""
    ci_high: float
    wilson_low: float
    wilson_high: float


def rate(
    outcomes: Sequence[bool], *, resamples: int = DEFAULT_RESAMPLES, seed: int = DEFAULT_SEED
) -> Rate:
    boot = bootstrap_proportion(outcomes, resamples=resamples, seed=seed)
    k = sum(outcomes)
    wilson = wilson_interval(k, len(outcomes))
    return Rate(
        k=k,
        n=len(outcomes),
        value=boot.estimate,
        ci_low=boot.low,
        ci_high=boot.high,
        wilson_low=wilson.low,
        wilson_high=wilson.high,
    )


class GroupSummary(_Summary):
    n: int
    ex: Rate
    pass_at_n: Rate
    selection_accuracy: float | None
    """EX / pass@N; None when no question had a correct candidate."""
    cost_per_question_usd: float
    latency_p50_s: float
    latency_p95_s: float


def group_summary(questions: Sequence[QuestionRecord]) -> GroupSummary:
    if not questions:
        raise ValueError("cannot summarise an empty group")
    ex = rate([q.correct for q in questions])
    oracle = rate([q.pass_at_n for q in questions])
    p50, p95 = np.percentile([q.latency_s for q in questions], [50, 95])
    return GroupSummary(
        n=len(questions),
        ex=ex,
        pass_at_n=oracle,
        selection_accuracy=ex.value / oracle.value if oracle.k else None,
        cost_per_question_usd=sum(q.cost_usd for q in questions) / len(questions),
        latency_p50_s=float(p50),
        latency_p95_s=float(p95),
    )


def _group_order(key: str, order: Sequence[str]) -> tuple[int, str]:
    return (order.index(key) if key in order else len(order), key)


def breakdown(
    questions: Iterable[QuestionRecord],
    key: Callable[[QuestionRecord], str | None],
    *,
    order: Sequence[str] = (),
) -> dict[str, GroupSummary]:
    """Summaries per group, in `order` first and then alphabetically; None keys become 'unknown'."""
    groups: dict[str, list[QuestionRecord]] = {}
    for q in questions:
        groups.setdefault(key(q) or UNKNOWN, []).append(q)
    return {
        name: group_summary(groups[name])
        for name in sorted(groups, key=lambda g: _group_order(g, order))
    }


class LinkingSummary(_Summary):
    n: int
    """Questions with both gold and linked columns."""
    full_recall: Rate
    """Share of questions whose gold columns are all among the linked columns."""
    mean_column_recall: float


def linking_summary(questions: Iterable[QuestionRecord]) -> LinkingSummary | None:
    recalls = [r for q in questions if (r := q.linking_recall) is not None]
    if not recalls:
        return None
    return LinkingSummary(
        n=len(recalls),
        full_recall=rate([r == 1.0 for r in recalls]),
        mean_column_recall=sum(recalls) / len(recalls),
    )


class CoverageCase(_Summary):
    """One gold query checked against the full-schema grammar."""

    db_id: str
    question_id: str
    parsed: bool
    error: str | None = None


class CoverageSummary(_Summary):
    overall: Rate
    by_db: dict[str, Rate]
    failures: list[CoverageCase]


def grammar_coverage(cases: Iterable[CoverageCase]) -> CoverageSummary | None:
    """Aggregate gold-SQL grammar checks, from the coverage script or from question records."""
    by_db: dict[str, list[CoverageCase]] = {}
    for case in cases:
        by_db.setdefault(case.db_id, []).append(case)
    if not by_db:
        return None
    every = [c for db in sorted(by_db) for c in by_db[db]]
    return CoverageSummary(
        overall=rate([c.parsed for c in every]),
        by_db={db: rate([c.parsed for c in by_db[db]]) for db in sorted(by_db)},
        failures=[c for c in every if not c.parsed],
    )


class RejectionSummary(_Summary):
    calls: int
    rejections: int
    rate: float | None


def rejection_summary(questions: Iterable[QuestionRecord]) -> RejectionSummary:
    calls = rejections = 0
    for q in questions:
        calls += q.grammar_calls
        rejections += q.grammar_rejections
    return RejectionSummary(
        calls=calls, rejections=rejections, rate=rejections / calls if calls else None
    )


class SafetySummary(_Summary):
    events_by_layer: dict[str, int]
    """Queries stopped at each layer; an `executor` event is a query that got through layers 1-2."""
    questions_stopped_by_layer: dict[str, int]
    adversarial_questions: int
    database_violations: int
    """Questions where an unsafe effect reached the database. Must be 0."""


def safety_summary(questions: Iterable[QuestionRecord]) -> SafetySummary:
    events: dict[str, int] = dict.fromkeys(SAFETY_LAYERS, 0)
    stopped: dict[str, int] = dict.fromkeys(SAFETY_LAYERS, 0)
    adversarial = violations = 0
    for q in questions:
        for event in q.safety_events:
            events[event.layer] += 1
        for layer in {e.layer for e in q.safety_events}:
            stopped[layer] += 1
        adversarial += q.bucket == "adversarial"
        violations += q.safety_violation
    return SafetySummary(
        events_by_layer=events,
        questions_stopped_by_layer=stopped,
        adversarial_questions=adversarial,
        database_violations=violations,
    )


class AbstentionSummary(_Summary):
    abstained: int
    should_abstain: int
    precision: Rate | None
    """Of the questions the system abstained on, the share it should have."""
    recall: Rate | None
    """Of the questions it should have abstained on, the share it did."""


def abstention_summary(questions: Sequence[QuestionRecord]) -> AbstentionSummary | None:
    """Precision and recall of abstaining, over answerable, tenant and unanswerable questions.

    Adversarial questions are left out: refusing an attack is scored by the adversarial verdict
    (`correct` on that bucket), and counting a refusal as a wrong abstention would punish the
    behaviour the bucket asks for.
    """
    scored = [q for q in questions if q.bucket != "adversarial"]
    abstained = [q.should_abstain for q in scored if q.abstained]
    targets = [q.abstained for q in scored if q.should_abstain]
    if not abstained and not targets:
        return None
    return AbstentionSummary(
        abstained=len(abstained),
        should_abstain=len(targets),
        precision=rate(abstained) if abstained else None,
        recall=rate(targets) if targets else None,
    )


class PairedComparison(_Summary):
    """Variant minus reference on the questions both runs answered."""

    n: int
    reference_ex: float
    variant_ex: float
    delta: float
    delta_ci_low: float
    delta_ci_high: float
    reference_only: int
    variant_only: int
    mcnemar_p: float


def _by_question(questions: Sequence[QuestionRecord]) -> dict[tuple[str, str], bool]:
    outcomes = {(q.db_id, q.question_id): q.correct for q in questions}
    if len(outcomes) != len(questions):
        raise ValueError("a question appears twice in one side of a paired comparison")
    return outcomes


def compare_paired(
    reference: Sequence[QuestionRecord], variant: Sequence[QuestionRecord]
) -> PairedComparison:
    """Paired bootstrap CI on the EX difference and exact McNemar test, matched by question."""
    ref, var = _by_question(reference), _by_question(variant)
    keys = sorted(ref.keys() & var.keys())
    if not keys:
        raise ValueError("the two runs share no questions")
    a = [ref[k] for k in keys]
    b = [var[k] for k in keys]
    delta = bootstrap_paired_difference(a, b)
    test = mcnemar_exact(a, b)
    return PairedComparison(
        n=len(keys),
        reference_ex=sum(a) / len(a),
        variant_ex=sum(b) / len(b),
        delta=delta.estimate,
        delta_ci_low=delta.low,
        delta_ci_high=delta.high,
        reference_only=test.reference_only,
        variant_only=test.variant_only,
        mcnemar_p=test.p_value,
    )


def evidence_pairing(questions: Sequence[QuestionRecord]) -> PairedComparison | None:
    """With-evidence minus without-evidence EX on the same questions; None if a side is missing."""
    without = [q for q in questions if not q.with_evidence]
    with_ = [q for q in questions if q.with_evidence]
    if not without or not with_:
        return None
    return compare_paired(without, with_)


class RunSummary(_Summary):
    overall: GroupSummary
    by_difficulty: dict[str, GroupSummary]
    by_db: dict[str, GroupSummary]
    by_bucket: dict[str, GroupSummary]
    """SaaS buckets; empty for BIRD."""
    linking: LinkingSummary | None
    grammar_coverage: CoverageSummary | None
    grammar_rejections: RejectionSummary
    safety: SafetySummary
    abstention: AbstentionSummary | None
    rves: float | None
    """R-VES on a 0-125 scale; None unless every question carries a reward."""
    cost_total_usd: float
    failures: int
    failure_labels: dict[str, int]
    """Taxonomy label counts over failures; unlabelled failures are counted as 'unlabelled'."""
    gold_suspect_failures: int


def summarize_run(questions: Sequence[QuestionRecord]) -> RunSummary:
    failures = [q for q in questions if not q.correct]
    labels = Counter(
        q.failure_label.label.value if q.failure_label else "unlabelled" for q in failures
    )
    rewards = [q.rves_reward for q in questions]
    coverage = (
        CoverageCase(db_id=q.db_id, question_id=q.question_id, parsed=q.gold_in_grammar)
        for q in questions
        if q.gold_in_grammar is not None
    )
    saas = [q for q in questions if q.bucket is not None]
    return RunSummary(
        overall=group_summary(questions),
        by_difficulty=breakdown(questions, lambda q: q.difficulty, order=DIFFICULTY_ORDER),
        by_db=breakdown(questions, lambda q: q.db_id),
        by_bucket=breakdown(saas, lambda q: q.bucket),
        linking=linking_summary(questions),
        grammar_coverage=grammar_coverage(coverage),
        grammar_rejections=rejection_summary(questions),
        safety=safety_summary(questions),
        abstention=abstention_summary(questions),
        rves=rves_score([r for r in rewards if r is not None]) if None not in rewards else None,
        cost_total_usd=sum(q.cost_usd for q in questions),
        failures=len(failures),
        failure_labels=dict(sorted(labels.items())),
        gold_suspect_failures=sum(q.gold_suspect for q in failures),
    )


class GoldColumnsError(ValueError):
    """Gold SQL could not be parsed or qualified against the schema."""


def gold_columns(sql: str, schema: DatabaseSchema) -> set[ColumnRef]:
    """Base-table columns a query reads, with T1/T2 aliases, CTEs and subqueries resolved.

    A column of a derived table (CTE or subquery output) is not reported itself; the base
    columns its definition reads are. `SELECT *` counts every column of the table. Identifiers
    that match no column are skipped: SQLite then reads a double-quoted identifier as a string
    literal, which BIRD gold SQL relies on. Names come back in the schema's spelling.
    """
    mapping = MappingSchema(
        {t.name: dict.fromkeys(t.column_names, "TEXT") for t in schema.tables}, dialect="sqlite"
    )
    try:
        tree = qualify(
            sqlglot.parse_one(sql, dialect="sqlite"),
            schema=mapping,
            dialect="sqlite",
            validate_qualify_columns=False,
            quote_identifiers=False,
            identify=False,
        )
        scopes = traverse_scope(tree)
    except SqlglotError as e:
        raise GoldColumnsError(f"cannot resolve columns of {sql!r}: {e}") from e
    found: set[ColumnRef] = set()
    for scope in scopes:
        for column in scope.columns:
            table_name = _base_table(scope, column.table)
            table = schema.table(table_name) if table_name else None
            col = table.column(column.name) if table else None
            if table and col:
                found.add((table.name, col.name))
    return found


def _base_table(scope: Scope | None, alias: str) -> str | None:
    """Follow an alias outwards (correlated subqueries) to a base table; None for derived ones."""
    while scope is not None:
        source = scope.sources.get(alias)
        if isinstance(source, exp.Table):
            return source.name
        if source is not None:
            return None
        scope = scope.parent
    return None
