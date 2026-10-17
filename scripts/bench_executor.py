"""Measure the executor overheads quoted in docs/adr/007-sandboxed-executor.md.

Run: uv run --frozen python scripts/bench_executor.py
Builds a throwaway 20,000-row database in a temporary directory; no network access.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import resource
import sqlite3
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from functools import partial
from multiprocessing.context import ForkServerContext, SpawnContext
from pathlib import Path
from typing import Any

from text2sql.execution import AccessPolicy, ExecutionLimits, SandboxedExecutor
from text2sql.execution.sandbox import Sandbox

LIMITS = ExecutionLimits(timeout_s=30.0)
QUERIES = {
    "SELECT 1": "SELECT 1",
    "GROUP BY over 20k rows": "SELECT tenant_id, COUNT(*), AVG(amount) FROM orders GROUP BY 1",
    "1,000-row result": "SELECT id, customer, amount, note FROM orders LIMIT 1000",
}
CPU_BOUND = (
    "SELECT COUNT(*) FROM orders AS a, (SELECT id FROM orders LIMIT 300) AS b WHERE a.amount > b.id"
)


def build_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, tenant_id INT, customer TEXT, "
        "amount REAL, note TEXT)"
    )
    con.executemany(
        "INSERT INTO orders (tenant_id, customer, amount, note) VALUES (?, ?, ?, ?)",
        [(i % 50, f"customer {i}", i * 1.25, "x" * 40) for i in range(20_000)],
    )
    con.commit()
    con.close()
    return path


def measure(fn: Callable[[], object], runs: int) -> tuple[float, float]:
    """Median and p95 wall time in milliseconds, after a short warm-up."""
    for _ in range(min(5, runs)):
        fn()
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1e3)
    return statistics.median(samples), statistics.quantiles(samples, n=20)[-1]


def fetch(con: sqlite3.Connection, sql: str) -> list[Any]:
    return con.execute(sql).fetchmany(1001)


def query_in_child(db: str, sql: str) -> None:
    sandbox = Sandbox(Path(db), AccessPolicy())
    sandbox.run(sql, None, LIMITS)
    sandbox.close()


def process_per_query(
    ctx: SpawnContext | ForkServerContext, db: Path, sql: str
) -> Callable[[], object]:
    def run() -> None:
        child = ctx.Process(target=query_in_child, args=(str(db), sql))
        child.start()
        child.join()

    return run


def executor_per_query(db: Path, sql: str) -> Callable[[], object]:
    def run() -> None:
        with SandboxedExecutor(db, limits=LIMITS) as ex:
            ex.execute(sql)

    return run


async def concurrent_burst(ex: SandboxedExecutor, n: int) -> float:
    await ex.execute_async("SELECT 1")  # start the workers first
    started = time.perf_counter()
    await asyncio.gather(*(ex.execute_async(CPU_BOUND) for _ in range(n)))
    return (time.perf_counter() - started) * 1e3


def main() -> None:
    db = build_db(Path(tempfile.mkdtemp()) / "bench.db")
    print(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}")

    plain = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    sandbox = Sandbox(db, AccessPolicy())
    spawn, forkserver = mp.get_context("spawn"), mp.get_context("forkserver")
    print(
        "\n| Query | Plain sqlite3 | Sandbox in-process | Persistent worker "
        "| New executor per query | spawn per query | forkserver per query |"
    )
    with SandboxedExecutor(db, limits=LIMITS) as executor:
        for label, sql in QUERIES.items():
            cells = [
                measure(partial(fetch, plain, sql), 2000),
                measure(partial(sandbox.run, sql, None, LIMITS), 2000),
                measure(partial(executor.execute, sql), 2000),
                measure(executor_per_query(db, sql), 30),
                measure(process_per_query(spawn, db, sql), 15),
                measure(process_per_query(forkserver, db, sql), 30),
            ]
            row = " | ".join(f"{median:.3g} / {p95:.3g}" for median, p95 in cells)
            print(f"| {label} | {row} |")

    worker_rss_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    cold, _ = measure(executor_per_query(db, "SELECT 1"), 10)
    print(f"\nnew executor + first query (worker start): {cold:.1f} ms median")
    print(f"peak RSS of any worker or child process so far: {worker_rss_mb:.0f} MB")

    bare, _ = measure(partial(fetch, plain, CPU_BOUND), 10)
    guarded, _ = measure(partial(sandbox.run, CPU_BOUND, None, LIMITS), 10)
    print(f"CPU-bound query: plain {bare:.1f} ms, sandbox {guarded:.1f} ms")

    for workers in (1, 2, 4):
        with SandboxedExecutor(db, limits=LIMITS, max_workers=workers) as ex:
            elapsed = asyncio.run(concurrent_burst(ex, 8))
        print(f"8 concurrent CPU-bound queries, max_workers={workers}: {elapsed:.0f} ms")


if __name__ == "__main__":
    main()
