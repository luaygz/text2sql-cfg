"""Presets and CLI overrides: what `text2sql eval --preset X --set k=v` will run."""

from __future__ import annotations

import pytest
from pipeline_fakes import FakeLLM, config

from text2sql.config import PRESETS, Settings, apply_overrides
from text2sql.generation import STRATEGIES
from text2sql.llm import LLMClient
from text2sql.pipeline import Pipeline


def test_presets_are_the_three_named_configurations() -> None:
    assert set(PRESETS) == {"baseline", "fast", "best"}
    for name, preset in PRESETS.items():
        assert preset.name == name
        assert set(preset.strategies) <= STRATEGIES.keys()


def test_baseline_is_one_full_schema_candidate_with_nothing_else() -> None:
    baseline = PRESETS["baseline"]
    assert baseline.strategies == ("direct_full",)
    assert baseline.n_candidates == 1
    assert not (
        baseline.question_analysis
        or baseline.value_retrieval
        or baseline.schema_linking
        or baseline.repair
        or baseline.cheap_path
        or baseline.explain
    )
    assert baseline.fewshot_k == 0
    assert baseline.selector == "first"
    assert baseline.grammar


def test_every_preset_builds_a_pipeline(settings: Settings) -> None:
    llm: LLMClient = FakeLLM(settings)  # type: ignore[assignment]
    for preset in PRESETS.values():
        Pipeline(llm, preset, settings=settings)


def test_overrides_parse_by_field_type() -> None:
    cfg = apply_overrides(
        PRESETS["best"],
        {
            "n_candidates": "3",
            "repair": "false",
            "literal_check": "false",
            "judge_threshold": "0.5",
            "strategies": "query_plan, direct_full",
            "generator_effort": "high",
            "selector": "vote",
        },
    )
    assert cfg.n_candidates == 3
    assert cfg.repair is False
    assert cfg.judge_threshold == 0.5
    assert cfg.strategies == ("query_plan", "direct_full")
    assert cfg.generator_effort == "high"
    assert cfg.selector == "vote"
    assert cfg.name == "best"
    assert apply_overrides(cfg, {"generator_effort": "default"}).generator_effort is None


def test_overrides_reject_unknown_keys_bad_values_and_the_name() -> None:
    with pytest.raises(ValueError, match="unknown pipeline setting 'n'"):
        apply_overrides(PRESETS["baseline"], {"n": "3"})
    with pytest.raises(ValueError, match="unknown pipeline setting 'name'"):
        apply_overrides(PRESETS["baseline"], {"name": "mine"})
    with pytest.raises(ValueError):
        apply_overrides(PRESETS["baseline"], {"n_candidates": "0"})
    with pytest.raises(ValueError):
        apply_overrides(PRESETS["baseline"], {"selector": "best_guess"})
    with pytest.raises(ValueError):
        apply_overrides(PRESETS["baseline"], {"generator_effort": "extreme"})


def test_stages_that_need_the_analysis_cannot_run_without_it() -> None:
    with pytest.raises(ValueError, match="value_retrieval, schema_linking need question_analysis"):
        config(value_retrieval=True, schema_linking=True)
    with pytest.raises(ValueError, match="cheap_path"):
        config(cheap_path=True, n_candidates=3, strategies=("small_linked", "direct_full"))
    with pytest.raises(ValueError, match="fewshot_k > 0"):
        config(fewshot_k=2)


def test_grammar_off_needs_repair_off() -> None:
    with pytest.raises(ValueError, match="grammar=false needs repair=false"):
        apply_overrides(PRESETS["best"], {"grammar": "false"})
    off = apply_overrides(
        PRESETS["best"], {"grammar": "false", "repair": "false", "literal_check": "false"}
    )
    assert not off.grammar


def test_unknown_strategy_or_missing_cheap_strategy_fails_at_construction(
    settings: Settings,
) -> None:
    llm: LLMClient = FakeLLM(settings)  # type: ignore[assignment]
    with pytest.raises(ValueError, match="unknown strategies"):
        Pipeline(llm, config(strategies=("direct_fulll",)), settings=settings)
    cheap = config(
        question_analysis=True,
        schema_linking=True,
        cheap_path=True,
        n_candidates=3,
        selector="vote",
        strategies=("small_linked", "query_plan"),
    )
    with pytest.raises(ValueError, match="cheap_path needs 'direct_full'"):
        Pipeline(llm, cheap, settings=settings)
