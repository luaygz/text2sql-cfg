"""The repair loop and grammar-call failures, with the real guard deciding what failed."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pipeline_fakes import (
    FRENCH,
    NOBODY,
    OFF_GRAMMAR,
    UNKNOWN_ALIAS,
    FakeLLM,
    StubValueIndex,
    analysis,
    call_meta,
    config,
    grammar_failure,
    run_pipeline,
)

from text2sql.config import Settings
from text2sql.llm import GrammarRejectedByAPI
from text2sql.pipeline import DatabaseResources
from text2sql.retrieval import QuestionAnalysis

ResourcesFactory = Callable[..., DatabaseResources]
TWO = {"strategies": ("direct_full", "query_plan"), "n_candidates": 2, "selector": "vote"}


def test_validator_rejection_is_repaired_at_most_max_repairs_times(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [UNKNOWN_ALIAS] * 4})

    answer, trace = run_pipeline(llm, config(repair=True, max_repairs=2), resources_factory())

    candidate = trace.candidates[0]
    assert len(llm.calls_for("repair.direct_full#")) == 2
    assert [a.number for a in candidate.attempts] == [0, 1, 2]
    assert candidate.repairs == 2
    assert candidate.status == "guard_rejected"
    assert candidate.validator_error is not None
    assert candidate.rejection is not None and candidate.rejection.layer == "validator"
    assert candidate.attempts[-1].feedback is None  # no repair was asked for the last one
    assert all(candidate.rejection.rule in f for f in llm.feedback)
    assert answer.status == "failed"
    assert answer.reason == "no candidate query executed (1 guard_rejected)"
    assert [e.layer for e in trace.safety_events] == ["validator"] * 3


def test_repair_stops_as_soon_as_the_query_executes(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [UNKNOWN_ALIAS, FRENCH, FRENCH]})

    answer, trace = run_pipeline(llm, config(repair=True, max_repairs=2), resources_factory())

    assert answer.sql == FRENCH
    assert trace.candidates[0].repairs == 1
    assert trace.candidates[0].status == "ok"
    assert trace.grammar_calls == 2


def test_without_repair_a_rejected_candidate_gets_one_call(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [UNKNOWN_ALIAS, FRENCH]})

    answer, trace = run_pipeline(llm, config(repair=False), resources_factory())

    assert answer.status == "failed"
    assert len(llm.purposes) == 1
    assert trace.candidates[0].repairs == 0


@pytest.mark.parametrize(("may_be_empty", "repairs"), [(False, 1), (True, 0)])
def test_empty_results_are_repaired_only_when_rows_are_expected(
    settings: Settings,
    resources_factory: ResourcesFactory,
    may_be_empty: bool,
    repairs: int,
) -> None:
    res = resources_factory(value_index=StubValueIndex({("singer", "country"): ["France"]}))
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [NOBODY, FRENCH]},
        structured_values={QuestionAnalysis: analysis(may_be_empty=may_be_empty)},
    )
    cfg = config(question_analysis=True, value_retrieval=True, repair=True, max_repairs=2)

    answer, trace = run_pipeline(llm, cfg, res)

    assert trace.candidates[0].repairs == repairs
    if repairs:
        assert answer.sql == FRENCH
        # The retrieved values of the column the empty query filtered on come back as a hint.
        assert "'France'" in llm.feedback[0]
    else:
        assert answer.status == "answered"
        assert answer.sql == NOBODY
        assert answer.preview is not None and answer.preview.row_count == 0


def test_empty_results_are_not_repaired_without_question_analysis(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [NOBODY, FRENCH]})

    answer, _ = run_pipeline(llm, config(repair=True), resources_factory())

    assert answer.sql == NOBODY
    assert llm.calls_for("repair") == []


def test_a_repair_that_breaks_an_empty_query_keeps_the_executed_attempt(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [NOBODY, UNKNOWN_ALIAS]},
        structured_values={QuestionAnalysis: analysis(may_be_empty=False)},
    )
    cfg = config(question_analysis=True, repair=True, max_repairs=1)

    answer, trace = run_pipeline(llm, cfg, resources_factory())

    candidate = trace.candidates[0]
    assert candidate.repairs == 1
    assert candidate.final.number == 0
    assert candidate.status == "empty"
    assert answer.status == "answered"
    assert answer.sql == NOBODY


def test_off_grammar_output_drops_the_candidate_and_is_a_layer_one_event(
    settings: Settings, resources_factory: ResourcesFactory, events_path: Path
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [OFF_GRAMMAR], ("query_plan", 0): [FRENCH]})

    answer, trace = run_pipeline(llm, config(**TWO, repair=True), resources_factory())

    dropped, kept = trace.candidates
    assert dropped.status == "grammar_failed"
    assert not dropped.grammar_ok
    assert dropped.sql is None
    assert dropped.attempts[0].grammar_failure is not None
    assert dropped.attempts[0].grammar_failure.startswith("local_parse")
    assert llm.calls_for("repair") == []  # never retried, with or without the grammar
    assert kept.status == "ok"
    assert answer.sql == FRENCH
    assert (trace.grammar_calls, trace.grammar_failures) == (2, 1)
    assert [(e.layer, e.rule, e.sql) for e in trace.safety_events] == [
        ("grammar", "local_parse", OFF_GRAMMAR)
    ]
    logged = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert [(e["layer"], e["context"]["strategy"]) for e in logged] == [("grammar", "direct_full")]


def test_api_grammar_rejection_counts_but_is_not_a_safety_event(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    rejected = GrammarRejectedByAPI(
        "regex construction fuel exhausted",
        fingerprint="abc",
        meta=call_meta("generate.direct_full", "gpt-6.1-sol", cost=0.0),
    )
    llm = FakeLLM(settings, sql={("direct_full", 0): [rejected], ("query_plan", 0): [FRENCH]})

    answer, trace = run_pipeline(llm, config(**TWO), resources_factory())

    assert answer.sql == FRENCH
    assert trace.grammar_failures == 1
    assert trace.safety_events == []
    assert any("rejected the full grammar" in w for w in trace.warnings)


def test_a_failed_repair_call_keeps_the_last_query(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [UNKNOWN_ALIAS, grammar_failure()]})

    answer, trace = run_pipeline(llm, config(repair=True), resources_factory())

    candidate = trace.candidates[0]
    assert len(candidate.attempts) == 2
    assert candidate.sql == UNKNOWN_ALIAS
    assert candidate.status == "guard_rejected"
    assert candidate.grammar_ok  # the final state is the last attempt that produced SQL
    assert (candidate.grammar_calls, candidate.grammar_failures) == (2, 1)
    assert answer.status == "failed"
