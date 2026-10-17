from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from text2sql.config import REPO_ROOT
from text2sql.data.bird import BirdExample, Difficulty, load_minidev, read_split_file
from text2sql.data.bird_split import SEED, TEST_FRACTION, build_split_file, split_question_ids

HAS_BIRD = (REPO_ROOT / "data" / "bird" / "mini_dev_sqlite.json").is_file()
requires_bird = pytest.mark.skipif(not HAS_BIRD, reason="BIRD data absent; run the bird download")

DIFFICULTIES: tuple[Difficulty, ...] = ("simple", "moderate", "challenging")


def _example(qid: int, difficulty: Difficulty, db_id: str) -> BirdExample:
    return BirdExample(
        question_id=qid,
        db_id=db_id,
        question="q",
        evidence="",
        gold_sql="SELECT 1",
        difficulty=difficulty,
    )


def _synthetic(sizes: dict[tuple[Difficulty, str], int]) -> list[BirdExample]:
    examples, qid = [], 0
    for (difficulty, db_id), n in sizes.items():
        for _ in range(n):
            qid += 1
            examples.append(_example(qid, difficulty, db_id))
    return examples


def _within_one(examples: Sequence[BirdExample], test: set[int], key: Callable[..., str]) -> bool:
    total = Counter(key(e) for e in examples)
    chosen = Counter(key(e) for e in examples if e.question_id in test)
    return all(abs(chosen[k] - n * TEST_FRACTION) < 1 for k, n in total.items())


def _assert_valid_split(examples: Sequence[BirdExample], dev: list[int], test: list[int]) -> None:
    ids = {e.question_id for e in examples}
    assert set(dev).isdisjoint(test)
    assert set(dev) | set(test) == ids
    assert len(test) == round(len(ids) * TEST_FRACTION)
    strata: Counter[tuple[str, str]] = Counter((e.difficulty, e.db_id) for e in examples)
    in_test: Counter[tuple[str, str]] = Counter(
        (e.difficulty, e.db_id) for e in examples if e.question_id in set(test)
    )
    for stratum, n in strata.items():
        exact = n * TEST_FRACTION
        assert math.floor(exact) <= in_test[stratum] <= math.ceil(exact), stratum


SIZES: dict[tuple[Difficulty, str], int] = {
    ("simple", "a"): 7,
    ("moderate", "a"): 11,
    ("challenging", "a"): 2,
    ("simple", "b"): 5,
    ("moderate", "b"): 9,
    ("challenging", "b"): 4,
    ("simple", "c"): 1,
}


class TestSplitQuestionIds:
    def test_same_seed_same_split_regardless_of_input_order(self) -> None:
        examples = _synthetic(SIZES)
        assert split_question_ids(examples) == split_question_ids(list(reversed(examples)))

    def test_different_seed_changes_membership_not_counts(self) -> None:
        examples = _synthetic(SIZES)
        _, test_a = split_question_ids(examples, seed=1)
        _, test_b = split_question_ids(examples, seed=2)
        assert test_a != test_b
        assert len(test_a) == len(test_b)

    def test_split_is_valid(self) -> None:
        examples = _synthetic(SIZES)
        _assert_valid_split(examples, *split_question_ids(examples))

    def test_singleton_stratum_goes_to_dev(self) -> None:
        examples = _synthetic({("simple", "a"): 1, ("moderate", "a"): 10})
        _, test = split_question_ids(examples)
        assert 1 not in test

    @settings(max_examples=60, deadline=None)
    @given(
        st.dictionaries(
            st.tuples(st.sampled_from(DIFFICULTIES), st.sampled_from(["a", "b", "c", "d"])),
            st.integers(min_value=1, max_value=25),
            min_size=1,
        ),
        st.integers(min_value=0, max_value=2**32),
    )
    def test_any_stratification_is_valid(
        self, sizes: dict[tuple[Difficulty, str], int], seed: int
    ) -> None:
        examples = _synthetic(sizes)
        _assert_valid_split(examples, *split_question_ids(examples, seed=seed))


class TestCommittedSplitFiles:
    def test_files_are_disjoint_and_sized_70_30(self) -> None:
        dev, test = read_split_file("dev"), read_split_file("test")
        assert set(dev.question_ids).isdisjoint(test.question_ids)
        assert (dev.count, test.count) == (350, 150)
        for split in (dev, test):
            assert split.seed == SEED
            assert sum(split.counts_by_difficulty.values()) == split.count
            assert sum(split.counts_by_db.values()) == split.count

    @pytest.mark.bird
    @requires_bird
    def test_files_match_a_fresh_split_of_minidev(self) -> None:
        examples = load_minidev()
        dev, test = split_question_ids(examples)
        _assert_valid_split(examples, dev, test)
        assert _within_one(examples, set(test), lambda e: e.difficulty)
        assert _within_one(examples, set(test), lambda e: e.db_id)
        assert read_split_file("dev") == build_split_file("dev", dev, examples)
        assert read_split_file("test") == build_split_file("test", test, examples)
