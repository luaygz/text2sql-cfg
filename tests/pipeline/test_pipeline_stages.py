"""Stage flags, the trace the eval runner reads, progress events, and error propagation.

Generation, the guard (with the real sandboxed executor) and selection are the real modules;
only the LLM and the retrieval indexes are scripted."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import pytest
from pipeline_fakes import (
    FRENCH,
    OLDEST,
    FakeLLM,
    StubFewShotIndex,
    StubValueIndex,
    analysis,
    call_meta,
    config,
    linker,
    request,
    run_pipeline,
)

from text2sql.config import QueryMode, Settings
from text2sql.llm import BudgetExceeded, StructuredCallFailed
from text2sql.pipeline import DatabaseResources, PipelineEvent
from text2sql.pipeline import pipeline as pipeline_module
from text2sql.pipeline.answer import Explanation
from text2sql.retrieval import FewShotExample, QuestionAnalysis
from text2sql.safety import ScopeContext

ResourcesFactory = Callable[..., DatabaseResources]

RETRIEVAL = {
    "question_analysis": True,
    "value_retrieval": True,
    "schema_linking": True,
    "fewshot_k": 1,
}
FEWSHOT = FewShotExample(
    "How many concerts were there?", None, "SELECT COUNT(*) FROM concert AS T1"
)


def test_baseline_runs_one_full_schema_candidate_and_nothing_else(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, sql={("direct_full", 0): [FRENCH]})

    answer, trace = run_pipeline(llm, config(), res)

    assert answer.status == "answered"
    assert answer.sql == FRENCH
    assert answer.preview is not None
    assert answer.preview.rows == [["Ada"], ["Cy"]]
    assert answer.preview.row_count == 2
    assert answer.schema_elements == ["singer.country", "singer.name"]
    assert answer.confidence == 1.0
    assert answer.explanation is None
    assert [s.name for s in trace.stages] == [
        "resources",
        "grammars",
        "candidates",
        "selection",
        "answer",
    ]
    assert len(llm.purposes) == 1
    assert llm.purposes[0].startswith("generate.direct_full[")
    assert trace.analysis is None
    assert trace.linked_columns is None
    assert trace.grammars["linked"].fingerprint == res.full_grammar.fingerprint
    assert trace.grammars["full"].fingerprint == res.full_grammar.fingerprint
    assert trace.selection is not None
    assert (trace.selection.method, trace.selection.index) == ("first", 0)
    candidate = trace.candidates[0]
    assert candidate.status == "ok"
    assert candidate.grammar_ok
    assert candidate.executed_sql == FRENCH
    assert candidate.params == {}
    assert candidate.row_count == 2
    assert candidate.repairs == 0
    assert candidate.fingerprint is not None
    assert (trace.grammar_calls, trace.grammar_failures) == (1, 0)
    assert trace.cost_usd == pytest.approx(0.01)
    assert trace.model_latency_s == pytest.approx(1.0)
    assert trace.safety_events == []


def test_retrieval_stages_feed_the_strategies_that_use_them(
    settings: Settings, resources_factory: ResourcesFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = resources_factory(value_index=StubValueIndex({("singer", "country"): ["France"]}))
    fewshots = StubFewShotIndex([FEWSHOT])
    monkeypatch.setattr(pipeline_module, "_fewshot_index", lambda pool: fewshots)
    monkeypatch.setattr(pipeline_module, "link_schema", linker({"singer": ["name", "country"]}))
    llm = FakeLLM(
        settings,
        sql={("direct_linked_fewshot", 0): [FRENCH], ("direct_full", 0): [FRENCH]},
        structured_values={QuestionAnalysis: analysis(skeleton="which <column> are from <value>")},
    )
    cfg = config(
        **RETRIEVAL,
        strategies=("direct_linked_fewshot", "direct_full"),
        n_candidates=2,
        selector="vote",
    )

    answer, trace = run_pipeline(llm, cfg, res)

    assert answer.status == "answered"
    assert [s.name for s in trace.stages] == [
        "resources",
        "analysis",
        "values",
        "linking",
        "fewshots",
        "grammars",
        "candidates",
        "selection",
        "answer",
    ]
    assert fewshots.skeletons == ["which <column> are from <value>"]
    assert trace.matches == {("singer", "country"): ["France"]}
    assert trace.linked_columns == frozenset(
        {("singer", "singer_id"), ("singer", "name"), ("singer", "country")}
    )
    assert trace.grammars["linked"].fingerprint != trace.grammars["full"].fingerprint
    assert trace.grammars["linked"].built_from == "linked"
    # Embedding first, then the two selection passes at once: 0.5 + max(2.0, 3.0).
    linking = trace.stage("linking")
    assert linking is not None
    assert linking.model_latency_s == pytest.approx(3.5)
    prompts = dict(zip(llm.purposes, llm.messages, strict=True))
    linked_prompt = next(m for p, m in prompts.items() if p.startswith("generate.direct_linked"))
    full_prompt = next(m for p, m in prompts.items() if p.startswith("generate.direct_full"))
    linked_user = linked_prompt[-1].text
    assert "France" in linked_user
    assert FEWSHOT.question in linked_user
    assert FEWSHOT.question not in full_prompt[-1].text
    assert "# Table: concert" not in linked_prompt[0].text  # unlinked table left out
    assert "# Table: concert" in full_prompt[0].text
    stage_calls = {s.name: len(s.calls) for s in trace.stages}
    assert stage_calls == {
        "resources": 0,
        "analysis": 1,
        "values": 1,
        "linking": 3,
        "fewshots": 1,
        "grammars": 0,
        "candidates": 2,
        "selection": 0,
        "answer": 0,
    }
    assert len(trace.calls) == 8


def test_failed_question_analysis_skips_the_stages_that_need_it(
    settings: Settings, resources_factory: ResourcesFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = resources_factory(value_index=StubValueIndex())
    monkeypatch.setattr(pipeline_module, "link_schema", linker({"singer": None}))
    failure = StructuredCallFailed(
        "refusal", "no", meta=call_meta("retrieval.analysis", "gpt-6-luna"), raw_text=None
    )
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [FRENCH]},
        structured_values={QuestionAnalysis: failure},
    )
    cfg = config(question_analysis=True, value_retrieval=True, schema_linking=True)

    answer, trace = run_pipeline(llm, cfg, res)

    assert answer.status == "answered"
    assert "analysis" in [s.name for s in trace.stages]
    assert not {"values", "linking"} & {s.name for s in trace.stages}
    assert trace.analysis is None
    assert trace.linked_columns is None
    assert any("question analysis failed" in w for w in trace.warnings)
    assert len(trace.calls) == 2  # the failed analysis is still paid for


def test_generator_effort_override_applies_to_generator_strategies_only(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, sql={("direct_full", 0): [FRENCH], ("small_linked", 0): [FRENCH]})
    cfg = config(
        strategies=("direct_full", "small_linked"),
        n_candidates=2,
        selector="vote",
        generator_effort="high",
    )

    _, trace = run_pipeline(llm, cfg, res)

    efforts = {c.strategy: (c.model, c.effort) for c in trace.candidates}
    assert efforts["direct_full"] == (settings.generator_model, "high")
    assert efforts["small_linked"] == (settings.small_model, "low")


def test_concurrent_candidates_count_the_slowest_toward_model_latency(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [FRENCH], ("query_plan", 0): [FRENCH]},
        latencies={"direct_full": 1.0, "query_plan": 3.0},
    )
    cfg = config(strategies=("direct_full", "query_plan"), n_candidates=2, selector="vote")

    answer, trace = run_pipeline(llm, cfg, res)

    assert answer.confidence == 1.0
    assert trace.model_latency_s == pytest.approx(3.0)
    assert trace.cost_usd == pytest.approx(0.02)
    # Both use the database's full-schema prompt prefix: the second waited for the first to
    # write the prompt cache, and the wait is not model latency.
    assert [c.gate_wait_s > 0 for c in trace.candidates] == [False, True]


def test_explanation_uses_the_small_model_without_result_rows(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [FRENCH]},
        structured_values={Explanation: Explanation(explanation="Lists the French singers.")},
    )

    answer, trace = run_pipeline(llm, config(explain=True), res)

    assert answer.explanation == "Lists the French singers."
    explain = trace.stage("explain")
    assert explain is not None
    assert [c.purpose for c in explain.calls] == ["answer.explain"]
    assert explain.calls[0].model == settings.small_model
    assert trace.prompt_tags == ["explain@1.0"]
    sent = "\n".join(m.text for m in llm.messages[-1])
    assert FRENCH in sent
    assert "Ada" not in sent  # database values never reach the explanation call


def test_events_cover_every_stage_and_candidate(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, sql={("direct_full", 0): [FRENCH], ("query_plan", 0): [OLDEST]})
    cfg = config(strategies=("direct_full", "query_plan"), n_candidates=2, selector="vote")
    events: list[PipelineEvent] = []

    answer, trace = run_pipeline(llm, cfg, res, on_event=events.append)

    started = [e.stage for e in events if e.status == "started"]
    finished = [e.stage for e in events if e.status == "finished"]
    assert started == finished == [s.name for s in trace.stages]
    candidates = [e.data for e in events if e.stage == "candidate"]
    assert sorted((d["index"], d["strategy"], d["status"]) for d in candidates) == [
        (0, "direct_full", "ok"),
        (1, "query_plan", "ok"),
    ]
    infos = [e.data for e in events if e.stage == "selection" and e.status == "info"]
    assert len(infos[0]["clusters"]) == 2  # type: ignore[arg-type]
    assert infos[1]["method"] == "vote"
    final = events[-1]
    assert (final.stage, final.status) == ("answer", "finished")
    assert final.data["answer"] == answer.model_dump(mode="json")
    assert final.data["cost_usd"] == pytest.approx(trace.cost_usd)
    assert all(b.elapsed_s >= a.elapsed_s for a, b in pairwise(events))


def test_a_failing_event_callback_does_not_change_the_answer(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, sql={("direct_full", 0): [FRENCH]})

    def broken(event: PipelineEvent) -> None:
        raise RuntimeError("viewer went away")

    answer, _ = run_pipeline(llm, config(), res, on_event=broken)

    assert answer.status == "answered"
    assert answer.sql == FRENCH


def test_budget_exhaustion_propagates_as_itself(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [FRENCH], ("query_plan", 0): [BudgetExceeded("run cap")]},
    )
    cfg = config(strategies=("direct_full", "query_plan"), n_candidates=2, selector="vote")

    with pytest.raises(BudgetExceeded, match="run cap"):
        run_pipeline(llm, cfg, res)


def test_scope_is_required_in_tenant_mode_and_refused_elsewhere(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, sql={("direct_full", 0): [FRENCH]})

    with pytest.raises(ValueError, match="does not scope"):
        run_pipeline(llm, config(), res, request(scope=ScopeContext(tenant_id=1)))
    with pytest.raises(ValueError, match="needs the caller's ScopeContext"):
        run_pipeline(llm, config(), res, request(QueryMode.TENANT))
    assert llm.purposes == []
