"""The process boundary: hard kills, respawn, pooling, async and thread safety, lifecycle."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from text2sql.execution import (
    ExecutionError,
    ExecutionLimits,
    QueryFailed,
    QueryTimeout,
    ResultTooLarge,
    SandboxedExecutor,
)
from text2sql.execution import executor as executor_module
from text2sql.sqlite_budget import CHECK_INTERVAL, STEPS_PER_SECOND

HEAVY = "SELECT COUNT(*) FROM numbers AS a, numbers AS b, numbers AS c"
MEDIUM = "SELECT COUNT(*) FROM numbers AS a, numbers AS b WHERE a.n < b.n"


def wait_for(predicate, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.01)


def process_state(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return None


@contextmanager
def throttled(pid: int) -> Iterator[None]:
    """Let the process run 1 ms in every 10 ms, as on a machine about ten times as busy."""
    done = threading.Event()

    def toggle() -> None:
        while not done.is_set():
            os.kill(pid, signal.SIGSTOP)
            time.sleep(0.009)
            os.kill(pid, signal.SIGCONT)
            time.sleep(0.001)

    thread = threading.Thread(target=toggle, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        os.kill(pid, signal.SIGCONT)


def test_hung_worker_is_killed_and_replaced(fresh_db, worker_pids):
    limits = ExecutionLimits(timeout_s=0.3)  # wall clock on: killed 1 s after the limit
    kill_s = executor_module.kill_after(limits)
    with SandboxedExecutor(fresh_db, limits=limits, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        os.kill(pid, signal.SIGSTOP)  # a worker stuck where the progress handler cannot reach

        started = time.monotonic()
        with pytest.raises(QueryTimeout, match=r"0\.3 s"):
            ex.execute("SELECT 1")
        elapsed = time.monotonic() - started

        assert kill_s - 0.05 <= elapsed < kill_s + 2.0
        assert process_state(pid) is None  # killed and reaped, not left as a zombie
        assert ex.execute("SELECT 2").rows == ((2,),)
        (replacement,) = worker_pids() - before
        assert replacement != pid


@pytest.mark.parametrize("wall_clock", [True, False])
def test_soft_timeout_keeps_the_worker(fresh_db, worker_pids, wall_clock):
    limits = ExecutionLimits(timeout_s=0.2, wall_clock=wall_clock)
    with SandboxedExecutor(fresh_db, limits=limits, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 3")
        pids = worker_pids() - before
        with pytest.raises(QueryTimeout):
            ex.execute(HEAVY)
        assert ex.execute("SELECT 3").rows == ((3,),)
        assert worker_pids() - before == pids  # stopped inside the worker, not by the kill


def slow_text_query(rows: int) -> str:
    """About 13 VM steps per pair, each pair building and scanning a 100 kB string: tens of
    microseconds per step, hundreds of times slower than the step calibration assumes."""
    return (
        f"SELECT COUNT(*) FROM numbers AS a, (SELECT n FROM numbers LIMIT {rows}) AS b "
        f"WHERE REPLACE('{'a' * 1000}' || a.n || b.n, 'a', '{'a' * 100}') LIKE '%z%'"
    )


def test_wall_clock_limit_stops_a_slow_query_far_from_its_step_budget(fresh_db, worker_pids):
    sql = slow_text_query(rows=75)
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        pids = worker_pids() - before

        production = ExecutionLimits(timeout_s=1.0, max_rows=200)
        started = time.monotonic()
        with pytest.raises(QueryTimeout):
            ex.execute(sql, limits=production)
        assert 1.0 <= time.monotonic() - started < executor_module.kill_after(production)
        assert worker_pids() - before == pids  # the progress handler stopped it, not the kill

        # The same limit counted in steps alone lets it run past 1 s to completion: its step
        # count is far below the budget.
        benchmark = ExecutionLimits(timeout_s=1.0, wall_clock=False)
        result = ex.execute(sql, limits=benchmark)
        assert result.rows == ((0,),)
        assert result.elapsed_s > benchmark.timeout_s


@pytest.mark.skipif(sys.platform != "linux", reason="throttles the worker with SIGSTOP/SIGCONT")
def test_step_budget_outcome_does_not_depend_on_load(fresh_db, worker_pids, steps_used):
    """Without a wall-clock limit, a query given just enough steps finishes, and one given one
    check too few times out, the same way on an idle worker and on one slowed tenfold, and every
    time it is repeated."""
    sql = MEDIUM + " AND a.n < 500"
    steps = steps_used(fresh_db, sql)
    enough = ExecutionLimits(
        timeout_s=(steps + CHECK_INTERVAL // 2) / STEPS_PER_SECOND, wall_clock=False
    )
    short = ExecutionLimits(
        timeout_s=(steps - CHECK_INTERVAL // 2) / STEPS_PER_SECOND, wall_clock=False
    )
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        for slowed in (False, True, False, True):
            with throttled(pid) if slowed else nullcontext():
                result = ex.execute(sql, limits=enough)
                with pytest.raises(QueryTimeout):
                    ex.execute(sql, limits=short)
            assert result.rows == ((874_750,),)
            if slowed:  # with `wall_clock` on, the same limit would have stopped it
                assert result.elapsed_s > 2 * enough.timeout_s
        assert worker_pids() - before == {pid}


@pytest.mark.parametrize("wall_clock", [True, False])
def test_work_hidden_inside_single_steps_is_stopped_by_the_kill(
    fresh_db, worker_pids, monkeypatch, wall_clock
):
    """Each row is one REPLACE building 9.75 MB in a handful of VM steps (several ms of work), so
    the progress handler is not called for hundreds of rows; only the kill ends the query."""
    monkeypatch.setattr(executor_module, "KILL_MIN_GRACE_S", 0.5)  # steps only: kill after 0.6 s
    expr = f"REPLACE(REPLACE('{'a' * 150}' || n, 'a', '{'a' * 255}'), 'a', '{'b' * 255}')"
    limits = ExecutionLimits(timeout_s=0.1, wall_clock=wall_clock)
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        started = time.monotonic()
        with pytest.raises(QueryTimeout):
            ex.execute(f"SELECT LENGTH({expr}) FROM numbers", limits=limits)
        assert time.monotonic() - started >= executor_module.kill_after(limits) - 0.05
        assert process_state(pid) is None
        assert ex.execute("SELECT 4").rows == ((4,),)


def test_worker_that_died_while_idle_is_replaced_without_an_error(fresh_db, worker_pids):
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: process_state(pid) in (None, "Z"))
        assert ex.execute("SELECT 4").rows == ((4,),)
        assert pid not in worker_pids()


def test_worker_crash_mid_query_is_reported_not_retried(fresh_db, worker_pids):
    with SandboxedExecutor(fresh_db, limits=ExecutionLimits(timeout_s=10), max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(ex.execute, HEAVY)
            time.sleep(0.2)
            os.kill(pid, signal.SIGKILL)
            with pytest.raises(ExecutionError, match="exited unexpectedly") as caught:
                pending.result(timeout=5)
        assert type(caught.value) is ExecutionError
        assert ex.execute("SELECT 5").rows == ((5,),)


def test_per_call_limits_override_the_executor_defaults(executor):
    assert len(executor.execute("SELECT n FROM numbers").rows) == 1000
    capped = executor.execute("SELECT n FROM numbers", limits=ExecutionLimits(max_rows=3))
    assert capped.rows == ((0,), (1,), (2,))
    assert capped.truncated
    with pytest.raises(QueryTimeout):
        executor.execute(HEAVY, limits=ExecutionLimits(timeout_s=0.1))


@pytest.mark.skipif(sys.platform != "linux", reason="the memory cap uses Linux RLIMIT_DATA")
def test_memory_cap_stops_a_wide_row_and_the_worker_survives(fresh_db, worker_pids, big_text):
    """One row of 30 copies of a 9.75 MB value is converted whole before any byte count can see
    it; only the worker's RLIMIT_DATA stops it."""
    wide_row = "SELECT " + ", ".join([big_text] * 30)
    small_heap = ExecutionLimits(max_memory_bytes=8 * 2**20)
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        pids = worker_pids() - before
        started = time.monotonic()
        with pytest.raises(ResultTooLarge, match="out of memory"):
            ex.execute(wide_row)
        assert time.monotonic() - started < 2.0
        # The cap is per call: 8 MiB still runs small queries but not one 9.75 MB value.
        assert ex.execute("SELECT 2", limits=small_heap).rows == ((2,),)
        with pytest.raises(ResultTooLarge, match="out of memory"):
            ex.execute(f"SELECT {big_text}", limits=small_heap)
        assert len(ex.execute(f"SELECT {big_text}").rows[0][0]) == 9_753_750
        assert worker_pids() - before == pids  # the same worker throughout


def test_oversized_reply_is_refused_unread_and_the_worker_replaced(
    fresh_db, worker_pids, monkeypatch
):
    """A compromised worker must not be able to make the parent allocate an arbitrary reply."""
    with SandboxedExecutor(fresh_db, max_workers=1) as ex:
        before = worker_pids()
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
        monkeypatch.setattr(executor_module, "max_reply_bytes", lambda *_: 16)
        with pytest.raises(ExecutionError, match="bad message length") as caught:
            ex.execute("SELECT 'more than sixteen bytes of reply'")
        assert type(caught.value) is ExecutionError
        assert process_state(pid) is None
        monkeypatch.undo()
        assert ex.execute("SELECT 7").rows == ((7,),)


def test_close_stops_workers_and_rejects_new_queries(fresh_db, worker_pids):
    before = worker_pids()
    with SandboxedExecutor(fresh_db) as ex:
        ex.execute("SELECT 1")
        (pid,) = worker_pids() - before
    assert process_state(pid) is None
    with pytest.raises(RuntimeError, match="closed"):
        ex.execute("SELECT 1")
    ex.close()  # idempotent


def test_worker_busy_during_close_is_stopped_when_its_query_ends(fresh_db, worker_pids):
    before = worker_pids()
    ex = SandboxedExecutor(fresh_db, limits=ExecutionLimits(timeout_s=0.3))
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(ex.execute, HEAVY)
        wait_for(lambda: len(worker_pids() - before) == 1)
        ex.close()
        with pytest.raises(QueryTimeout):
            pending.result(timeout=5)
    assert worker_pids() - before == set()


def test_constructor_validates_arguments(tmp_path):
    with pytest.raises(FileNotFoundError):
        SandboxedExecutor(tmp_path / "missing.db")
    with pytest.raises(ValueError, match="max_workers"):
        SandboxedExecutor(tmp_path, max_workers=0)


def test_unreadable_database_fails_each_query_without_hanging(tmp_path):
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"not a database" * 100)
    with SandboxedExecutor(garbage, max_workers=1) as ex:
        for _ in range(2):
            with pytest.raises(QueryFailed, match="not a database"):
                ex.execute("SELECT 1")


def test_worker_that_does_not_start_in_time_is_killed(fresh_db, worker_pids, monkeypatch):
    monkeypatch.setattr(executor_module, "STARTUP_TIMEOUT_S", 0.001)
    before = worker_pids()
    with (
        SandboxedExecutor(fresh_db) as ex,
        pytest.raises(ExecutionError, match="did not start"),
    ):
        ex.execute("SELECT 1")
    assert worker_pids() - before == set()


def test_execute_async_keeps_the_event_loop_running(fresh_db):
    async def scenario(ex: SandboxedExecutor) -> int:
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(ticker())
        with pytest.raises(QueryTimeout):
            await ex.execute_async(HEAVY, limits=ExecutionLimits(timeout_s=1.0))
        task.cancel()
        return ticks

    with SandboxedExecutor(fresh_db) as ex:
        assert asyncio.run(scenario(ex)) >= 10
        # A second event loop gets its own gate.
        assert asyncio.run(ex.execute_async("SELECT :x", {"x": 7})).rows == ((7,),)


def test_concurrent_async_calls_share_a_bounded_pool(fresh_db, worker_pids):
    async def burst(ex: SandboxedExecutor) -> list[tuple[tuple[object, ...], ...]]:
        results = await asyncio.gather(
            *(ex.execute_async(MEDIUM + " AND a.n < :k", {"k": k}) for k in range(6))
        )
        return [result.rows for result in results]

    before = worker_pids()
    with SandboxedExecutor(fresh_db, max_workers=2) as ex:
        rows = asyncio.run(burst(ex))
        assert len(worker_pids() - before) == 2
    expected = [((sum(1999 - n for n in range(k)),),) for k in range(6)]
    assert rows == expected


def test_execute_is_thread_safe(fresh_db, worker_pids):
    before = worker_pids()
    seen_workers: set[int] = set()
    lock = threading.Lock()

    def query(k: int) -> tuple[tuple[object, ...], ...]:
        rows = ex.execute("SELECT n FROM numbers WHERE n = :k", {"k": k}).rows
        with lock:
            seen_workers.update(worker_pids() - before)
        return rows

    with SandboxedExecutor(fresh_db, max_workers=3) as ex, ThreadPoolExecutor(8) as pool:
        results = list(pool.map(query, range(40)))
    assert results == [((k,),) for k in range(40)]
    assert 1 <= len(seen_workers) <= 3
