from __future__ import annotations

from pathlib import Path

import pytest

from text2sql.llm.budget import LedgerEntry, RunBudget, SpendLedger, spend_report
from text2sql.llm.types import BudgetExceeded


def entry(
    cost: float, *, phase: str = "dev", model: str = "gpt-6-luna", run: str = "r1"
) -> LedgerEntry:
    return LedgerEntry(
        run_id=run,
        phase=phase,
        purpose="test",
        model=model,
        service_tier="flex",
        input_tokens=100,
        cached_tokens=10,
        cache_write_tokens=20,
        output_tokens=30,
        reasoning_tokens=5,
        cost_usd=cost,
        latency_s=0.5,
        request_hash="h",
    )


def budget(ledger: SpendLedger, *, run_cap: float = 1.0, lifetime_cap: float = 10.0) -> RunBudget:
    return RunBudget(
        run_cap_usd=run_cap, lifetime_cap_usd=lifetime_cap, ledger=ledger, run_id="r2", phase="dev"
    )


def test_ledger_appends_one_row_per_charge(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "runs" / "spend_ledger.jsonl")
    b = budget(ledger)
    for cost in (0.1, 0.2):
        b.charge(b.reserve(0.3, purpose="t"), entry(cost))
    rows = list(ledger.entries())
    assert [r.cost_usd for r in rows] == [0.1, 0.2]
    assert len(ledger.path.read_text().splitlines()) == 2
    assert b.spent_usd == pytest.approx(0.3)
    assert b.reserved_usd == 0.0


def test_in_flight_reservations_count_against_the_run_cap(tmp_path: Path) -> None:
    b = budget(SpendLedger(tmp_path / "l.jsonl"), run_cap=1.0)
    first = b.reserve(0.6, purpose="a")
    with pytest.raises(BudgetExceeded, match="run r2"):
        b.reserve(0.6, purpose="b")
    b.release(first)
    b.reserve(0.6, purpose="b")


def test_spend_plus_estimate_over_run_cap_aborts_before_the_call(tmp_path: Path) -> None:
    b = budget(SpendLedger(tmp_path / "l.jsonl"), run_cap=0.5)
    b.charge(b.reserve(0.4, purpose="a"), entry(0.45))
    with pytest.raises(BudgetExceeded):
        b.reserve(0.06, purpose="next")
    b.reserve(0.04, purpose="small enough")


def test_lifetime_cap_includes_earlier_runs_in_the_ledger(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "l.jsonl")
    ledger.append(entry(9.5, run="old"))
    b = budget(ledger, run_cap=5.0, lifetime_cap=10.0)
    assert b.prior_spend_usd == pytest.approx(9.5)
    with pytest.raises(BudgetExceeded, match="lifetime"):
        b.reserve(0.6, purpose="x")
    b.reserve(0.4, purpose="x")


def test_summary_counts_cache_hits_separately_from_spend(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "l.jsonl")
    ledger.append(entry(1.0, run="old"))
    b = budget(ledger)
    b.charge(b.reserve(0.1, purpose="a"), entry(0.05))
    b.record_cache_hits("gpt-6-luna", 3, 0.15)
    summary = b.summary()
    luna = summary.by_model["gpt-6-luna"]
    assert (luna.api_calls, luna.cache_hits) == (1, 3)
    assert luna.cost_usd == pytest.approx(0.05)
    assert luna.priced_cache_hits_usd == pytest.approx(0.15)
    assert summary.lifetime_spent_usd == pytest.approx(1.05)
    assert "3 cache hits" in summary.render()
    assert len(list(ledger.entries())) == 2


def test_spend_report_groups_by_phase_and_model(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "l.jsonl")
    ledger.append(entry(0.1, phase="dev"))
    ledger.append(entry(0.2, phase="dev"))
    ledger.append(entry(0.4, phase="dev", model="gpt-6.1-sol"))
    ledger.append(entry(1.0, phase="eval-test"))
    report = spend_report(ledger.path)
    groups = {(r.phase, r.model): (r.calls, round(r.cost_usd, 6)) for r in report.rows}
    assert groups == {
        ("dev", "gpt-6-luna"): (2, 0.3),
        ("dev", "gpt-6.1-sol"): (1, 0.4),
        ("eval-test", "gpt-6-luna"): (1, 1.0),
    }
    assert report.total_usd == pytest.approx(1.7)
    assert "eval-test" in report.render()


def test_missing_ledger_means_no_prior_spend(tmp_path: Path) -> None:
    assert SpendLedger(tmp_path / "absent.jsonl").total_usd() == 0.0
    assert spend_report(tmp_path / "absent.jsonl").rows == []
