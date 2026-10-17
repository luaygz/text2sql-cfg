from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sps

from text2sql.evals.stats import (
    bootstrap_paired_difference,
    bootstrap_proportion,
    mcnemar_exact,
    wilson_interval,
)


def _pairs(both: int, ref_only: int, var_only: int, neither: int) -> tuple[list[bool], list[bool]]:
    ref = [True] * both + [True] * ref_only + [False] * var_only + [False] * neither
    var = [True] * both + [False] * ref_only + [True] * var_only + [False] * neither
    return ref, var


# McNemar


def test_mcnemar_matches_hand_computed_tail():
    # b=1, c=9: p = 2 * (C(10,0) + C(10,1)) / 2**10 = 22/1024
    ref, var = _pairs(both=40, ref_only=1, var_only=9, neither=50)
    result = mcnemar_exact(ref, var)
    assert (result.reference_only, result.variant_only) == (1, 9)
    assert result.p_value == pytest.approx(22 / 1024, abs=1e-15)


def test_mcnemar_second_hand_computed_table():
    # b=8, c=2: p = 2 * (1 + 10 + 45) / 1024
    ref, var = _pairs(both=3, ref_only=8, var_only=2, neither=7)
    assert mcnemar_exact(ref, var).p_value == pytest.approx(112 / 1024, abs=1e-15)


def test_mcnemar_ignores_concordant_pairs():
    small = mcnemar_exact(*_pairs(both=0, ref_only=3, var_only=12, neither=0))
    large = mcnemar_exact(*_pairs(both=400, ref_only=3, var_only=12, neither=300))
    assert small.p_value == large.p_value


def test_mcnemar_is_symmetric_in_direction():
    ref, var = _pairs(both=5, ref_only=4, var_only=11, neither=5)
    forward, backward = mcnemar_exact(ref, var), mcnemar_exact(var, ref)
    assert forward.p_value == backward.p_value
    assert (forward.reference_only, forward.variant_only) == (
        backward.variant_only,
        backward.reference_only,
    )


@pytest.mark.parametrize("b,c", [(0, 0), (3, 3), (5, 6), (10, 0)])
def test_mcnemar_balanced_or_empty_discordance_never_exceeds_one(b, c):
    p = mcnemar_exact(*_pairs(both=10, ref_only=b, var_only=c, neither=10)).p_value
    assert 0.0 < p <= 1.0
    if b == c:
        assert p == 1.0


@pytest.mark.parametrize("b,c", [(1, 4), (7, 19), (30, 45), (0, 6), (120, 90)])
def test_mcnemar_agrees_with_scipy_binomtest(b, c):
    expected = sps.binomtest(min(b, c), b + c, 0.5).pvalue
    p = mcnemar_exact(*_pairs(both=2, ref_only=b, var_only=c, neither=2)).p_value
    assert p == pytest.approx(min(1.0, expected), rel=1e-9)


def test_paired_inputs_must_match_in_length():
    with pytest.raises(ValueError, match="differ in length"):
        mcnemar_exact([True, False], [True])


# Wilson


def test_wilson_textbook_values():
    half = wilson_interval(5, 10)
    assert (half.low, half.high) == (
        pytest.approx(0.2366, abs=1e-4),
        pytest.approx(0.7634, abs=1e-4),
    )
    zero = wilson_interval(0, 10)
    assert zero.low == 0.0
    assert zero.high == pytest.approx(3.8415 / 13.8415, abs=1e-4)


def test_wilson_rejects_impossible_counts():
    for k, n in [(1, 0), (-1, 5), (6, 5)]:
        with pytest.raises(ValueError):
            wilson_interval(k, n)


# Bootstrap of a proportion


def test_bootstrap_is_deterministic_for_a_seed():
    outcomes = [True] * 601 + [False] * 396
    assert bootstrap_proportion(outcomes, seed=3) == bootstrap_proportion(outcomes, seed=3)
    few = {bootstrap_proportion(outcomes, resamples=25, seed=s) for s in range(5)}
    assert len(few) > 1


def test_bootstrap_matches_explicit_index_resampling():
    rng = np.random.default_rng(11)
    outcomes = list(rng.random(300) < 0.62)
    fast = bootstrap_proportion(outcomes, resamples=20_000)
    arr = np.asarray(outcomes)
    idx = np.random.default_rng(5).integers(0, arr.size, size=(20_000, arr.size))
    slow = np.quantile(arr[idx].mean(axis=1), [0.025, 0.975])
    assert fast.estimate == pytest.approx(arr.mean())
    assert fast.low == pytest.approx(slow[0], abs=0.01)
    assert fast.high == pytest.approx(slow[1], abs=0.01)


def test_bootstrap_interval_has_close_to_nominal_coverage():
    rng = np.random.default_rng(2026)
    true_p, n, trials = 0.7, 200, 400
    covered = 0
    for seed in range(trials):
        sample = list(rng.random(n) < true_p)
        ci = bootstrap_proportion(sample, resamples=2_000, seed=seed)
        covered += ci.low <= true_p <= ci.high
    assert 0.91 <= covered / trials <= 0.98


def test_bootstrap_interval_is_narrower_with_more_questions():
    small = bootstrap_proportion([True, False] * 50)
    large = bootstrap_proportion([True, False] * 500)
    assert (large.high - large.low) < (small.high - small.low) / 2


def test_bootstrap_degenerates_at_100_percent_where_wilson_does_not():
    boot = bootstrap_proportion([True] * 30)
    assert (boot.low, boot.high) == (1.0, 1.0)
    assert wilson_interval(30, 30).low < 0.9


@pytest.mark.parametrize("kwargs", [{"confidence": 0.0}, {"confidence": 1.0}, {"resamples": 0}])
def test_bootstrap_rejects_bad_parameters(kwargs):
    with pytest.raises(ValueError):
        bootstrap_proportion([True, False], **kwargs)


def test_bootstrap_rejects_empty_input():
    with pytest.raises(ValueError, match="non-empty"):
        bootstrap_proportion([])


# Paired difference


def test_paired_difference_of_identical_runs_is_exactly_zero():
    ref = [True, False, True, True, False] * 20
    ci = bootstrap_paired_difference(ref, ref)
    assert (ci.estimate, ci.low, ci.high) == (0.0, 0.0, 0.0)


def test_paired_difference_estimate_and_direction():
    ref, var = _pairs(both=50, ref_only=5, var_only=25, neither=20)
    ci = bootstrap_paired_difference(ref, var)
    assert ci.estimate == pytest.approx(20 / 100)
    assert 0.0 < ci.low < ci.estimate < ci.high


def test_paired_difference_matches_explicit_pair_resampling():
    ref, var = _pairs(both=120, ref_only=14, var_only=26, neither=40)
    a, b = np.asarray(ref), np.asarray(var)
    fast = bootstrap_paired_difference(ref, var, resamples=20_000)
    idx = np.random.default_rng(9).integers(0, a.size, size=(20_000, a.size))
    slow = np.quantile(b[idx].mean(axis=1) - a[idx].mean(axis=1), [0.025, 0.975])
    assert fast.low == pytest.approx(slow[0], abs=0.01)
    assert fast.high == pytest.approx(slow[1], abs=0.01)


def test_pairing_is_narrower_than_treating_runs_as_independent():
    # Two runs that agree on most questions: pairing removes the shared variance.
    ref, var = _pairs(both=140, ref_only=4, var_only=12, neither=44)
    paired = bootstrap_paired_difference(ref, var)
    a, b = bootstrap_proportion(ref), bootstrap_proportion(var)
    unpaired_width = np.hypot(a.high - a.low, b.high - b.low)
    assert paired.high - paired.low < unpaired_width / 2
