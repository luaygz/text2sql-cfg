"""Confidence intervals and paired tests for per-question correctness.

Everything here takes boolean outcomes (one per question) and is deterministic for a given seed.
Resampling n Bernoulli outcomes with replacement only matters through the number of successes,
which is Binomial(n, k/n); for paired outcomes it is the multinomial over the four agreement
cells. Drawing those counts directly is distributionally identical to resampling question
indices and costs O(resamples) instead of O(resamples * n).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import numpy.typing as npt

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 0
DEFAULT_CONFIDENCE = 0.95


@dataclass(frozen=True, slots=True)
class Interval:
    estimate: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class McNemarResult:
    reference_only: int
    """Questions the reference got right and the variant got wrong."""
    variant_only: int
    p_value: float
    """Two-sided exact binomial p on the discordant pairs; 1.0 when there are none."""


def _outcomes(values: Sequence[bool]) -> npt.NDArray[np.bool_]:
    arr = np.asarray(values, dtype=np.bool_)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("need a non-empty 1-D sequence of outcomes")
    return arr


def _check(confidence: float, resamples: int) -> float:
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    if resamples < 1:
        raise ValueError(f"resamples must be positive, got {resamples}")
    return (1.0 - confidence) / 2.0


def _percentiles(draws: npt.NDArray[np.float64], tail: float) -> tuple[float, float]:
    low, high = np.quantile(draws, [tail, 1.0 - tail])
    return float(low), float(high)


def bootstrap_proportion(
    outcomes: Sequence[bool],
    *,
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Interval:
    """Percentile bootstrap interval for the share of true outcomes."""
    tail = _check(confidence, resamples)
    x = _outcomes(outcomes)
    n = x.size
    p = float(x.sum()) / n
    rng = np.random.default_rng(seed)
    draws = rng.binomial(n, p, size=resamples).astype(np.float64) / n
    return Interval(p, *_percentiles(draws, tail))


def _discordant(reference: Sequence[bool], variant: Sequence[bool]) -> tuple[int, int, int, int]:
    a, b = _outcomes(reference), _outcomes(variant)
    if a.size != b.size:
        raise ValueError(f"paired outcomes differ in length: {a.size} vs {b.size}")
    both = int(np.sum(a & b))
    reference_only = int(np.sum(a & ~b))
    variant_only = int(np.sum(~a & b))
    return both, reference_only, variant_only, a.size - both - reference_only - variant_only


def bootstrap_paired_difference(
    reference: Sequence[bool],
    variant: Sequence[bool],
    *,
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Interval:
    """Percentile bootstrap interval for mean(variant) - mean(reference), resampling pairs."""
    tail = _check(confidence, resamples)
    cells = np.array(_discordant(reference, variant), dtype=np.int64)
    n = int(cells.sum())
    rng = np.random.default_rng(seed)
    draws = rng.multinomial(n, cells / n, size=resamples)
    diffs = (draws[:, 2] - draws[:, 1]).astype(np.float64) / n
    return Interval(float(cells[2] - cells[1]) / n, *_percentiles(diffs, tail))


def mcnemar_exact(reference: Sequence[bool], variant: Sequence[bool]) -> McNemarResult:
    """Exact McNemar test: under H0 each discordant pair favours either side with p = 1/2.

    Two-sided p = min(1, 2 * P(X <= min(b, c))) for X ~ Binomial(b + c, 1/2), summed in exact
    integer arithmetic.
    """
    _, reference_only, variant_only, _ = _discordant(reference, variant)
    discordant = reference_only + variant_only
    tail = sum(math.comb(discordant, i) for i in range(min(reference_only, variant_only) + 1))
    p_value = min(1.0, 2 * tail / 2**discordant)
    return McNemarResult(reference_only, variant_only, p_value)


def wilson_interval(successes: int, n: int, *, confidence: float = DEFAULT_CONFIDENCE) -> Interval:
    """Wilson score interval; unlike the percentile bootstrap it stays wide at 0% and 100%."""
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError(f"need 0 <= successes <= n and n > 0, got {successes}/{n}")
    tail = _check(confidence, 1)
    z = NormalDist().inv_cdf(1.0 - tail)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = 0.0 if successes == 0 else max(0.0, center - half)
    high = 1.0 if successes == n else min(1.0, center + half)
    return Interval(p, low, high)
