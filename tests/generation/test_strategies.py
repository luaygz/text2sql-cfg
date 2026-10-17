"""Strategy table, candidate scheduling and model tiers."""

from __future__ import annotations

import pytest

from text2sql.config import Settings
from text2sql.generation import DEFAULT_SCHEDULE, STRATEGIES, model_for, schedule
from text2sql.prompts import load_prompt

REQUIRED = {"divide_conquer", "query_plan", "direct_full", "direct_linked_fewshot", "small_linked"}


def test_required_strategies_exist_with_loadable_method_prompts() -> None:
    assert set(STRATEGIES) >= REQUIRED
    for name, spec in STRATEGIES.items():
        assert spec.name == name
        assert load_prompt(spec.prompt).render("method")
    assert STRATEGIES["direct_full"].schema_view == "full"
    assert not STRATEGIES["direct_full"].fewshots
    assert STRATEGIES["direct_linked_fewshot"].schema_view == "linked"
    assert STRATEGIES["direct_linked_fewshot"].fewshots
    assert STRATEGIES["small_linked"].model_tier == "small"


def test_default_schedule_covers_n_up_to_eight_with_every_strategy_by_five() -> None:
    assert len(DEFAULT_SCHEDULE) == 8
    assert set(DEFAULT_SCHEDULE[:5]) == REQUIRED
    picked = schedule(DEFAULT_SCHEDULE, 8)
    assert [p.strategy.name for p in picked] == list(DEFAULT_SCHEDULE)
    assert [p.sample for p in picked] == [0, 0, 0, 0, 0, 1, 1, 1]


def test_schedule_prefix_is_stable_across_n() -> None:
    eight = schedule(DEFAULT_SCHEDULE, 8)
    for n in (1, 3, 5):
        assert schedule(DEFAULT_SCHEDULE, n) == eight[:n]


def test_schedule_cycles_and_numbers_repeats() -> None:
    picked = schedule(("direct_full", "small_linked"), 5)
    assert [(p.strategy.name, p.sample) for p in picked] == [
        ("direct_full", 0),
        ("small_linked", 0),
        ("direct_full", 1),
        ("small_linked", 1),
        ("direct_full", 2),
    ]


@pytest.mark.parametrize(
    ("names", "n", "message"),
    [
        (("direct_full",), 0, "at least one"),
        ((), 3, "no strategies"),
        (("direct_full", "telepathy"), 1, "unknown strategies"),
    ],
)
def test_schedule_rejects_bad_input(names: tuple[str, ...], n: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        schedule(names, n)


def test_model_for_maps_tiers_to_configured_models() -> None:
    settings = Settings(generator_model="big-model", small_model="small-model")
    assert model_for(STRATEGIES["divide_conquer"], settings) == "big-model"
    assert model_for(STRATEGIES["small_linked"], settings) == "small-model"
