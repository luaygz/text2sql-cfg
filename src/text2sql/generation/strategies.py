"""Candidate strategies (ADR-008 stage 6) and the order in which a run samples them.

Diversity comes from the strategy, the schema view, the few-shots and the model, never from
temperature (reasoning models reject it). Every gpt-6.1-sol strategy runs at medium effort: in
the live smoke (ADR-012) medium added about 15 output tokens per call over low, with the same
latency, and one effort for all full-schema strategies keeps their prompt-cache prefix shared
(the cache is partitioned by reasoning effort).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict

from text2sql.config import ReasoningEffort, Settings

SchemaView = Literal["full", "linked"]
ModelTier = Literal["generator", "small"]


class StrategySpec(BaseModel, frozen=True):
    """One way of asking for a candidate. `prompt` names the method template in `prompts/`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    prompt: str
    model_tier: ModelTier
    effort: ReasoningEffort
    schema_view: SchemaView
    fewshots: bool


_SPECS = (
    StrategySpec(
        name="divide_conquer",
        prompt="generate_divide_conquer",
        model_tier="generator",
        effort="medium",
        schema_view="full",
        fewshots=False,
    ),
    StrategySpec(
        name="query_plan",
        prompt="generate_query_plan",
        model_tier="generator",
        effort="medium",
        schema_view="full",
        fewshots=False,
    ),
    StrategySpec(
        name="direct_full",
        prompt="generate_direct",
        model_tier="generator",
        effort="medium",
        schema_view="full",
        fewshots=False,
    ),
    StrategySpec(
        name="direct_linked_fewshot",
        prompt="generate_direct",
        model_tier="generator",
        effort="medium",
        schema_view="linked",
        fewshots=True,
    ),
    StrategySpec(
        name="small_linked",
        prompt="generate_direct",
        model_tier="small",
        effort="low",
        schema_view="linked",
        fewshots=False,
    ),
)

STRATEGIES: Mapping[str, StrategySpec] = MappingProxyType({s.name: s for s in _SPECS})

DEFAULT_SCHEDULE: tuple[str, ...] = (
    "divide_conquer",
    "query_plan",
    "direct_linked_fewshot",
    "direct_full",
    "small_linked",
    "divide_conquer",
    "query_plan",
    "direct_full",
)
"""Candidate order for N = 1..8: the two strongest single generators in CHASE-SQL first, then
the input that differs most from them (linked schema with few-shots), then the full-schema
baseline and the small model. Entries 6-8 are second samples of the full-schema strategies,
whose prompt prefix is cached; a second linked sample would pay its whole prompt again."""


@dataclass(frozen=True)
class ScheduledCandidate:
    strategy: StrategySpec
    sample: int
    """0 for a strategy's first candidate in a run, 1 for its second, ...; it separates the
    response-cache keys of otherwise identical requests."""


def schedule(names: Sequence[str], n: int) -> list[ScheduledCandidate]:
    """The first `n` candidates of a run that cycles through `names`.

    A name that comes round again gets the next sample index, so `schedule(("a", "b"), 3)` is
    a/0, b/0, a/1.
    """
    if n < 1:
        raise ValueError(f"need at least one candidate, got n={n}")
    if not names:
        raise ValueError("no strategies to schedule")
    unknown = sorted(set(names) - STRATEGIES.keys())
    if unknown:
        raise ValueError(f"unknown strategies {unknown}; known: {sorted(STRATEGIES)}")
    seen: Counter[str] = Counter()
    picked: list[ScheduledCandidate] = []
    for i in range(n):
        name = names[i % len(names)]
        picked.append(ScheduledCandidate(STRATEGIES[name], seen[name]))
        seen[name] += 1
    return picked


def model_for(spec: StrategySpec, settings: Settings) -> str:
    """The configured model name for the strategy's tier."""
    return settings.generator_model if spec.model_tier == "generator" else settings.small_model
