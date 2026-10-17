"""BIRD scoring, the Arcwise release split, partial runs, the held-out guard, report placement."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from runner_fakes import (
    FRESNO,
    SCHOOLS,
    T0,
    FakeCandidate,
    FakeResources,
    FakeSystem,
    FakeTrace,
    answered,
    finish,
    item,
    make_db,
    offline_settings,
    plan,
    resources_for,
    run_with,
)

from text2sql.config import PRESETS, get_settings
from text2sql.evals import runner as runner_module
from text2sql.evals.datasets import BirdItem, load_items, sample_items
from text2sql.evals.records import QuestionRecord
from text2sql.evals.registry import RESULTS_FILE, load_registry, read_report
from text2sql.evals.runner import (
    HeldOutSplitError,
    RunAbortedError,
    RunOutcome,
    RunPlan,
    configure,
    plan_run,
    record_held_out_run,
)
from text2sql.evals.scoring import RunContext, score_bird
from text2sql.llm import BudgetExceeded
from text2sql.pipeline import Answer, Request

EXTRA_DEV_ROW = "INSERT INTO schools VALUES (4, 'Dogwood', 'Fresno', 80);"
RUN = RunContext("bird_minidev", "dev", with_evidence=True)


@pytest.fixture
def minidev_db(tmp_path: Path) -> Path:
    return make_db(tmp_path / "minidev" / "schools.sqlite", SCHOOLS)


@pytest.fixture
def dev_db(tmp_path: Path) -> Path:
    """The same database in the BIRD Dev release, which has one more Fresno school."""
    return make_db(tmp_path / "dev" / "schools.sqlite", SCHOOLS + EXTRA_DEV_ROW)


def score(
    bird_item: BirdItem, outcome: tuple[Answer, FakeTrace], run: RunContext = RUN
) -> tuple[QuestionRecord, FakeSystem]:
    system = FakeSystem(lambda _: outcome, resources_for(bird_item.gold_db))
    record = asyncio.run(score_bird(bird_item, system.ask, system.resources("schools"), run))
    return record, system


class TestBirdScoring:
    def test_final_sql_uses_official_set_semantics(self, minidev_db: Path) -> None:
        record, _ = score(item(minidev_db), answered(FRESNO + " ORDER BY name DESC"))
        assert record.correct
        assert record.gold_preview is None, "previews are only kept for failures"

    def test_every_executed_candidate_is_scored_but_rejected_ones_never_count(
        self, minidev_db: Path
    ) -> None:
        right = FakeCandidate(FRESNO + " ORDER BY name")
        extra_column = FakeCandidate("SELECT name, city FROM schools WHERE city = 'Fresno'")
        rejected = FakeCandidate(FRESNO, status="guard_rejected", validator_error="x: y")
        outcome = answered(extra_column.sql or "", right, extra_column, rejected, index=1)
        record, _ = score(item(minidev_db), outcome)

        assert [c.correct for c in record.candidates] == [True, False, False]
        assert record.selected_index == 1
        assert not record.correct
        assert record.pass_at_n, "the oracle sees the right candidate the selector missed"
        assert record.candidates[2].validator_error == "x: y"
        assert record.gold_preview is not None and record.gold_preview.row_count == 2
        assert record.predicted_preview is not None
        assert record.predicted_preview.columns == ["name", "city"]

    def test_gold_columns_linking_and_grammar_coverage(self, minidev_db: Path) -> None:
        outcome = answered(FRESNO, linked_columns=frozenset({("schools", "name")}))
        record, _ = score(item(minidev_db), outcome)
        assert record.gold_columns == [("schools", "city"), ("schools", "name")]
        assert record.linking_recall == 0.5
        assert record.gold_in_grammar is True

    def test_gold_outside_the_grammar_is_reported(self, minidev_db: Path) -> None:
        two_statements = "SELECT name FROM schools; SELECT 1"
        record, _ = score(item(minidev_db, gold=two_statements), answered(FRESNO))
        assert record.gold_in_grammar is False

    def test_evidence_is_withheld_from_the_pipeline_but_kept_in_the_record(
        self, minidev_db: Path
    ) -> None:
        run = RunContext("bird_minidev", "dev", with_evidence=False)
        record, system = score(item(minidev_db), answered(FRESNO), run)
        assert system.asked[0].evidence is None
        assert record.evidence == "Fresno is a city"
        assert not record.with_evidence

    def test_no_answer_scores_zero_with_the_gold_preview(self, minidev_db: Path) -> None:
        failed = Answer(
            status="failed", sql=None, preview=None, explanation=None, schema_elements=[],
            confidence=0.0, reason="all candidates failed",
        )  # fmt: skip
        record, _ = score(item(minidev_db), (failed, answered(FRESNO)[1]))
        assert not record.correct and record.final_sql is None and record.selected_index is None
        assert record.gold_preview is not None and record.predicted_preview is None

    def test_cost_and_latency_come_from_the_trace(self, minidev_db: Path) -> None:
        record, _ = score(item(minidev_db), answered(FRESNO, cost_usd=0.5, model_latency_s=7.0))
        assert (record.cost_usd, record.latency_s) == (0.5, 7.0)


class TestArcwiseRelease:
    def test_prediction_is_scored_on_the_gold_items_release(
        self, minidev_db: Path, dev_db: Path
    ) -> None:
        """`SELECT 3` equals the Fresno count only on the Dev copy, which has a fourth school."""
        gold = "SELECT COUNT(*) FROM schools WHERE city = 'Fresno'"
        on_dev, _ = score(item(dev_db, gold=gold), answered("SELECT 3"))
        on_minidev, _ = score(item(minidev_db, gold=gold), answered("SELECT 3"))
        assert on_dev.correct and not on_minidev.correct

    def test_original_label_is_suspect_when_the_correction_changes_the_result(
        self, minidev_db: Path
    ) -> None:
        corrected = FRESNO + " AND enrollment > 200"
        suspect, _ = score(item(minidev_db, alternate_gold=corrected), answered(FRESNO))
        reworded = "SELECT name FROM schools AS T1 WHERE T1.city = 'Fresno'"
        same, _ = score(item(minidev_db, alternate_gold=reworded), answered(FRESNO))
        assert suspect.gold_suspect and not same.gold_suspect

    def test_final_sql_is_also_compared_with_the_arcwise_gold(self, minidev_db: Path) -> None:
        corrected = FRESNO + " AND enrollment > 200"
        reworded = "SELECT name FROM schools AS T1 WHERE T1.city = 'Fresno'"
        arcwise_right, _ = score(item(minidev_db, alternate_gold=corrected), answered(corrected))
        original_right, _ = score(item(minidev_db, alternate_gold=corrected), answered(FRESNO))
        same_golds, _ = score(item(minidev_db, alternate_gold=reworded), answered(FRESNO))
        no_arcwise, _ = score(item(minidev_db), answered(corrected))
        failed = Answer(
            status="failed", sql=None, preview=None, explanation=None, schema_elements=[],
            confidence=0.0, reason="all candidates failed",
        )  # fmt: skip
        no_sql, _ = score(item(minidev_db, alternate_gold=corrected), (failed, answered(FRESNO)[1]))

        assert not arcwise_right.correct and arcwise_right.matches_arcwise_gold is True
        assert original_right.correct and original_right.matches_arcwise_gold is False
        assert same_golds.correct and same_golds.matches_arcwise_gold is True
        assert no_arcwise.matches_arcwise_gold is None
        assert no_sql.matches_arcwise_gold is None


BIRD_DATA = get_settings().data_dir / "bird" / "mini_dev_sqlite.json"
requires_bird = pytest.mark.skipif(not BIRD_DATA.exists(), reason="BIRD data absent")


@pytest.mark.bird
@requires_bird
class TestRealBirdItems:
    def test_arcwise_items_use_dev_databases_and_reworded_inputs_only_where_changed(
        self,
    ) -> None:
        from text2sql.data.bird import load_split

        examples = {str(e.question_id): e for e in load_split("dev")}
        items = load_items("bird_arcwise", "dev")
        assert len(items) == sum(e.has_arcwise for e in examples.values())
        for it in items:
            assert isinstance(it, BirdItem)
            e = examples[it.question_id]
            assert it.gold_db.parent.parent.name == "dev_databases"
            assert it.gold_sql == e.gold_sql_arcwise
            assert it.question == (e.question_arcwise if e.arcwise_inputs_changed else e.question)

    def test_original_items_use_minidev_databases(self) -> None:
        items = load_items("bird_minidev", "dev")
        assert {it.gold_db.parent.parent.name for it in items if isinstance(it, BirdItem)} == {
            "minidev_databases"
        }

    def test_limit_is_a_stable_sample_in_dataset_order(self) -> None:
        items = load_items("bird_minidev", "dev")
        first, second = sample_items(items, 10), sample_items(items, 10)
        assert first == second and len(first) == 10
        order = [items.index(i) for i in first]
        assert order == sorted(order)
        assert len({i.db_id for i in first}) > 1


class BudgetStops(FakeSystem):
    """Question 2 is still in flight when question 3 hits the budget; 4 must never start."""

    def __init__(self, resources: dict[str, FakeResources]) -> None:
        super().__init__(lambda _: answered(FRESNO), resources)
        self.release = asyncio.Event()

    async def ask(self, request: Request) -> tuple[Answer, FakeTrace]:
        self.asked.append(request)
        if request.question_id == "1":
            return answered(FRESNO)
        if request.question_id == "2":
            await self.release.wait()
            return answered(FRESNO)
        self.release.set()
        raise BudgetExceeded("run would reach $0.31, over its $0.30 cap")


class TestPartialRuns:
    def test_budget_stop_finishes_in_flight_and_schedules_nothing_new(
        self, tmp_path: Path, minidev_db: Path
    ) -> None:
        items = [item(minidev_db, qid=str(i)) for i in range(1, 5)]
        system = BudgetStops(resources_for(minidev_db))
        outcome = run_with(system, plan(items), offline_settings(tmp_path))

        assert [q.question_id for q in outcome.questions] == ["1", "2"]
        assert [r.question_id for r in system.asked] == ["1", "2", "3"]
        assert outcome.stop_reason is not None and outcome.stop_reason.startswith("budget")
        assert system.closed

    def test_partial_run_is_reported_as_partial(self, tmp_path: Path, minidev_db: Path) -> None:
        items = [item(minidev_db, qid=str(i)) for i in range(1, 5)]
        outcome = run_with(
            BudgetStops(resources_for(minidev_db)), plan(items), offline_settings(tmp_path)
        )
        report = read_report(finish(plan(items), outcome, tmp_path) / RESULTS_FILE)
        assert report.run.partial
        assert report.run.partial_reason == outcome.stop_reason
        assert (report.run.questions_planned, report.summary.overall.n) == (4, 2)
        assert "partial: 2/4" in (tmp_path / "RESULTS.md").read_text()

    def test_a_run_stopped_before_any_answer_writes_no_report(self, tmp_path: Path) -> None:
        outcome = RunOutcome(questions=[], stop_reason="budget exceeded: lifetime cap")
        with pytest.raises(RunAbortedError, match="lifetime cap"):
            finish(plan([]), outcome, tmp_path)
        assert not (tmp_path / "reports").exists()


class TestRecordedCommit:
    START = "a" * 40

    def _recorded(self, tmp_path: Path, minidev_db: Path, monkeypatch: Any, head: str) -> str:
        monkeypatch.setattr(runner_module, "current_git_sha", lambda: head)
        items = [item(minidev_db, qid="1")]
        system = FakeSystem(lambda _: answered(FRESNO), resources_for(minidev_db))
        outcome = run_with(system, plan(items), offline_settings(tmp_path))
        directory = finish(plan(items), outcome, tmp_path, git_sha=self.START)
        return read_report(directory / RESULTS_FILE).run.git_sha

    def test_the_commit_a_run_started_at_is_recorded(
        self, tmp_path: Path, minidev_db: Path, monkeypatch: Any
    ) -> None:
        assert self._recorded(tmp_path, minidev_db, monkeypatch, head=self.START) == self.START

    def test_a_commit_made_during_the_run_marks_it_dirty(
        self, tmp_path: Path, minidev_db: Path, monkeypatch: Any
    ) -> None:
        sha = self._recorded(tmp_path, minidev_db, monkeypatch, head="b" * 40)
        assert sha == f"{self.START}-dirty"


class TestHeldOutSplit:
    @pytest.mark.parametrize("split", ["test", "all"])
    def test_test_questions_need_allow_test(self, split: Any) -> None:
        with pytest.raises(HeldOutSplitError, match="allow-test"):
            plan_run(dataset="bird_minidev", split=split, preset="baseline")

    def test_held_out_runs_are_logged(self, tmp_path: Path, minidev_db: Path) -> None:
        settings = offline_settings(tmp_path)
        test_plan = RunPlan(
            dataset="bird_minidev", split="test", preset="best", config=PRESETS["best"],
            overrides={}, with_evidence=True, items=[item(minidev_db)],
        )  # fmt: skip
        record_held_out_run(settings, "r1", test_plan, T0)
        record_held_out_run(settings, "r2", test_plan, T0)
        lines = (settings.runs_dir / "held_out_runs.jsonl").read_text().splitlines()
        assert [json.loads(line)["run_id"] for line in lines] == ["r1", "r2"]
        assert json.loads(lines[0])["split"] == "test"


class TestConfiguration:
    def test_overrides_are_recorded_typed_and_with_results_md_names(self) -> None:
        config, recorded = configure(
            "best", {"generator_effort": "high", "n_candidates": "3"}, with_evidence=False
        )
        assert recorded == {"effort": "high", "n_candidates": 3}
        assert config.n_candidates == 3 and not config.use_evidence

    def test_evidence_is_not_an_override(self) -> None:
        with pytest.raises(ValueError, match="with_evidence"):
            configure("best", {"use_evidence": "false"}, with_evidence=True)

    @pytest.mark.parametrize(
        ("overrides", "kind"),
        [
            ({}, "reference"),
            ({"n_candidates": "3"}, "n_sweep"),
            ({"generator_effort": "high"}, "effort_sweep"),
            ({"selector": "vote"}, "ablation"),
        ],
    )
    def test_overrides_decide_where_results_md_places_the_run(
        self, tmp_path: Path, minidev_db: Path, overrides: dict[str, str], kind: str
    ) -> None:
        run_plan = plan([item(minidev_db)], overrides=overrides)
        system = FakeSystem(lambda _: answered(FRESNO), resources_for(minidev_db))
        finish(run_plan, run_with(system, run_plan, offline_settings(tmp_path)), tmp_path)
        (entry,) = load_registry(tmp_path / "reports")
        assert entry.kind == kind
        assert entry.run.config["pipeline"]["name"] == "best"
