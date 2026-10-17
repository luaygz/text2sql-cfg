from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from datasketch import MinHash, MinHashLSH
from datasketch.lsh import _optimal_param

from text2sql.retrieval.lsh import (
    NUM_PERM,
    SCHEME,
    SEED,
    BandIndex,
    shingles,
    signature,
    signatures,
)

WORDS = [
    "New York", "Newark", "New Orleans", "York", "Yorkshire", "Berlin", "Bern", "Paris",
    "Parish", "Munich", "Hamburg", "Hamburger", "Alameda", "Alameda County", "Los Angeles",
    "San Diego", "San Francisco", "Fresno", "x", "ab", "Ian Thorpe", "Thorpe Park",
]  # fmt: skip


def test_chess_parameters_mean_one_row_per_band() -> None:
    # The banded index relies on datasketch choosing 100 bands of 1 row for CHESS's settings.
    assert _optimal_param(0.01, NUM_PERM, 0.5, 0.5) == (NUM_PERM, 1)


def test_bulk_and_single_signatures_agree() -> None:
    bulk = signatures(WORDS)
    assert bulk.shape == (len(WORDS), NUM_PERM)
    for row, word in zip(bulk, WORDS, strict=True):
        assert np.array_equal(row, signature(word))


@pytest.mark.parametrize("query", ["new yrok", "Hamburg", "san", "Thorpe", "zzz", "ab"])
def test_candidates_equal_datasketch_lsh(query: str) -> None:
    lsh = MinHashLSH(threshold=0.01, num_perm=NUM_PERM)
    for i, word in enumerate(WORDS):
        m = MinHash(num_perm=NUM_PERM, seed=SEED, scheme=SCHEME)
        m.update_batch(shingles(word))
        lsh.insert(str(i), m)
    q = MinHash(num_perm=NUM_PERM, seed=SEED, scheme=SCHEME)
    q.update_batch(shingles(query))
    expected = {int(k) for k in lsh.query(q)}
    assert BandIndex.build(signatures(WORDS)).candidates(signature(query)) == expected


def test_query_ranks_by_estimated_jaccard_and_respects_top_n() -> None:
    index = BandIndex.build(signatures(WORDS))
    top = index.query(signature("hamburg"), 3)
    assert len(top) <= 3
    assert top[0] == (WORDS.index("Hamburg"), 1.0)  # case-insensitive shingles
    scores = [s for _, s in top]
    assert scores == sorted(scores, reverse=True)


def test_query_with_no_shared_shingle_returns_nothing() -> None:
    index = BandIndex.build(signatures(["alpha", "beta"]))
    assert index.query(signature("qqqqq"), 10) == []


def test_round_trip_through_disk(tmp_path: Path) -> None:
    index = BandIndex.build(signatures(WORDS))
    index.save(tmp_path)
    loaded = BandIndex.load(tmp_path)
    assert loaded.size == len(WORDS)
    assert loaded.query(signature("Paris"), 5) == index.query(signature("Paris"), 5)


def test_load_rejects_mismatched_arrays(tmp_path: Path) -> None:
    index = BandIndex.build(signatures(WORDS))
    index.save(tmp_path)
    np.save(tmp_path / "lsh_ids.npy", index.ids[:, :3])
    with pytest.raises(ValueError, match="corrupt"):
        BandIndex.load(tmp_path)
