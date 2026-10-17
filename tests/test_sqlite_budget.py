from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from text2sql.sqlite_budget import CHECK_INTERVAL, step_budget, steps_for

COUNT = (
    "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 50000) "
    "SELECT COUNT(*) FROM n"
)


def _run(steps: int) -> tuple[bool, int]:
    """(finished, steps charged) for COUNT under a budget of `steps`."""
    conn = sqlite3.connect(":memory:")
    try:
        with step_budget(conn, steps) as budget:
            try:
                conn.execute(COUNT).fetchall()
            except sqlite3.OperationalError:
                assert budget.exhausted
                return False, budget.used
            return True, budget.used
    finally:
        conn.close()


def test_the_same_query_is_charged_the_same_steps_every_time() -> None:
    finished, used = _run(10**12)
    assert finished
    assert {_run(10**12)[1] for _ in range(3)} == {used}


def test_the_outcome_at_the_limit_does_not_depend_on_machine_load() -> None:
    _, used = _run(10**12)
    stop = threading.Event()

    def burn() -> None:
        while not stop.is_set():
            sum(range(10_000))

    burners = [threading.Thread(target=burn) for _ in range(4)]
    for t in burners:
        t.start()
    try:
        slow = [_run(used) for _ in range(3)], [_run(used - CHECK_INTERVAL) for _ in range(3)]
    finally:
        stop.set()
        for t in burners:
            t.join()
    assert all(finished for finished, _ in slow[0])
    assert not any(finished for finished, _ in slow[1])


def test_a_budget_ignores_wall_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # A clock that jumps an hour per call would end any wall-clock deadline at once.
    real = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real() + 3600 * (real() % 1000))
    assert _run(10**12)[0]


def test_seconds_convert_to_a_positive_step_count() -> None:
    assert steps_for(30) > steps_for(2) >= CHECK_INTERVAL
    with pytest.raises(ValueError):
        steps_for(0)
