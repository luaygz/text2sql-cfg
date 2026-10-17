from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from text2sql.config import REPO_ROOT, get_settings
from text2sql.data.bird import (
    BirdExample,
    bird_db_path,
    bird_description_dir,
    load_bird_train,
    load_minidev,
    load_split,
    minidev_db_ids,
)

HAS_BIRD = (REPO_ROOT / "data" / "bird" / "mini_dev_sqlite.json").is_file()
requires_bird = pytest.mark.skipif(not HAS_BIRD, reason="BIRD data absent; run the bird download")


def _row(qid: int | str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "question_id": qid,
        "db_id": "shop",
        "question": f"question {qid}",
        "evidence": f"evidence {qid}",
        "SQL": f"SELECT {qid}",
        "difficulty": "simple",
    }
    row.update(overrides)
    return row


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "bird").mkdir()
    yield tmp_path
    get_settings.cache_clear()


def _write(
    data_dir: Path, minidev: list[dict[str, object]], arcwise: list[dict[str, object]]
) -> None:
    (data_dir / "bird" / "mini_dev_sqlite.json").write_text(json.dumps(minidev))
    (data_dir / "bird" / "arcwise_plat_sql.json").write_text(json.dumps(arcwise))


class TestLoadMinidev:
    def test_merges_arcwise_labels_by_question_id(self, data_dir: Path) -> None:
        arcwise = _row("2", SQL="SELECT 'fixed'", question="reworded", evidence=None)
        del arcwise["difficulty"]
        _write(data_dir, [_row(2), _row(1)], [arcwise])
        first, second = load_minidev()
        assert (first.question_id, second.question_id) == (1, 2)
        assert first.gold_sql_arcwise is None and not first.has_arcwise
        assert second.gold_sql_arcwise == "SELECT 'fixed'"
        assert second.question_arcwise == "reworded"
        assert second.evidence_arcwise == ""  # Arcwise writes empty evidence as null
        assert second.gold_sql == "SELECT 2"  # original label untouched

    def test_inputs_changed_ignores_whitespace_only_edits(self, data_dir: Path) -> None:
        _write(
            data_dir,
            [_row(1), _row(2)],
            [
                _row(1, question=" question  1 ", SQL="SELECT 'new'"),
                _row(2, evidence="different evidence"),
            ],
        )
        same, changed = load_minidev()
        assert not same.arcwise_inputs_changed
        assert changed.arcwise_inputs_changed

    def test_arcwise_id_unknown_to_minidev_is_an_error(self, data_dir: Path) -> None:
        _write(data_dir, [_row(1)], [_row(99)])
        with pytest.raises(ValueError, match="99"):
            load_minidev()

    def test_duplicate_question_ids_are_an_error(self, data_dir: Path) -> None:
        _write(data_dir, [_row(1), _row(1)], [])
        with pytest.raises(ValueError, match="duplicate"):
            load_minidev()

    def test_unknown_difficulty_is_rejected(self, data_dir: Path) -> None:
        _write(data_dir, [_row(1, difficulty="hard")], [])
        with pytest.raises(ValidationError):
            load_minidev()

    def test_missing_files_point_at_the_download_command(self, data_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match=r"text2sql\.data\.download bird"):
            load_minidev()

    def test_examples_are_immutable(self, data_dir: Path) -> None:
        _write(data_dir, [_row(1)], [])
        (example,) = load_minidev()
        with pytest.raises(ValidationError):
            example.gold_sql = "DROP TABLE x"  # type: ignore[misc]

    def test_partial_arcwise_labels_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="together"):
            BirdExample(
                question_id=1,
                db_id="shop",
                question="q",
                evidence="",
                gold_sql="SELECT 1",
                difficulty="simple",
                gold_sql_arcwise="SELECT 2",
            )


class TestPaths:
    def test_db_path_per_release(self, data_dir: Path) -> None:
        for release in ("minidev", "dev"):
            db = data_dir / "bird" / f"{release}_databases" / "shop" / "shop.sqlite"
            db.parent.mkdir(parents=True)
            db.touch()
        assert bird_db_path("shop") == data_dir / "bird/minidev_databases/shop/shop.sqlite"
        assert bird_db_path("shop", "dev") == data_dir / "bird/dev_databases/shop/shop.sqlite"

    @pytest.mark.parametrize("db_id", ["", "../shop", "a/b", ".hidden"])
    def test_rejects_ids_that_are_not_plain_names(self, data_dir: Path, db_id: str) -> None:
        with pytest.raises(ValueError, match="not a database id"):
            bird_db_path(db_id)

    def test_missing_database_raises(self, data_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            bird_description_dir("shop")


class TestLoadSplit:
    def test_split_naming_unknown_question_fails(self, data_dir: Path) -> None:
        _write(data_dir, [_row(1)], [])
        (data_dir / "splits").mkdir()
        (data_dir / "splits" / "bird_minidev_dev.json").write_text(
            json.dumps(
                {
                    "name": "dev",
                    "source": "s",
                    "method": "m",
                    "seed": 1,
                    "test_fraction": 0.3,
                    "count": 2,
                    "counts_by_difficulty": {},
                    "counts_by_db": {},
                    "question_ids": [1, 7],
                }
            )
        )
        with pytest.raises(ValueError, match="not in Mini-Dev"):
            load_split("dev")


class TestTrain:
    def test_train_rows_get_line_number_ids(self, data_dir: Path) -> None:
        rows = [
            {"db_id": "a", "question": "q0", "evidence": "e", "SQL": "SELECT 0"},
            {"db_id": "b", "question": "q1", "evidence": None, "SQL": "SELECT 1"},
        ]
        path = data_dir / "bird" / "train_filtered.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        first, second = load_bird_train()
        assert (first.train_id, second.train_id) == (0, 1)
        assert second.evidence == ""
        assert second.gold_sql == "SELECT 1"


@pytest.mark.bird
@requires_bird
class TestRealMinidev:
    def test_500_unique_examples(self) -> None:
        examples = load_minidev()
        assert len(examples) == 500
        assert len({e.question_id for e in examples}) == 500

    def test_difficulty_and_database_counts_match_the_bird_readme(self) -> None:
        examples = load_minidev()
        assert Counter(e.difficulty for e in examples) == {
            "simple": 148,
            "moderate": 250,
            "challenging": 102,
        }
        assert Counter(e.db_id for e in examples) == {
            "debit_card_specializing": 30,
            "student_club": 48,
            "thrombosis_prediction": 50,
            "european_football_2": 51,
            "formula_1": 66,
            "superhero": 52,
            "codebase_community": 49,
            "card_games": 52,
            "toxicology": 40,
            "california_schools": 30,
            "financial": 32,
        }

    def test_arcwise_covers_all_but_the_two_replaced_duplicates(self) -> None:
        missing = [e.question_id for e in load_minidev() if not e.has_arcwise]
        assert missing == [119, 120]

    def test_every_database_exists_in_both_releases(self) -> None:
        assert len(minidev_db_ids()) == 11
        for db_id in minidev_db_ids():
            for release in ("minidev", "dev"):
                assert bird_db_path(db_id, release).stat().st_size > 0
                assert any(bird_description_dir(db_id, release).glob("*.csv"))

    def test_filtered_train_set(self) -> None:
        train = load_bird_train()
        assert len(train) == 6601
        assert not {e.db_id for e in train} & set(minidev_db_ids())
