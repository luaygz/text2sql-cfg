"""Per-call cost from the price table in config/pricing.yaml.

Prices are configuration: nothing in this module knows a dollar figure. Cost follows the
prompt-caching guide's formula, where `input_tokens` already includes cached and cache-write
tokens and reasoning tokens are billed as output tokens.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field

from text2sql.config import get_settings
from text2sql.llm.types import PricingError, Usage

_PER_TOKEN = 1e-6
log = structlog.get_logger(__name__)


class Rates(BaseModel):
    """USD per 1M tokens. A missing cache rate means the model has no discounted rate for that
    token class, so those tokens bill at the input rate; a missing output rate means the model
    produces no output tokens (embeddings)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: float = Field(ge=0)
    cached_input: float | None = Field(default=None, ge=0)
    cache_write: float | None = Field(default=None, ge=0)
    output: float | None = Field(default=None, ge=0)


class ModelPrice(Rates):
    long_context: Rates | None = None


class PriceTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    verified: date
    long_context_threshold_tokens: int = Field(gt=0)
    tier_multipliers: dict[str, float]
    models: dict[str, ModelPrice]

    @classmethod
    def load(cls, path: Path) -> PriceTable:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def rates(self, model: str, input_tokens: int) -> Rates:
        """Rates for a call with `input_tokens` input. Models without a long-context entry
        (embeddings) bill one rate at any length."""
        try:
            price = self.models[model]
        except KeyError:
            raise PricingError(f"model {model!r} has no entry in the price table") from None
        if input_tokens > self.long_context_threshold_tokens and price.long_context is not None:
            return price.long_context
        return price

    def multiplier(self, service_tier: str) -> float:
        """Multiplier for the tier a response reports. An unlisted tier is priced at the most
        expensive listed multiplier, so an unexpected tier can only overstate spend."""
        try:
            return self.tier_multipliers[service_tier]
        except KeyError:
            worst = max(self.tier_multipliers.values())
            log.warning("pricing.unknown_tier", service_tier=service_tier, multiplier=worst)
            return worst

    def cost_usd(self, model: str, usage: Usage, service_tier: str) -> float:
        rates = self.rates(model, usage.input_tokens)
        uncached = usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens
        if uncached < 0:
            raise PricingError(f"cached plus cache-write tokens exceed input tokens: {usage}")
        if usage.output_tokens and rates.output is None:
            raise PricingError(f"{model!r} has no output rate but reported output tokens")
        cached_rate = rates.input if rates.cached_input is None else rates.cached_input
        write_rate = rates.input if rates.cache_write is None else rates.cache_write
        dollars_per_million = (
            uncached * rates.input
            + usage.cached_tokens * cached_rate
            + usage.cache_write_tokens * write_rate
            + usage.output_tokens * (rates.output or 0.0)
        )
        return dollars_per_million * _PER_TOKEN * self.multiplier(service_tier)

    def max_cost_usd(
        self, model: str, *, input_tokens: int, output_tokens: int, service_tier: str
    ) -> float:
        """Upper bound for a call: every input token at the dearer of the input and cache-write
        rates, and the full output allowance."""
        rates = self.rates(model, input_tokens)
        input_rate = max(rates.input, rates.cache_write or 0.0)
        output_rate = rates.output or 0.0
        return (
            (input_tokens * input_rate + output_tokens * output_rate)
            * _PER_TOKEN
            * self.multiplier(service_tier)
        )


@lru_cache(maxsize=4)
def load_prices(path: Path | None = None) -> PriceTable:
    """The price table at `path`, default `Settings.pricing_path`."""
    return PriceTable.load(path or get_settings().pricing_path)
