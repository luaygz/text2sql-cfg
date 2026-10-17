"""Stratified 70/30 dev/test split of BIRD Mini-Dev, written to data/splits/.

    uv run --frozen python -m text2sql.data.bird_split

Strata are (difficulty, db_id) pairs. Each stratum sends floor(0.3 * n) questions to test; the
remaining round(0.3 * N) - sum(floor) test slots go one at a time to the stratum (among those
with a fractional share) whose difficulty and database totals are furthest below 30%. Every
stratum therefore gets floor or ceil of its share and the test set has exactly round(0.3 * N)
questions. The margin balancing is greedy, so it is not guaranteed in general; on Mini-Dev every
per-difficulty and per-database count lands within one question of 30% (checked in tests).
Members are drawn with `random.Random(SEED)`, so the output depends only on the questions and
the seed.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from text2sql.data.bird import BirdExample, SplitFile, SplitName, load_minidev, split_path

SEED = 20261016
TEST_FRACTION = 0.3
SOURCE = "BIRD Mini-Dev SQLite, birdsql/bird_mini_dev@f65faf4 (500 questions)"
METHOD = (
    "stratified by (difficulty, db_id); per-stratum test count floor(0.3n) plus largest-deficit "
    "rounding on the difficulty and database margins; members drawn with random.Random(seed)"
)

type Stratum = tuple[str, str]


def _test_quotas(sizes: dict[Stratum, int], fraction: float) -> dict[Stratum, int]:
    quotas = {s: math.floor(n * fraction) for s, n in sizes.items()}
    deficit_diff: defaultdict[str, float] = defaultdict(float)
    deficit_db: defaultdict[str, float] = defaultdict(float)
    for (difficulty, db_id), n in sizes.items():
        deficit_diff[difficulty] += n * fraction - quotas[(difficulty, db_id)]
        deficit_db[db_id] += n * fraction - quotas[(difficulty, db_id)]
    remaining = round(sum(sizes.values()) * fraction) - sum(quotas.values())
    candidates = {s for s, n in sizes.items() if n * fraction > quotas[s]}
    for _ in range(remaining):
        best = max(
            sorted(candidates),
            key=lambda s: (
                deficit_diff[s[0]] + deficit_db[s[1]],
                sizes[s] * fraction - quotas[s],
            ),
        )
        candidates.remove(best)
        quotas[best] += 1
        deficit_diff[best[0]] -= 1
        deficit_db[best[1]] -= 1
    return quotas


def split_question_ids(
    examples: Sequence[BirdExample], *, seed: int = SEED, test_fraction: float = TEST_FRACTION
) -> tuple[list[int], list[int]]:
    """Return sorted (dev, test) question_ids; deterministic for a given example set and seed."""
    strata: defaultdict[Stratum, list[int]] = defaultdict(list)
    for example in examples:
        strata[(example.difficulty, example.db_id)].append(example.question_id)
    quotas = _test_quotas({s: len(ids) for s, ids in strata.items()}, test_fraction)
    rng = random.Random(seed)
    dev: list[int] = []
    test: list[int] = []
    for stratum in sorted(strata):
        ids = sorted(strata[stratum])
        rng.shuffle(ids)
        test.extend(ids[: quotas[stratum]])
        dev.extend(ids[quotas[stratum] :])
    return sorted(dev), sorted(test)


def build_split_file(
    name: SplitName, question_ids: Sequence[int], examples: Sequence[BirdExample]
) -> SplitFile:
    chosen = set(question_ids)
    members = [e for e in examples if e.question_id in chosen]
    return SplitFile(
        name=name,
        source=SOURCE,
        method=METHOD,
        seed=SEED,
        test_fraction=TEST_FRACTION,
        count=len(members),
        counts_by_difficulty=dict(sorted(Counter(e.difficulty for e in members).items())),
        counts_by_db=dict(sorted(Counter(e.db_id for e in members).items())),
        question_ids=sorted(chosen),
    )


def write_splits() -> list[Path]:
    examples = load_minidev()
    dev, test = split_question_ids(examples)
    splits: tuple[tuple[SplitName, list[int]], ...] = (("dev", dev), ("test", test))
    written = []
    for name, ids in splits:
        path = split_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build_split_file(name, ids, examples).model_dump_json(indent=2) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    for written_path in write_splits():
        print(written_path)
