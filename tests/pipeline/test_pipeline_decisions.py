"""Cheap-path routing, abstain and clarify, and when the judge is asked."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pytest
from pipeline_fakes import (
    ALL_NAMES,
    COUNT,
    FRENCH,
    OLDEST,
    FakeLLM,
    analysis,
    config,
    grammar_failure,
    run_pipeline,
    with_limit,
)

from text2sql.config import QueryMode, Settings
from text2sql.pipeline import DatabaseResources
from text2sql.pipeline import decide as decide_module
from text2sql.retrieval import QuestionAnalysis
from text2sql.selection import Cluster, ExecutedCandidate, Selection

ResourcesFactory = Callable[..., DatabaseResources]
CHEAP = {
    "question_analysis": True,
    "cheap_path": True,
    "strategies": ("small_linked", "direct_full", "query_plan"),
    "n_candidates": 3,
    "selector": "vote",
}
THREE = {
    "strategies": ("direct_full", "query_plan", "divide_conquer"),
    "n_candidates": 3,
    "selector": "vote",
}


def cheap_llm(
    settings: Settings, small: str, full: str, plan: str = FRENCH, complexity: str = "easy"
) -> FakeLLM:
    return FakeLLM(
        settings,
        sql={("small_linked", 0): [small], ("direct_full", 0): [full], ("query_plan", 0): [plan]},
        structured_values={QuestionAnalysis: analysis(complexity=complexity)},
    )


def test_cheap_path_answers_easy_questions_its_two_candidates_agree_on(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = cheap_llm(settings, FRENCH, FRENCH)

    answer, trace = run_pipeline(llm, config(**CHEAP), resources_factory())

    assert trace.cheap_path_taken
    assert answer.sql == FRENCH
    assert [c.strategy for c in trace.candidates] == ["small_linked", "direct_full"]
    assert llm.calls_for("generate.query_plan") == []
    names = [s.name for s in trace.stages]
    assert "cheap_path" in names
    assert "candidates" not in names


@pytest.mark.parametrize(
    ("small", "full", "complexity"),
    [
        (FRENCH, OLDEST, "easy"),  # the two disagree
        (FRENCH, FRENCH, "non_nested"),  # agree, but the question is not easy
        ("SELECT T1.name FROM singer AS T1 WHERE T1.country = 'Peru'", FRENCH, "easy"),  # empty
    ],
)
def test_cheap_path_escalates_and_reuses_both_cheap_candidates(
    settings: Settings,
    resources_factory: ResourcesFactory,
    small: str,
    full: str,
    complexity: str,
) -> None:
    llm = cheap_llm(settings, small, full, complexity=complexity)

    answer, trace = run_pipeline(llm, config(**CHEAP), resources_factory())

    assert not trace.cheap_path_taken
    assert [(c.index, c.strategy) for c in trace.candidates] == [
        (0, "small_linked"),
        (1, "direct_full"),
        (2, "query_plan"),
    ]
    for strategy in ("small_linked", "direct_full", "query_plan"):
        assert len(llm.calls_for(f"generate.{strategy}[")) == 1
    escalation = trace.stage("candidates")
    assert escalation is not None
    assert len(escalation.calls) == 1
    assert answer.sql == FRENCH  # the vote over all three
    assert trace.selection is not None
    assert trace.candidates[trace.selection.index or 0].sql == FRENCH


def test_most_candidates_abstaining_abstains_with_their_reason(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    reason = "no table records ticket prices"
    llm = FakeLLM(
        settings,
        sql={
            ("direct_full", 0): [with_limit(FRENCH)],
            ("query_plan", 0): [f"ABSTAIN: {reason}"],
            ("divide_conquer", 0): [f"ABSTAIN: {reason}"],
        },
    )
    res = resources_factory(mode=QueryMode.PRODUCTION)

    answer, trace = run_pipeline(llm, config(**THREE), res)

    assert answer.status == "abstained"
    assert answer.reason == reason
    assert answer.sql is None
    assert answer.confidence == pytest.approx(2 / 3)
    assert trace.selection is None
    assert [c.status for c in trace.candidates] == ["ok", "abstained", "abstained"]
    assert trace.candidates[1].abstain_reason == reason


def test_an_abstention_beats_candidates_that_all_failed(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(
        settings,
        sql={
            ("direct_full", 0): [grammar_failure()],
            ("query_plan", 0): ["ABSTAIN: ambiguous"],
            ("divide_conquer", 0): [grammar_failure("incomplete")],
        },
    )

    answer, _ = run_pipeline(llm, config(**THREE), resources_factory(mode=QueryMode.PRODUCTION))

    assert answer.status == "abstained"
    assert answer.reason == "ambiguous"


def test_candidates_scattered_over_results_ask_to_clarify(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(
        settings,
        sql={
            ("direct_full", 0): [with_limit(FRENCH)],
            ("query_plan", 0): [with_limit(ALL_NAMES)],
            ("divide_conquer", 0): [with_limit(COUNT)],
        },
    )

    answer, trace = run_pipeline(llm, config(**THREE), resources_factory(mode=QueryMode.PRODUCTION))

    assert answer.status == "clarify"
    assert answer.reason == "3 candidate queries returned 3 different results"
    assert answer.sql is None
    assert len(trace.clusters) == 3
    assert trace.selection is None


def test_benchmark_mode_never_abstains_or_asks(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(
        settings,
        sql={
            ("direct_full", 0): [FRENCH],
            ("query_plan", 0): [ALL_NAMES],
            ("divide_conquer", 0): [COUNT],
        },
    )

    answer, trace = run_pipeline(llm, config(**THREE), resources_factory())

    assert answer.status == "answered"
    assert answer.confidence == pytest.approx(1 / 3)
    assert trace.selection is not None and trace.selection.method == "vote"


def test_a_two_way_split_with_a_plurality_is_answered_in_production(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(
        settings,
        sql={
            ("direct_full", 0): [with_limit(FRENCH)],
            ("query_plan", 0): [with_limit(FRENCH)],
            ("divide_conquer", 0): [with_limit(COUNT)],
        },
    )

    answer, _ = run_pipeline(llm, config(**THREE), resources_factory(mode=QueryMode.PRODUCTION))

    assert answer.status == "answered"
    assert answer.sql == with_limit(FRENCH)
    assert answer.confidence == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    ("results", "judged"),
    [
        ([FRENCH, FRENCH, ALL_NAMES, ALL_NAMES, COUNT], True),  # top share 0.4 < 0.6
        ([FRENCH, FRENCH, FRENCH, FRENCH, COUNT], False),  # top share 0.8
        ([FRENCH] * 5, False),  # one cluster
    ],
)
def test_the_judge_runs_only_when_the_vote_is_split_below_the_threshold(
    settings: Settings,
    resources_factory: ResourcesFactory,
    monkeypatch: pytest.MonkeyPatch,
    results: list[str],
    judged: bool,
) -> None:
    asked: list[int] = []

    async def judge_select(
        llm: object, cands: Sequence[ExecutedCandidate], clusters: Sequence[Cluster], **_: Any
    ) -> Selection:
        asked.append(len(clusters))
        last = clusters[-1]
        return Selection(last.representative, "judge", 0.2, len(clusters), {}, ())

    monkeypatch.setattr(decide_module, "judge_select", judge_select)
    llm = FakeLLM(settings, sql={("direct_full", i): [sql] for i, sql in enumerate(results)})
    cfg = config(strategies=("direct_full",), n_candidates=5, selector="judge", judge_threshold=0.6)

    answer, trace = run_pipeline(llm, cfg, resources_factory())

    assert asked == ([3] if judged else [])
    assert trace.selection is not None
    if judged:
        assert trace.selection.method == "judge"
        assert answer.sql == COUNT
    else:
        assert trace.selection.method == "vote"
        assert answer.sql == FRENCH
