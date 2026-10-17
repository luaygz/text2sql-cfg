"""MinHash LSH over character 3-grams, with CHESS's parameters, stored as numpy arrays.

CHESS indexes distinct column values in a datasketch `MinHashLSH(threshold=0.01, num_perm=100)`
over character 3-grams and ranks the candidates of a query by estimated Jaccard similarity,
keeping the top 10. For those parameters datasketch picks 100 bands of one row each
(`_optimal_param(0.01, 100)` returns `(100, 1)`), so a value is a candidate exactly when one of
its 100 min-hash values equals the query's at the same position, and the share of equal
positions is the Jaccard estimate used for ranking.

datasketch keeps every band key in Python dictionaries. On 50,000 short strings that took 16 s
to insert and about 700 MB of memory, and card_games alone has about 200,000 indexable values,
so the band tables here are sorted numpy arrays instead (one row per band, searched with
`searchsorted`): 800 bytes per value on disk, memory-mapped on load. The signatures still come
from datasketch's `MinHash`, and `tests/retrieval/test_lsh.py` checks that the candidate sets
equal datasketch's `MinHashLSH` on the same data.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from datasketch import MinHash

NUM_PERM = 100
NGRAM = 3
SCHEME = "affine32"
SEED = 1

type Signatures = npt.NDArray[np.uint32]
"""One row of `NUM_PERM` min-hash values per string."""


def normalize(text: str) -> str:
    """Case- and whitespace-insensitive form used for shingling and exact lookup."""
    return " ".join(text.casefold().split())


def shingles(text: str) -> list[bytes]:
    """Character 3-grams of the normalized text; shorter strings are one shingle."""
    s = normalize(text)
    if len(s) <= NGRAM:
        return [s.encode()]
    return [s[i : i + NGRAM].encode() for i in range(len(s) - NGRAM + 1)]


def signatures(texts: Sequence[str]) -> Signatures:
    if not texts:
        return np.zeros((0, NUM_PERM), dtype=np.uint32)
    hashes = MinHash.bulk([shingles(t) for t in texts], num_perm=NUM_PERM, seed=SEED, scheme=SCHEME)
    return np.stack([np.asarray(m.hashvalues, dtype=np.uint32) for m in hashes])


def signature(text: str) -> npt.NDArray[np.uint32]:
    m = MinHash(num_perm=NUM_PERM, seed=SEED, scheme=SCHEME)
    m.update_batch(shingles(text))
    return np.asarray(m.hashvalues, dtype=np.uint32)


@dataclass(frozen=True)
class BandIndex:
    """Per band, the min-hash values of every indexed string in sorted order, and their ids."""

    sorted_hashes: npt.NDArray[np.uint32]
    """Shape (NUM_PERM, n)."""
    ids: npt.NDArray[np.uint32]
    """Shape (NUM_PERM, n): `ids[b, i]` is the string whose band-b hash is `sorted_hashes[b, i]`."""

    @classmethod
    def build(cls, sigs: Signatures) -> BandIndex:
        by_band = np.ascontiguousarray(sigs.T)
        order = np.argsort(by_band, axis=1, kind="stable").astype(np.uint32)
        return cls(np.take_along_axis(by_band, order, axis=1), order)

    @property
    def size(self) -> int:
        return int(self.ids.shape[1])

    def query(self, sig: npt.NDArray[np.uint32], top_n: int) -> list[tuple[int, float]]:
        """The `top_n` candidates with the highest estimated Jaccard, as (id, estimate), best
        first; ties keep the lower id first so results are deterministic."""
        hits: list[npt.NDArray[np.uint32]] = []
        for band in range(NUM_PERM):
            row = self.sorted_hashes[band]
            lo = int(np.searchsorted(row, sig[band], side="left"))
            hi = int(np.searchsorted(row, sig[band], side="right"))
            if hi > lo:
                hits.append(np.asarray(self.ids[band, lo:hi]))
        if not hits:
            return []
        candidates, counts = np.unique(np.concatenate(hits), return_counts=True)
        best = np.lexsort((candidates, -counts))[:top_n]
        return [(int(candidates[i]), float(counts[i]) / NUM_PERM) for i in best]

    def candidates(self, sig: npt.NDArray[np.uint32]) -> set[int]:
        """Every id sharing at least one band with `sig` (what `MinHashLSH.query` returns)."""
        return {i for i, _ in self.query(sig, self.size)}

    def save(self, directory: Path) -> None:
        np.save(directory / "lsh_hashes.npy", self.sorted_hashes)
        np.save(directory / "lsh_ids.npy", self.ids)

    @classmethod
    def load(cls, directory: Path) -> BandIndex:
        hashes = np.load(directory / "lsh_hashes.npy", mmap_mode="r")
        ids = np.load(directory / "lsh_ids.npy", mmap_mode="r")
        if hashes.shape != ids.shape or hashes.shape[0] != NUM_PERM:
            raise ValueError(f"corrupt LSH arrays in {directory}: {hashes.shape} vs {ids.shape}")
        return cls(hashes, ids)
