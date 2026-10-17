from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from text2sql.evals.bird_metric import (
    SqlRunError,
    SqlTimeoutError,
    execute_readonly,
    execution_match,
    results_match,
    rves_question_reward,
    rves_reward,
    rves_score,
)

# Never finishes on its own: SQLite keeps producing rows until interrupted.
ENDLESS = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT max(i) FROM n"


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "shop.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, price REAL);
        INSERT INTO item VALUES (1, 'apple', 1.0), (2, 'pear', 2.5), (3, 'plum', NULL);
        """
    )
    conn.commit()
    conn.close()
    return path


class TestResultsMatch:
    def test_row_order_is_ignored(self) -> None:
        assert results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])

    def test_duplicate_rows_are_ignored_like_the_official_set_comparison(self) -> None:
        assert results_match([(1,), (1,), (2,)], [(2,), (1,)])

    def test_column_order_matters(self) -> None:
        assert not results_match([(1, "a")], [("a", 1)])

    def test_integer_equals_float_with_same_value(self) -> None:
        assert results_match([(1,)], [(1.0,)])

    def test_no_float_tolerance(self) -> None:
        assert not results_match([(0.1 + 0.2,)], [(0.3,)])

    def test_numeric_string_is_not_a_number(self) -> None:
        assert not results_match([("1",)], [(1,)])

    def test_null_matches_only_null(self) -> None:
        assert results_match([(None,)], [(None,)])
        assert not results_match([(None,)], [(0,)])

    def test_extra_column_is_a_miss(self) -> None:
        assert not results_match([(1, "a")], [(1,)])

    def test_two_empty_results_match(self) -> None:
        assert results_match([], [])

    def test_empty_vs_null_row_is_a_miss(self) -> None:
        assert not results_match([], [(None,)])

    def test_accepts_lists_as_rows(self) -> None:
        assert results_match([[1, "a"]], [(1, "a")])


class TestExecuteReadonly:
    def test_returns_all_rows_as_tuples(self, db: Path) -> None:
        rows = execute_readonly("SELECT id, name FROM item ORDER BY id", db)
        assert rows == [(1, "apple"), (2, "pear"), (3, "plum")]

    def test_writes_are_rejected_and_the_file_is_unchanged(self, db: Path) -> None:
        with pytest.raises(SqlRunError, match="readonly"):
            execute_readonly("DELETE FROM item", db)
        assert execute_readonly("SELECT count(*) FROM item", db) == [(3,)]

    def test_sql_error_raises_run_error_not_timeout(self, db: Path) -> None:
        with pytest.raises(SqlRunError) as info:
            execute_readonly("SELECT missing_column FROM item", db)
        assert not isinstance(info.value, SqlTimeoutError)

    def test_long_query_times_out_close_to_the_deadline(self, db: Path) -> None:
        start = time.monotonic()
        with pytest.raises(SqlTimeoutError):
            execute_readonly(ENDLESS, db, timeout_s=0.2)
        assert time.monotonic() - start < 5

    def test_missing_database_raises_and_creates_nothing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.sqlite"
        with pytest.raises(FileNotFoundError):
            execute_readonly("SELECT 1", missing)
        assert not missing.exists()

    def test_path_with_uri_special_characters(self, tmp_path: Path, db: Path) -> None:
        odd = tmp_path / "dir with space?#%" / "x.sqlite"
        odd.parent.mkdir()
        odd.write_bytes(db.read_bytes())
        assert execute_readonly("SELECT count(*) FROM item", odd) == [(3,)]

    def test_named_params_are_bound(self, db: Path) -> None:
        rows = execute_readonly(
            "SELECT name FROM item WHERE id = :item_id", db, params={"item_id": 2}
        )
        assert rows == [("pear",)]

    def test_missing_named_param_is_a_run_error(self, db: Path) -> None:
        with pytest.raises(SqlRunError):
            execute_readonly("SELECT name FROM item WHERE id = :item_id", db, params={})


class TestExecutionMatch:
    def test_equivalent_queries_match(self, db: Path) -> None:
        assert execution_match(
            "SELECT name FROM item WHERE price > 1",
            "SELECT name FROM item WHERE price >= 2.5 ORDER BY name",
            db,
        )

    def test_different_results_do_not_match(self, db: Path) -> None:
        assert not execution_match("SELECT name FROM item", "SELECT id FROM item", db)

    def test_prediction_error_is_a_miss(self, db: Path) -> None:
        assert not execution_match("SELEC name FROM item", "SELECT name FROM item", db)

    def test_gold_error_is_a_miss(self, db: Path) -> None:
        assert not execution_match("SELECT name FROM item", "SELECT nope FROM item", db)

    def test_prediction_timeout_is_a_miss(self, db: Path) -> None:
        assert not execution_match(ENDLESS, "SELECT 1", db, timeout_s=0.2)

    def test_the_clock_is_pinned_so_scores_do_not_change_with_the_day(self, db: Path) -> None:
        assert execution_match("SELECT date('now')", "SELECT '2026-10-16'", db)
        assert execution_match("SELECT CURRENT_DATE", "SELECT date('now')", db)

    def test_count_star_with_ints_matches_float_aggregate(self, db: Path) -> None:
        assert execution_match("SELECT count(*) FROM item", "SELECT CAST(3 AS REAL)", db)

    def test_params_are_bound_to_both_statements(self, db: Path) -> None:
        assert execution_match(
            "SELECT name FROM item WHERE id <= :max_id",
            "SELECT name FROM item WHERE id < :max_id + 1 ORDER BY id DESC",
            db,
            params={"max_id": 2},
        )
        assert not execution_match(
            "SELECT name FROM item WHERE id <= :max_id",
            "SELECT name FROM item",
            db,
            params={"max_id": 2},
        )

    def test_prediction_without_the_gold_param_value_is_a_miss(self, db: Path) -> None:
        assert not execution_match(
            "SELECT name FROM item WHERE id = :other",
            "SELECT name FROM item WHERE id = :item_id",
            db,
            params={"item_id": 1},
        )


class TestRves:
    @pytest.mark.parametrize(
        ("ratio", "reward"),
        [
            (0, 0.0),
            (0.01, 0.25),
            (0.25, 0.5),
            (0.49, 0.5),
            (0.5, 0.75),
            (0.99, 0.75),
            (1.0, 1.0),
            (1.99, 1.0),
            (2.0, 1.25),
            (50.0, 1.25),
        ],
    )
    def test_reward_bands(self, ratio: float, reward: float) -> None:
        assert rves_reward(ratio) == reward

    def test_score_is_mean_of_sqrt_rewards_times_100(self) -> None:
        assert rves_score([1.0, 0.25, 0.0, 1.25]) == pytest.approx(
            (100 + 50 + 0 + 1.25**0.5 * 100) / 4
        )

    def test_score_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            rves_score([])

    def test_wrong_prediction_scores_zero(self, db: Path) -> None:
        assert rves_question_reward("SELECT id FROM item", "SELECT name FROM item", db) == 0.0

    def test_correct_prediction_gets_a_positive_reward(self, db: Path) -> None:
        reward = rves_question_reward(
            "SELECT name FROM item", "SELECT name FROM item ORDER BY name", db, iterations=5
        )
        assert reward in {0.25, 0.5, 0.75, 1.0, 1.25}

    def test_failing_prediction_scores_zero(self, db: Path) -> None:
        assert rves_question_reward("SELECT nope FROM item", "SELECT 1", db) == 0.0
