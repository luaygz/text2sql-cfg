from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from text2sql.execution import (
    AccessPolicy,
    ExecutionLimits,
    Params,
    QueryResult,
    SandboxedExecutor,
)
from text2sql.execution.sandbox import Sandbox
from text2sql.sqlite_budget import step_budget

type Run = Callable[..., QueryResult]

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    "Full Name" TEXT,
    email TEXT,
    password_hash TEXT
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    amount REAL,
    receipt BLOB
);
CREATE INDEX orders_customer ON orders(customer_id);
CREATE VIEW customer_emails AS SELECT id, email FROM customers;
CREATE TABLE numbers (n INTEGER);
"""


def build_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany(
        'INSERT INTO customers (tenant_id, "Full Name", email, password_hash) VALUES (?, ?, ?, ?)',
        [(1 + i % 2, f"Customer {i}", f"c{i}@example.com", f"hash{i}") for i in range(10)],
    )
    con.executemany(
        "INSERT INTO orders (tenant_id, customer_id, amount, receipt) VALUES (?, ?, ?, ?)",
        [(1 + i % 2, 1 + i % 10, i * 2.5, bytes([i, 0, 255])) for i in range(30)],
    )
    con.executemany("INSERT INTO numbers VALUES (?)", [(i,) for i in range(2000)])
    con.commit()
    con.execute("ANALYZE")  # creates sqlite_stat1, another internal table that must stay hidden
    con.commit()
    con.close()
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker_pids() -> set[int]:
    """Live sandbox worker processes started by this test process (Linux /proc)."""
    me = os.getpid()
    pids: set[int] = set()
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
            cmdline = (stat.parent / "cmdline").read_bytes()
        except OSError:
            continue
        if int(fields[1]) == me and b"text2sql.execution.worker" in cmdline:
            pids.add(int(stat.parent.name))
    return pids


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_db(tmp_path_factory.mktemp("exec") / "shop.db")


@pytest.fixture
def fresh_db(tmp_path: Path) -> Path:
    """A private copy of the fixture database, for tests that kill workers or compare files."""
    return build_db(tmp_path / "shop.db")


@pytest.fixture(name="digest")
def digest_fixture() -> Callable[[Path], str]:
    return digest


@pytest.fixture(name="worker_pids")
def worker_pids_fixture() -> Callable[[], set[int]]:
    if not Path("/proc/self/stat").exists():
        pytest.skip("needs Linux /proc to find worker processes")
    return worker_pids


@pytest.fixture(scope="session")
def big_text() -> str:
    """SQL for a constant 9,753,750-character string: under the 10 MB value limit, built in
    milliseconds, and computed once by SQLite however many rows or columns repeat it."""
    return f"REPLACE(REPLACE('{'a' * 150}', 'a', '{'a' * 255}'), 'a', '{'b' * 255}')"


def steps_used(db: Path, sql: str) -> int:
    """Steps a query takes under the shared accounting (`text2sql.sqlite_budget`), measured on a
    plain read-only connection that, like the sandbox's, prepares every statement afresh."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, cached_statements=0)
    try:
        with step_budget(con, 10**15) as budget:
            con.execute(sql).fetchall()
        return budget.used
    finally:
        con.close()


@pytest.fixture(name="steps_used")
def steps_used_fixture() -> Callable[[Path, str], int]:
    return steps_used


@pytest.fixture(scope="module")
def executor(db: Path) -> Iterator[SandboxedExecutor]:
    with SandboxedExecutor(db) as ex:
        yield ex


@pytest.fixture(scope="module")
def sandbox(db: Path) -> Iterator[Sandbox]:
    sb = Sandbox(db, AccessPolicy())
    yield sb
    sb.close()


@pytest.fixture(params=["in-process", "worker"])
def run(request: pytest.FixtureRequest, sandbox: Sandbox, executor: SandboxedExecutor) -> Run:
    """The same checks against the in-process sandbox and through the worker process."""
    if request.param == "in-process":

        def run_in_process(
            sql: str, params: Params | None = None, *, limits: ExecutionLimits | None = None
        ) -> QueryResult:
            return sandbox.run(sql, params, limits or ExecutionLimits())

        return run_in_process
    return executor.execute
