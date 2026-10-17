"""Per-case outcomes of the adversarial suite and the report aggregated from them."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from text2sql.evals.safety_suite.cases import Expectation
from text2sql.safety import Layer
from text2sql.safety.leaks import LAYER_ORDER

Outcome = Literal["stopped", "passed", "executed", "leaked"]
"""What happened when one layer alone handled a case:

stopped   the layer refused it, or the query it produced returned nothing (the error came from
          what this layer did, e.g. a guard that does not project the column asked for)
passed    the layer accepted it; for layer 4, the permissive executor behind it refused it
executed  rows came back and none leaked
leaked    rows came back carrying data the caller must not see
"""

EXECUTED: Final = "executed"
"""`GuardOutcome.stopped_at` key in `stops_by_layer` for cases the guard ran to completion."""
SQLITE_ERROR_RULE: Final = "sqlite_error"
"""An ordinary SQLite error at layer 3: not a safety event, it feeds the repair loop."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GuardOutcome(_Frozen):
    stopped_at: Layer | None
    """Layer that stopped the case; None when it ran to completion."""
    rule: str | None
    detail: str
    reached_executor: bool
    executed: bool
    leaks: list[str]
    events: int
    """Safety events the guard logged for this case."""


class LayerOutcome(_Frozen):
    outcome: Outcome
    detail: str


class CaseResult(_Frozen):
    id: str
    category: str
    expect: Expectation
    layers: tuple[Layer, ...]
    sql: str
    tenant: int
    user: int | None
    guard: GuardOutcome
    isolation: dict[Layer, LayerOutcome]
    violation_at_executor: bool
    """A `reject` case reached layer 3."""
    violation_at_db: bool
    """A result leaked, a `reject` case ran, or a `bounded` case ran to completion."""
    isolation_failures: list[Layer]
    """Responsible layers that did not stop the case (or, for `contain`, leaked) on their own."""
    unlogged_stop: bool
    """The guard stopped the case without exactly one matching safety event, or logged one
    without stopping it."""


class ResponsibleCount(_Frozen):
    cases: int
    held: int
    """Cases this layer alone stopped (or, for `contain` cases, ran without a leak)."""


class SafetySuiteReport(_Frozen):
    created_at: datetime
    git_sha: str
    db_sha256: str
    cases_sha256: str
    n_cases: int
    cases_by_category: dict[str, int]
    stops_by_layer: dict[str, int]
    """Where the full guard stopped each case, in layer order, plus `executed`."""
    rules_by_layer: dict[str, dict[str, int]]
    isolation_by_layer: dict[str, dict[str, int]]
    """Layer -> outcome -> cases, every case run through that layer alone."""
    responsible_by_layer: dict[str, ResponsibleCount]
    violations_at_executor: int
    violations_at_db: int
    isolation_failures: int
    unlogged_stops: int
    db_unchanged: bool
    results: list[CaseResult]

    @property
    def passed(self) -> bool:
        return (
            self.violations_at_executor == 0
            and self.violations_at_db == 0
            and self.isolation_failures == 0
            and self.unlogged_stops == 0
            and self.db_unchanged
        )

    def summary(self) -> str:
        stops = ", ".join(f"{layer} {count}" for layer, count in self.stops_by_layer.items())
        lines = [
            f"safety suite: {self.n_cases} cases, {'PASS' if self.passed else 'FAIL'}",
            f"  stopped by: {stops}",
            f"  violations reaching layer 3: {self.violations_at_executor}",
            f"  violations reaching the database: {self.violations_at_db}",
            f"  responsible layer failed alone: {self.isolation_failures}",
            f"  stops without a logged safety event: {self.unlogged_stops}",
            f"  database unchanged: {'yes' if self.db_unchanged else 'NO'}",
        ]
        failing = [
            r.id
            for r in self.results
            if r.violation_at_executor
            or r.violation_at_db
            or r.isolation_failures
            or r.unlogged_stop
        ]
        if failing:
            lines.append(f"  failing cases: {', '.join(failing)}")
        return "\n".join(lines)


def build_report(
    results: list[CaseResult],
    *,
    created_at: datetime,
    git_sha: str,
    db_sha256: str,
    cases_sha256: str,
    db_unchanged: bool,
) -> SafetySuiteReport:
    stops: Counter[str] = Counter(r.guard.stopped_at or EXECUTED for r in results)
    rules: dict[str, Counter[str]] = {layer: Counter() for layer in LAYER_ORDER}
    for r in results:
        if r.guard.stopped_at is not None and r.guard.rule is not None:
            rules[r.guard.stopped_at][r.guard.rule] += 1
    return SafetySuiteReport(
        created_at=created_at,
        git_sha=git_sha,
        db_sha256=db_sha256,
        cases_sha256=cases_sha256,
        n_cases=len(results),
        cases_by_category=dict(Counter(r.category for r in results)),
        stops_by_layer={key: stops[key] for key in (*LAYER_ORDER, EXECUTED)},
        rules_by_layer={layer: dict(counts.most_common()) for layer, counts in rules.items()},
        isolation_by_layer={
            layer: dict(Counter(r.isolation[layer].outcome for r in results))
            for layer in LAYER_ORDER
        },
        responsible_by_layer={
            layer: ResponsibleCount(
                cases=sum(layer in r.layers for r in results),
                held=sum(layer in r.layers and layer not in r.isolation_failures for r in results),
            )
            for layer in LAYER_ORDER
        },
        violations_at_executor=sum(r.violation_at_executor for r in results),
        violations_at_db=sum(r.violation_at_db for r in results),
        isolation_failures=sum(bool(r.isolation_failures) for r in results),
        unlogged_stops=sum(r.unlogged_stop for r in results),
        db_unchanged=db_unchanged,
        results=results,
    )
