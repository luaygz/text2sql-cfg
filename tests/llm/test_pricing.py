"""Cost math against the checked-in price table. Expected dollar figures are the Standard rates
on https://developers.openai.com/api/docs/pricing.md as read on 2026-10-16."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from text2sql.llm.pricing import PriceTable
from text2sql.llm.types import PricingError, Usage

PRICES = PriceTable.load(Path(__file__).resolve().parents[2] / "config" / "pricing.yaml")
M = 1_000_000
N = 100_000  # well inside the short-context tier


def usage(
    input_tokens: int = 0, cached: int = 0, written: int = 0, output: int = 0, reasoning: int = 0
) -> Usage:
    return Usage(input_tokens, cached, written, output, reasoning)


@pytest.mark.parametrize(
    ("model", "tokens", "usd_per_million"),
    [
        ("gpt-6.1-sol", usage(input_tokens=N), 2.00),
        ("gpt-6.1-sol", usage(input_tokens=N, cached=N), 0.10),
        ("gpt-6.1-sol", usage(input_tokens=N, written=N), 2.50),
        ("gpt-6.1-sol", usage(output=N), 10.00),
        ("gpt-6-luna", usage(input_tokens=N), 0.10),
        ("gpt-6-luna", usage(input_tokens=N, cached=N), 0.01),
        ("gpt-6-luna", usage(input_tokens=N, written=N), 0.125),
        ("gpt-6-luna", usage(output=N), 0.50),
        ("text-embedding-3-small", usage(input_tokens=N), 0.02),
    ],
)
def test_each_token_class_bills_at_its_standard_rate(
    model: str, tokens: Usage, usd_per_million: float
) -> None:
    assert PRICES.cost_usd(model, tokens, "default") == pytest.approx(usd_per_million * N / M)


def test_embeddings_have_one_rate_at_any_request_size() -> None:
    big_batch = usage(input_tokens=290_000)
    assert PRICES.cost_usd("text-embedding-3-small", big_batch, "default") == pytest.approx(
        290_000 * 0.02 / M
    )


def test_mixed_call_splits_input_into_three_classes() -> None:
    # 10k input of which 6k cache reads and 2k cache writes; 1k output incl. 800 reasoning.
    mixed = usage(input_tokens=10_000, cached=6_000, written=2_000, output=1_000, reasoning=800)
    expected = (2_000 * 2.00 + 6_000 * 0.10 + 2_000 * 2.50 + 1_000 * 10.00) / M
    assert PRICES.cost_usd("gpt-6.1-sol", mixed, "default") == pytest.approx(expected)


def test_reasoning_tokens_are_not_billed_twice() -> None:
    with_reasoning = usage(output=1_000, reasoning=900)
    assert PRICES.cost_usd("gpt-6.1-sol", with_reasoning, "default") == pytest.approx(0.01)


@pytest.mark.parametrize(
    ("tier", "factor"),
    [("default", 1.0), ("auto", 1.0), ("flex", 0.5), ("batch", 0.5), ("priority", 2.0)],
)
def test_tier_multiplier_applies_to_every_token_class(tier: str, factor: float) -> None:
    mixed = usage(input_tokens=10_000, cached=6_000, written=2_000, output=1_000)
    standard = PRICES.cost_usd("gpt-6.1-sol", mixed, "default")
    assert PRICES.cost_usd("gpt-6.1-sol", mixed, tier) == pytest.approx(standard * factor)


def test_unknown_tier_is_priced_at_the_dearest_multiplier() -> None:
    tokens = usage(input_tokens=1_000, output=1_000)
    assert PRICES.cost_usd("gpt-6-luna", tokens, "ultrafast") == pytest.approx(
        PRICES.cost_usd("gpt-6-luna", tokens, "priority")
    )


def test_long_context_rates_start_above_272k_input_tokens() -> None:
    at_limit = PRICES.cost_usd("gpt-6.1-sol", usage(input_tokens=272_000), "default")
    above = PRICES.cost_usd("gpt-6.1-sol", usage(input_tokens=272_001), "default")
    assert at_limit == pytest.approx(272_000 * 2.00 / M)
    assert above == pytest.approx(272_001 * 4.00 / M)


def test_unpriceable_usage_is_an_error() -> None:
    with pytest.raises(PricingError, match="no entry"):
        PRICES.cost_usd("gpt-9", usage(input_tokens=1), "default")
    with pytest.raises(PricingError, match="exceed input"):
        PRICES.cost_usd("gpt-6-luna", usage(input_tokens=10, cached=8, written=8), "default")
    with pytest.raises(PricingError, match="no output rate"):
        PRICES.cost_usd("text-embedding-3-small", usage(input_tokens=5, output=1), "default")


@given(
    input_budget=st.integers(0, 300_000),
    output_budget=st.integers(0, 50_000),
    cached_share=st.floats(0, 1),
    written_share=st.floats(0, 1),
    used_output=st.floats(0, 1),
    tier=st.sampled_from(["default", "flex", "auto"]),
)
def test_pre_call_estimate_bounds_the_actual_cost(
    input_budget: int,
    output_budget: int,
    cached_share: float,
    written_share: float,
    used_output: float,
    tier: str,
) -> None:
    cached = int(input_budget * cached_share)
    written = int((input_budget - cached) * written_share)
    actual = usage(input_budget, cached, written, int(output_budget * used_output))
    bound = PRICES.max_cost_usd(
        "gpt-6.1-sol", input_tokens=input_budget, output_tokens=output_budget, service_tier=tier
    )
    assert PRICES.cost_usd("gpt-6.1-sol", actual, tier) <= bound + 1e-12
