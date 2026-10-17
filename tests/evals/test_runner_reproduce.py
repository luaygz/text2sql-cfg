"""Reproduction: a replay must match the committed report exactly, or say what differs."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from runner_fakes import (
    FRESNO,
    SCHOOLS,
    T0,
    FakeResources,
    FakeSystem,
    FakeTrace,
    Script,
    answered,
    finish,
    item,
    make_db,
    offline_settings,
    plan,
    run_with,
)

from text2sql.evals.datasets import BirdItem, EvalItem
from text2sql.evals.registry import RegisteredReport, load_registry
from text2sql.evals.report import regenerate_results_md, write_report
from text2sql.evals.reproduce import Reproduction, reproduce_report, results_md_problem
from text2sql.llm import CacheMiss
from text2sql.pipeline import Answer, Request

BIRCH_ONLY = "SELECT name FROM schools WHERE name = 'Birch'"


@pytest.fixture
def items(tmp_path: Path) -> list[BirdItem]:
    db = make_db(tmp_path / "minidev" / "schools.sqlite", SCHOOLS)
    return [item(db, qid=str(i)) for i in range(1, 4)]


def system_for(items: list[BirdItem], script: Script) -> FakeSystem:
    return FakeSystem(script, {"schools": FakeResources.of(items[0].gold_db, "schools")})


def recorded_report(tmp_path: Path, items: list[BirdItem]) -> RegisteredReport:
    """A committed report in which every question was answered correctly."""
    run_plan = plan(items)
    outcome = run_with(system_for(items, lambda _: answered(FRESNO)), run_plan,
                       offline_settings(tmp_path))  # fmt: skip
    finish(run_plan, outcome, tmp_path)
    (entry,) = load_registry(tmp_path / "reports")
    return entry


def replay(
    entry: RegisteredReport, items: list[BirdItem], script: Script, tmp_path: Path
) -> Reproduction:
    def items_for(*_: object) -> list[EvalItem]:
        return list(items)

    return asyncio.run(
        reproduce_report(
            entry, settings=offline_settings(tmp_path), items_for=items_for,
            open_system=lambda *_: system_for(items, script),
        )
    )  # fmt: skip


def test_identical_replay_matches(tmp_path: Path, items: list[BirdItem]) -> None:
    entry = recorded_report(tmp_path, items)
    result = replay(entry, items, lambda _: answered(FRESNO), tmp_path)
    assert (result.status, result.problems, result.questions) == ("match", (), 3)


def test_a_changed_answer_is_a_mismatch_naming_the_question(
    tmp_path: Path, items: list[BirdItem]
) -> None:
    entry = recorded_report(tmp_path, items)

    def drifted(request: Request) -> tuple[Answer, FakeTrace]:
        return answered(BIRCH_ONLY if request.question_id == "2" else FRESNO)

    result = replay(entry, items, drifted, tmp_path)
    assert result.status == "mismatch"
    assert len(result.problems) == 1
    assert result.problems[0].startswith("schools/2:")
    assert "correct True -> False" in result.problems[0]


def test_cost_drift_alone_is_a_mismatch(tmp_path: Path, items: list[BirdItem]) -> None:
    """Same answers, different list-price cost (e.g. a pricing change): numbers moved."""
    entry = recorded_report(tmp_path, items)
    result = replay(entry, items, lambda _: answered(FRESNO, cost_usd=0.03), tmp_path)
    assert result.status == "mismatch"
    assert all("cost_usd" in p for p in result.problems)


def test_a_cache_miss_is_reported(tmp_path: Path, items: list[BirdItem]) -> None:
    entry = recorded_report(tmp_path, items)

    def miss(_: Request) -> tuple[Answer, FakeTrace]:
        raise CacheMiss("0123456789abcdef", "generation.direct_full")

    result = replay(entry, items, miss, tmp_path)
    assert result.status == "cache_miss"
    assert "generation.direct_full" in result.problems[0]


def test_a_question_dropped_from_the_dataset_is_a_mismatch(
    tmp_path: Path, items: list[BirdItem]
) -> None:
    entry = recorded_report(tmp_path, items)
    result = replay(entry, items[:2], lambda _: answered(FRESNO), tmp_path)
    assert result.status == "mismatch"
    assert result.problems == ("questions no longer in the dataset: 3",)


def test_reproduce_refuses_online_settings(tmp_path: Path, items: list[BirdItem]) -> None:
    entry = recorded_report(tmp_path, items)
    online = offline_settings(tmp_path).model_copy(update={"offline": False})
    with pytest.raises(ValueError, match="offline"):
        asyncio.run(reproduce_report(entry, settings=online))


def test_results_md_must_match_the_reports(tmp_path: Path, items: list[BirdItem]) -> None:
    recorded_report(tmp_path, items)
    reports, results = tmp_path / "reports", tmp_path / "RESULTS.md"
    assert results_md_problem(reports_dir=reports, results_md=results) is None
    results.write_text(results.read_text() + "\nhand-edited\n")
    assert "out of date" in (results_md_problem(reports_dir=reports, results_md=results) or "")
    results.unlink()
    assert "missing" in (results_md_problem(reports_dir=reports, results_md=results) or "")


def test_results_md_check_renders_the_secondary_presets_too(
    tmp_path: Path, items: list[BirdItem]
) -> None:
    entry = recorded_report(tmp_path, items)
    reports, results = tmp_path / "reports", tmp_path / "RESULTS.md"
    fast = entry.run.model_copy(
        update={"config_name": "fast", "run_id": "r-fast", "timestamp": T0 + timedelta(minutes=5)}
    )
    write_report(fast, entry.questions, reports_dir=reports)
    regenerate_results_md(reports_dir=reports, output=results)
    assert "## The `fast` preset" in results.read_text()
    assert results_md_problem(reports_dir=reports, results_md=results) is None
