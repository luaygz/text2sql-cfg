"""Spend ledger and run budget.

Every billed API call appends one JSON line to the ledger (`Settings.ledger_path`). A
`RunBudget` refuses a call before it is made when its worst-case cost, added to what the run has
spent and what in-flight calls have reserved, would cross the per-run cap or the lifetime cap
(ledger total at start plus this run). Reservations make the check hold under concurrency.
Cache hits are free: they are counted in the run summary but never written to the ledger.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from text2sql.config import Settings, get_settings
from text2sql.llm.types import BudgetExceeded, Usage
from text2sql.observability import current_run_id


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str
    phase: str
    purpose: str
    model: str
    service_tier: str
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float
    latency_s: float
    request_hash: str


class SpendLedger:
    """Append-only JSONL. Each row is one `write` on a file opened in append mode, so rows from
    concurrent processes do not interleave."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, entry: LedgerEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")

    def entries(self) -> Iterator[LedgerEntry]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield LedgerEntry.model_validate_json(line)

    def total_usd(self) -> float:
        return sum(e.cost_usd for e in self.entries())


class ModelSpend(BaseModel):
    api_calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    priced_cache_hits_usd: float = 0.0
    """List-price value of the cache hits: what replaying from cache saved."""

    def add_usage(self, usage: Usage, cost_usd: float) -> None:
        self.api_calls += 1
        self.input_tokens += usage.input_tokens
        self.cached_tokens += usage.cached_tokens
        self.cache_write_tokens += usage.cache_write_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_tokens += usage.reasoning_tokens
        self.cost_usd += cost_usd


class RunSpend(BaseModel):
    run_id: str
    phase: str
    cost_usd: float
    run_cap_usd: float
    lifetime_spent_usd: float
    lifetime_cap_usd: float
    by_model: dict[str, ModelSpend]

    def render(self) -> str:
        lines = [
            f"run {self.run_id} ({self.phase}): ${self.cost_usd:.4f} of ${self.run_cap_usd:.2f} "
            f"run cap; lifetime ${self.lifetime_spent_usd:.4f} of ${self.lifetime_cap_usd:.2f}"
        ]
        for model, s in sorted(self.by_model.items()):
            lines.append(
                f"  {model}: {s.api_calls} calls, {s.cache_hits} cache hits, "
                f"in {s.input_tokens} (cached {s.cached_tokens}, written {s.cache_write_tokens}), "
                f"out {s.output_tokens} (reasoning {s.reasoning_tokens}), ${s.cost_usd:.4f}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class Reservation:
    amount_usd: float


class RunBudget:
    def __init__(
        self,
        *,
        run_cap_usd: float,
        lifetime_cap_usd: float,
        ledger: SpendLedger,
        run_id: str,
        phase: str,
    ) -> None:
        self.run_cap_usd = run_cap_usd
        self.lifetime_cap_usd = lifetime_cap_usd
        self.ledger = ledger
        self.run_id = run_id
        self.phase = phase
        self.prior_spend_usd = ledger.total_usd()
        self.spent_usd = 0.0
        self.reserved_usd = 0.0
        self._by_model: defaultdict[str, ModelSpend] = defaultdict(ModelSpend)

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None, *, run_id: str | None = None
    ) -> RunBudget:
        s = settings or get_settings()
        return cls(
            run_cap_usd=s.max_spend_usd,
            lifetime_cap_usd=s.total_spend_cap_usd,
            ledger=SpendLedger(s.ledger_path),
            run_id=run_id or current_run_id(),
            phase=s.phase,
        )

    def reserve(self, estimate_usd: float, *, purpose: str) -> Reservation:
        """Hold `estimate_usd` for one call, or raise BudgetExceeded if it does not fit."""
        committed = self.spent_usd + self.reserved_usd + estimate_usd
        if committed > self.run_cap_usd:
            raise BudgetExceeded(
                f"{purpose}: run {self.run_id} would reach ${committed:.4f}, over its "
                f"${self.run_cap_usd:.2f} cap (spent ${self.spent_usd:.4f}, "
                f"in flight ${self.reserved_usd:.4f}, next call up to ${estimate_usd:.4f})"
            )
        lifetime = self.prior_spend_usd + committed
        if lifetime > self.lifetime_cap_usd:
            raise BudgetExceeded(
                f"{purpose}: lifetime spend would reach ${lifetime:.4f}, over the "
                f"${self.lifetime_cap_usd:.2f} cap (ledger ${self.prior_spend_usd:.4f} before "
                f"this run)"
            )
        self.reserved_usd += estimate_usd
        return Reservation(estimate_usd)

    def release(self, reservation: Reservation) -> None:
        """Drop a reservation for a call that failed without being billed."""
        self.reserved_usd = max(0.0, self.reserved_usd - reservation.amount_usd)

    def charge(self, reservation: Reservation, entry: LedgerEntry) -> None:
        """Replace a reservation with the call's actual cost and write it to the ledger."""
        self.release(reservation)
        self.ledger.append(entry)
        self.spent_usd += entry.cost_usd
        usage = Usage(
            entry.input_tokens,
            entry.cached_tokens,
            entry.cache_write_tokens,
            entry.output_tokens,
            entry.reasoning_tokens,
        )
        self._by_model[entry.model].add_usage(usage, entry.cost_usd)

    def record_cache_hits(self, model: str, count: int, priced_usd: float) -> None:
        stats = self._by_model[model]
        stats.cache_hits += count
        stats.priced_cache_hits_usd += priced_usd

    def summary(self) -> RunSpend:
        return RunSpend(
            run_id=self.run_id,
            phase=self.phase,
            cost_usd=self.spent_usd,
            run_cap_usd=self.run_cap_usd,
            lifetime_spent_usd=self.prior_spend_usd + self.spent_usd,
            lifetime_cap_usd=self.lifetime_cap_usd,
            by_model={m: s.model_copy() for m, s in self._by_model.items()},
        )


class SpendRow(BaseModel):
    phase: str
    model: str
    calls: int
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float


class SpendReport(BaseModel):
    rows: list[SpendRow]
    total_usd: float

    def render(self) -> str:
        header = f"{'phase':<16} {'model':<24} {'calls':>6} {'in':>10} {'out':>10} {'usd':>10}"
        lines = [header]
        lines += [
            f"{r.phase:<16} {r.model:<24} {r.calls:>6} {r.input_tokens:>10} "
            f"{r.output_tokens:>10} {r.cost_usd:>10.4f}"
            for r in self.rows
        ]
        lines.append(f"{'total':<16} {'':<24} {'':>6} {'':>10} {'':>10} {self.total_usd:>10.4f}")
        return "\n".join(lines)


def spend_report(ledger_path: Path | None = None) -> SpendReport:
    """Ledger totals grouped by phase and model."""
    ledger = SpendLedger(ledger_path or get_settings().ledger_path)
    groups: dict[tuple[str, str], list[LedgerEntry]] = defaultdict(list)
    for entry in ledger.entries():
        groups[entry.phase, entry.model].append(entry)
    rows = [
        SpendRow(
            phase=phase,
            model=model,
            calls=len(es),
            input_tokens=sum(e.input_tokens for e in es),
            cached_tokens=sum(e.cached_tokens for e in es),
            cache_write_tokens=sum(e.cache_write_tokens for e in es),
            output_tokens=sum(e.output_tokens for e in es),
            reasoning_tokens=sum(e.reasoning_tokens for e in es),
            cost_usd=sum(e.cost_usd for e in es),
        )
        for (phase, model), es in sorted(groups.items())
    ]
    return SpendReport(rows=rows, total_usd=sum(r.cost_usd for r in rows))
