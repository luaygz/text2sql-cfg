"""BIRD's official execution-accuracy (EX) and R-VES comparison, reimplemented.

Source read on 2026-10-16: bird-bench/mini_dev at commit
abd11b6db92a1c9f809b32f7564c7c71b34d67f0, files `evaluation/evaluation_ex.py`,
`evaluation/evaluation_utils.py` and `evaluation/evaluation_ves.py` (last changed in f9d2750).
Semantics carried over exactly:

- A prediction is correct iff `set(pred_rows) == set(gold_rows)`. Rows are compared as tuples, so
  column order matters, row order and duplicate rows do not, and Python equality applies to values
  (`1 == 1.0`, no float tolerance, NULL is `None`).
- The predicted SQL runs first, then the gold SQL, on one connection, with every row fetched. One
  30 s budget (`meta_time_out`) covers both statements together.
- Any error or timeout, in either statement, scores 0.

Differences: the official script opens the database read-write and enforces the 30 s with
`func_timeout` on the wall clock; here the file is opened with a read-only URI and the limit is a
budget of SQLite virtual-machine steps worth 30 s on the reference machine
(`text2sql.sqlite_budget`). A wall-clock limit made the score of a slow query depend on how many
queries ran at once, so a replay could disagree with the recorded run; a step budget cannot. The
two coincide for every query that is not within a few seconds of the limit. Query shapes that run
few steps per second (long-text scans) are stopped by a wall-clock backstop at five times the
limit, the one place where load can still change a score. The clock is pinned to a fixed date
(`text2sql.sqlite_clock`; twelve Mini-Dev gold queries compute ages from `'now'`), so a score
does not change with the day it is computed. A missing database
file raises FileNotFoundError instead of silently scoring every question 0.
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np

from text2sql.sqlite_budget import CHECK_INTERVAL, StepBudget, steps_for
from text2sql.sqlite_clock import pin_clock

OFFICIAL_TIMEOUT_S = 30.0
"""`meta_time_out` default in evaluation_ex.py and run_evaluation.sh, applied as a step budget."""
WALL_BACKSTOP_FACTOR = 5
"""Wall-clock backstop as a multiple of the budget, for query shapes that run few SQLite steps per
second (long-text scans); a statement it stops scores 0 like any timeout."""
RVES_ITERATIONS = 100
"""`iterate_num` default in evaluation_ves.py."""

type Row = tuple[object, ...]
type SqlParams = Mapping[str, int | float | str]
"""Named parameters (`:tenant_id`, ...) bound to every statement of one call; BIRD uses none."""


class SqlRunError(Exception):
    """A statement failed (syntax error, unknown column, undecodable text, ...)."""


class SqlTimeoutError(SqlRunError):
    """A statement did not finish before its deadline."""


def results_match(
    pred_rows: Iterable[Sequence[object]], gold_rows: Iterable[Sequence[object]]
) -> bool:
    """BIRD EX for one question: equal as sets of row tuples."""
    return {tuple(row) for row in pred_rows} == {tuple(row) for row in gold_rows}


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite file through a `mode=ro` URI, so no statement can write to it, with the clock
    pinned to `BENCHMARK_NOW` so that scores do not change with the calendar
    (`text2sql.sqlite_clock`)."""
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    # No statement cache: SQLite charges a re-run statement from where its last run stopped, so a
    # cached statement would make step budgets depend on history (text2sql.sqlite_budget).
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True, cached_statements=0)
    pin_clock(conn)
    return conn


def _fetch_all(
    conn: sqlite3.Connection, sql: str, budget: StepBudget, params: SqlParams | None = None
) -> list[Row]:
    """All rows of `sql`, charged to `budget` (which may span several statements)."""
    conn.set_progress_handler(budget, CHECK_INTERVAL)
    try:
        cursor = conn.execute(sql) if params is None else conn.execute(sql, params)
        return [tuple(row) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        if budget.stopped:
            limit = "step budget" if budget.exhausted else "wall-clock backstop"
            raise SqlTimeoutError(f"{limit} exceeded: {exc}") from exc
        raise SqlRunError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        conn.set_progress_handler(None, 0)


def _budget(timeout_s: float) -> StepBudget:
    return StepBudget(steps_for(timeout_s), wall_s=WALL_BACKSTOP_FACTOR * timeout_s)


def execute_readonly(
    sql: str,
    db_path: Path,
    *,
    timeout_s: float = OFFICIAL_TIMEOUT_S,
    params: SqlParams | None = None,
) -> list[Row]:
    """Run one statement on a read-only connection and return every row (no row cap, as EX needs).

    Raises SqlTimeoutError once the statement has used `timeout_s` worth of SQLite steps, and
    SqlRunError for any SQLite error,
    including a named parameter the statement uses but `params` does not supply.
    """
    conn = open_readonly(db_path)
    try:
        return _fetch_all(conn, sql, _budget(timeout_s), params)
    finally:
        conn.close()


def execution_match(
    pred_sql: str,
    gold_sql: str,
    db_path: Path,
    *,
    timeout_s: float = OFFICIAL_TIMEOUT_S,
    params: SqlParams | None = None,
) -> bool:
    """Score one question as evaluation_ex.py does: True iff the two result sets are equal.

    Prediction first, then gold, sharing one step budget; any error or timeout is a miss. `params`
    is bound to both statements (the SaaS eval's tenant and user ids); BIRD passes none.
    """
    budget = _budget(timeout_s)
    conn = open_readonly(db_path)
    try:
        pred_rows = _fetch_all(conn, pred_sql, budget, params)
        gold_rows = _fetch_all(conn, gold_sql, budget, params)
    except SqlRunError:
        return False
    finally:
        conn.close()
    return results_match(pred_rows, gold_rows)


def rves_reward(time_ratio: float) -> float:
    """Reward for one question given mean(gold_time / pred_time), per evaluation_ves.py.

    A ratio of 0 stands for a wrong prediction (the official script never times one).
    """
    if time_ratio == 0:
        return 0.0
    if time_ratio >= 2:
        return 1.25
    if time_ratio >= 1:
        return 1.0
    if time_ratio >= 0.5:
        return 0.75
    if time_ratio >= 0.25:
        return 0.5
    return 0.25


def rves_score(rewards: Sequence[float]) -> float:
    """Aggregate per-question rewards into R-VES: mean of sqrt(reward) * 100 (range 0 to ~111.8)."""
    if not rewards:
        raise ValueError("R-VES needs at least one reward")
    return sum(math.sqrt(r) * 100 for r in rewards) / len(rewards)


def _timed_run(sql: str, db_path: Path, budget: StepBudget) -> float:
    conn = open_readonly(db_path)
    try:
        start = time.perf_counter()
        _fetch_all(conn, sql, budget)
        return time.perf_counter() - start
    finally:
        conn.close()


def _mean_without_outliers(ratios: Sequence[float]) -> float:
    values = np.asarray(ratios, dtype=float)
    mean, std = float(values.mean()), float(values.std())
    kept = [float(x) for x in values if mean - 3 * std < x < mean + 3 * std]
    # The official filter uses strict bounds, so identical ratios (std 0) keep nothing; its
    # ZeroDivisionError lands in a catch-all and the question scores 0. Keep that outcome.
    if not kept:
        return 0.0
    return sum(kept) / len(kept)


def rves_question_reward(
    pred_sql: str,
    gold_sql: str,
    db_path: Path,
    *,
    iterations: int = RVES_ITERATIONS,
    timeout_s: float = OFFICIAL_TIMEOUT_S,
) -> float:
    """R-VES reward for one question, following evaluation_ves.py.

    Results must match as sets; then both queries are timed `iterations` times (a fresh connection
    per run), ratios outside mean +/- 3 std are dropped, and the mean ratio maps to a reward. The
    whole procedure shares a `timeout_s * iterations` budget; errors and timeouts score 0.
    """
    budget = _budget(timeout_s * iterations)
    conn = open_readonly(db_path)
    try:
        pred_rows = _fetch_all(conn, pred_sql, budget)
        gold_rows = _fetch_all(conn, gold_sql, budget)
        if not results_match(pred_rows, gold_rows):
            return 0.0
        ratios = []
        for _ in range(iterations):
            pred_time = _timed_run(pred_sql, db_path, budget)
            gold_time = _timed_run(gold_sql, db_path, budget)
            ratios.append(gold_time / pred_time)
    except SqlRunError:
        return 0.0
    finally:
        conn.close()
    return rves_reward(_mean_without_outliers(ratios))
