from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from text2sql.config import get_settings
from text2sql.data.bird_gold_check import check_gold


def _db(path: Path, rows: list[int]) -> None:
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?)", [(r,) for r in rows])
    conn.commit()
    conn.close()


def _q(qid: int, sql: str) -> dict[str, object]:
    return {"question_id": qid, "db_id": "shop", "question": "q", "evidence": "", "SQL": sql}


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    bird = tmp_path / "bird"
    _db(bird / "minidev_databases" / "shop" / "shop.sqlite", [1, 2])
    _db(bird / "dev_databases" / "shop" / "shop.sqlite", [1, 2, 3])
    minidev = [
        {**_q(1, "SELECT x FROM t WHERE x < 3"), "difficulty": "simple"},
        {**_q(2, "SELECT count(*) FROM t"), "difficulty": "moderate"},
        {**_q(3, "SELECT nope FROM t"), "difficulty": "challenging"},
        {**_q(4, "SELECT 1"), "difficulty": "simple"},
    ]
    arcwise = [
        _q(1, "SELECT x FROM t WHERE x <= 2 ORDER BY x"),  # same answer, different text
        _q(2, "SELECT count(DISTINCT x) + 10 FROM t"),  # different answer
        _q(3, "SELECT x FROM t"),  # fixes a broken gold
    ]
    (bird / "mini_dev_sqlite.json").write_text(json.dumps(minidev))
    (bird / "arcwise_plat_sql.json").write_text(json.dumps(arcwise))
    yield tmp_path
    get_settings.cache_clear()


def test_report_counts_failures_and_differences(data_dir: Path) -> None:
    report = check_gold(timeout_s=5)
    assert (report.questions, report.arcwise_questions) == (4, 3)
    assert report.original_on_minidev.errors == [3]
    assert report.arcwise_on_dev.errors == []
    assert report.arcwise_differs_on_dev == [2]
    assert report.arcwise_changed_by_db == {"shop": 1}
    # count(*) and "x FROM t" see the extra dev row; "x < 3" does not.
    assert report.original_differs_across_releases == [2]
    assert report.arcwise_differs_across_releases == [2, 3]
