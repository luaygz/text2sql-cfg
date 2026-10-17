"""BIRD Mini-Dev questions, the Arcwise-Plat-SQL corrections, train questions and database paths.

Files come from `python -m text2sql.data.download bird` (see docs/adr/003-bird-data.md):

    data/bird/mini_dev_sqlite.json        500 questions, BIRD's canonical release
    data/bird/arcwise_plat_sql.json       498 corrected labels (Jin et al. 2026)
    data/bird/train_filtered.jsonl        6,601 train question/SQL pairs, no databases
    data/bird/minidev_databases/<db_id>/  Mini-Dev package: <db_id>.sqlite, database_description/
    data/bird/dev_databases/<db_id>/      BIRD Dev release dev_20240627, same layout
    data/splits/bird_minidev_{dev,test}.json   committed 70/30 split

The two database releases share schemas but not contents: the Mini-Dev package drops rows from
formula_1, thrombosis_prediction and toxicology and repairs leading zeros in
california_schools.satscores. Original Mini-Dev gold is scored on "minidev" (what BIRD ships with
it); Arcwise-Plat-SQL gold is scored on "dev" (what Jin et al. checked it against).

Arcwise-Plat-SQL is not only a gold-SQL fix: it inherits Arcwise's rewrites of 81 questions and 68
evidence strings, so an example carries the Arcwise question and evidence next to the Arcwise gold.
Run the Arcwise table on those inputs; predictions can be reused where `arcwise_inputs_changed`
is False.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from text2sql.config import get_settings

Difficulty = Literal["simple", "moderate", "challenging"]
SplitName = Literal["dev", "test"]
DbRelease = Literal["minidev", "dev"]
"""Which copy of the databases: the Mini-Dev package or the BIRD Dev release (see module doc)."""


def _same_text(a: str, b: str) -> bool:
    return a.split() == b.split()


class BirdExample(BaseModel):
    """One Mini-Dev question with its original and (when available) Arcwise-Plat-SQL labels."""

    model_config = ConfigDict(frozen=True)

    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: Difficulty
    gold_sql_arcwise: str | None = None
    """Arcwise-Plat-SQL gold; None for the 2 questions (119, 120) it does not cover."""
    question_arcwise: str | None = None
    evidence_arcwise: str | None = None

    @model_validator(mode="after")
    def _arcwise_all_or_nothing(self) -> Self:
        present = {
            self.gold_sql_arcwise is not None,
            self.question_arcwise is not None,
            self.evidence_arcwise is not None,
        }
        if len(present) != 1:
            raise ValueError("Arcwise gold, question and evidence must be set together")
        return self

    @property
    def has_arcwise(self) -> bool:
        return self.gold_sql_arcwise is not None

    @property
    def arcwise_inputs_changed(self) -> bool:
        """True when Arcwise reworded the question or evidence (beyond whitespace), so the model
        must be rerun for the Arcwise table instead of reusing the original prediction."""
        if self.question_arcwise is None or self.evidence_arcwise is None:
            return False
        return not (
            _same_text(self.question_arcwise, self.question)
            and _same_text(self.evidence_arcwise, self.evidence)
        )


class BirdTrainExample(BaseModel):
    """A BIRD train question/SQL pair (filtered release); `train_id` is its line number."""

    model_config = ConfigDict(frozen=True)

    train_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str


class SplitFile(BaseModel):
    """On-disk format of data/splits/bird_minidev_{dev,test}.json."""

    model_config = ConfigDict(frozen=True)

    name: SplitName
    source: str
    method: str
    seed: int
    test_fraction: float
    count: int
    counts_by_difficulty: dict[str, int]
    counts_by_db: dict[str, int]
    question_ids: list[int]

    @model_validator(mode="after")
    def _counts_consistent(self) -> Self:
        if self.count != len(self.question_ids) or len(set(self.question_ids)) != self.count:
            raise ValueError(f"split {self.name}: count does not match unique question_ids")
        return self


def bird_dir() -> Path:
    return get_settings().data_dir / "bird"


def split_path(name: SplitName) -> Path:
    return get_settings().data_dir / "splits" / f"bird_minidev_{name}.json"


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing; run `uv run --frozen python -m text2sql.data.download bird`"
        )
    return path


def _database_dir(db_id: str, release: DbRelease) -> Path:
    if not db_id or Path(db_id).name != db_id or db_id.startswith("."):
        raise ValueError(f"not a database id: {db_id!r}")
    return bird_dir() / f"{release}_databases" / db_id


def bird_db_path(db_id: str, release: DbRelease = "minidev") -> Path:
    """The SQLite file of a database in the given release."""
    return _require(_database_dir(db_id, release) / f"{db_id}.sqlite")


def bird_description_dir(db_id: str, release: DbRelease = "minidev") -> Path:
    """Directory of BIRD's per-table `database_description` CSVs for a database."""
    return _require(_database_dir(db_id, release) / "database_description")


class _TrainRow(BaseModel):
    """A row as BIRD stores it, with the gold query under `SQL`."""

    db_id: str
    question: str
    evidence: str | None
    """Arcwise writes an empty evidence string as null."""
    gold_sql: str = Field(alias="SQL")


class _QuestionRow(_TrainRow):
    question_id: int
    """Arcwise stores ids as strings; pydantic coerces them."""
    difficulty: Difficulty | None = None
    """Present in Mini-Dev rows, absent from Arcwise rows."""


_QuestionRows = TypeAdapter(list[_QuestionRow])


def _read_rows(path: Path) -> list[_QuestionRow]:
    return _QuestionRows.validate_json(_require(path).read_bytes())


@cache
def _minidev(root: Path) -> tuple[BirdExample, ...]:
    arcwise = {row.question_id: row for row in _read_rows(root / "arcwise_plat_sql.json")}
    examples = []
    for row in _read_rows(root / "mini_dev_sqlite.json"):
        if row.difficulty is None:
            raise ValueError(f"Mini-Dev question {row.question_id} has no difficulty")
        fix = arcwise.pop(row.question_id, None)
        examples.append(
            BirdExample(
                question_id=row.question_id,
                db_id=row.db_id,
                question=row.question,
                evidence=row.evidence or "",
                gold_sql=row.gold_sql,
                difficulty=row.difficulty,
                gold_sql_arcwise=None if fix is None else fix.gold_sql,
                question_arcwise=None if fix is None else fix.question,
                evidence_arcwise=None if fix is None else fix.evidence or "",
            )
        )
    if arcwise:
        raise ValueError(f"Arcwise-Plat-SQL ids missing from Mini-Dev: {sorted(arcwise)}")
    duplicates = [qid for qid, n in Counter(e.question_id for e in examples).items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate Mini-Dev question_ids: {duplicates}")
    return tuple(sorted(examples, key=lambda e: e.question_id))


def load_minidev() -> list[BirdExample]:
    """All 500 Mini-Dev examples, sorted by question_id."""
    return list(_minidev(bird_dir()))


def minidev_db_ids() -> tuple[str, ...]:
    """The 11 database ids used by Mini-Dev, sorted."""
    return tuple(sorted({e.db_id for e in _minidev(bird_dir())}))


def read_split_file(name: SplitName) -> SplitFile:
    return SplitFile.model_validate_json(_require(split_path(name)).read_bytes())


def load_split(name: SplitName) -> list[BirdExample]:
    """Examples of the committed `dev` (tuning) or `test` (held-out) split, by question_id."""
    wanted = set(read_split_file(name).question_ids)
    examples = [e for e in _minidev(bird_dir()) if e.question_id in wanted]
    if len(examples) != len(wanted):
        raise ValueError(f"split {name} names question_ids that are not in Mini-Dev")
    return examples


@cache
def _train(root: Path) -> tuple[BirdTrainExample, ...]:
    with _require(root / "train_filtered.jsonl").open(encoding="utf-8") as fh:
        rows = [_TrainRow.model_validate_json(line) for line in fh]
    return tuple(
        BirdTrainExample(
            train_id=train_id,
            db_id=row.db_id,
            question=row.question,
            evidence=row.evidence or "",
            gold_sql=row.gold_sql,
        )
        for train_id, row in enumerate(rows)
    )


def load_bird_train() -> list[BirdTrainExample]:
    """The 6,601 filtered BIRD train pairs (for few-shot retrieval; their databases are absent)."""
    return list(_train(bird_dir()))
