"""Synthetic evaluation records for the harness tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from text2sql.evals.records import (
    CandidateRecord,
    QuestionRecord,
    RunRecord,
    SpendSummary,
)

T0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)


def candidate(correct: bool | None = True, **kw: Any) -> CandidateRecord:
    fields: dict[str, Any] = {
        "strategy": "direct",
        "model": "gpt-6.1-sol",
        "effort": "low",
        "sql": "SELECT 1",
        "grammar_ok": True,
        "correct": correct,
        "cost_usd": 0.001,
        "latency_s": 1.0,
    }
    fields.update(kw)
    return CandidateRecord(**fields)


def question(
    qid: str | int,
    correct: bool,
    *,
    candidates: list[bool | None] | None = None,
    **kw: Any,
) -> QuestionRecord:
    """A BIRD Mini-Dev dev question; `candidates` lists per-candidate correctness."""
    outcomes = [correct] if candidates is None else candidates
    fields: dict[str, Any] = {
        "dataset": "bird_minidev",
        "split": "dev",
        "question_id": str(qid),
        "db_id": "california_schools",
        "question": f"Question {qid}?",
        "evidence": "free rate = `Free Meal Count (K-12)` / `Enrollment (K-12)`",
        "gold_sql": "SELECT 1",
        "difficulty": "simple",
        "with_evidence": True,
        "candidates": [candidate(c) for c in outcomes],
        "selected_index": 0 if outcomes else None,
        "final_sql": "SELECT 1" if outcomes else None,
        "correct": correct,
        "cost_usd": 0.01,
        "latency_s": 2.0,
    }
    fields.update(kw)
    return QuestionRecord(**fields)


def spend() -> SpendSummary:
    return SpendSummary(
        billed_usd=0.5,
        priced_usd=1.25,
        budget_usd=30.0,
        calls=40,
        cache_hits=10,
        input_tokens=50_000,
        cached_tokens=20_000,
        output_tokens=8_000,
        reasoning_tokens=5_000,
    )


def run(run_id: str = "run-0001", minutes: int = 0, **kw: Any) -> RunRecord:
    fields: dict[str, Any] = {
        "run_id": run_id,
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "timestamp": T0 + timedelta(minutes=minutes),
        "config_name": "best",
        "config": {"n_candidates": 5, "schema_linking": True},
        "n_candidates": 5,
        "effort": "low",
        "dataset": "bird_minidev",
        "split": "dev",
        "with_evidence": True,
        "questions_planned": 10,
        "partial": False,
        "spend": spend(),
    }
    fields.update(kw)
    return RunRecord(**fields)
