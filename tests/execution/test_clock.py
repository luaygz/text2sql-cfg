"""A pinned "now" for benchmark limits, the real clock otherwise, and no loss of protection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from text2sql.execution import (
    AccessDenied,
    AccessPolicy,
    ExecutionLimits,
    QueryTimeout,
    ResultTooLarge,
    SandboxedExecutor,
)
from text2sql.execution.sandbox import Sandbox
from text2sql.sqlite_clock import BENCHMARK_NOW

BENCHMARK = ExecutionLimits(timeout_s=1.0, wall_clock=False, clock=BENCHMARK_NOW)
PRODUCTION = ExecutionLimits(timeout_s=1.0, max_rows=200)
EVERY_WAY_TO_READ_THE_CLOCK = (
    "SELECT date('now'), DATE('NOW', 'start of month'), CURRENT_DATE, CURRENT_TIME, "
    "CURRENT_TIMESTAMP, strftime('%Y', 'now'), strftime('%Y-%m-%d %H:%M'), date(), "
    "julianday('now') - julianday('2026-10-15'), date('n' || 'ow')"
)
PINNED = (
    "2026-10-16",
    "2026-10-01",
    "2026-10-16",
    "12:00:00",
    "2026-10-16 12:00:00",
    "2026",
    "2026-10-16 12:00",
    "2026-10-16",
    1.5,
    "2026-10-16",
)


@pytest.fixture(scope="module")
def pinned_executor(db):
    with SandboxedExecutor(db, limits=BENCHMARK) as ex:
        yield ex


@pytest.fixture(scope="module")
def pinned_sandbox(db):
    sandbox = Sandbox(db, AccessPolicy(), clock=BENCHMARK_NOW)
    yield sandbox
    sandbox.close()


@pytest.fixture(params=["in-process", "worker"])
def pinned(request, pinned_sandbox, pinned_executor):
    """Run a statement with benchmark limits, in-process or through a worker."""
    if request.param == "in-process":
        return lambda sql: pinned_sandbox.run(sql, None, BENCHMARK)
    return pinned_executor.execute


def test_benchmark_limits_read_the_pinned_clock_however_it_is_asked(pinned):
    assert pinned(EVERY_WAY_TO_READ_THE_CLOCK).rows == (PINNED,)


def test_ages_from_now_are_the_same_on_any_day(pinned):
    result = pinned(
        "SELECT CAST(strftime('%Y', 'now') AS INTEGER) - CAST(strftime('%Y', '1990-10-17') AS "
        "INTEGER) - (strftime('%m-%d', 'now') < strftime('%m-%d', '1990-10-17'))"
    )
    assert result.rows == ((35,),)


def test_other_date_arithmetic_is_unchanged(pinned, run):
    sql = (
        "SELECT strftime('%m-%d', '1999-03-04'), date('2001-01-31', '+1 month'), "
        "julianday('2000-01-01'), date(NULL), strftime('%Y', 'x')"
    )
    assert pinned(sql).rows == run(sql).rows


def real_now_matches(timestamp: str, slack_s: float = 5.0) -> bool:
    value = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    return abs((datetime.now(UTC) - value).total_seconds()) <= slack_s


def test_production_limits_read_the_real_clock(run, pinned):
    pinned("SELECT CURRENT_TIMESTAMP")  # a pinned connection elsewhere changes nothing here
    now, omitted, from_now = run(
        "SELECT CURRENT_TIMESTAMP, date(), date('now')", limits=PRODUCTION
    ).rows[0]
    assert real_now_matches(now)
    assert omitted == from_now == now[:10]


@pytest.mark.parametrize(
    ("sql", "action", "target"),
    [
        ("SELECT datetime('now')", "FUNCTION", "datetime"),
        ("SELECT time()", "FUNCTION", "time"),
        ("SELECT unixepoch()", "FUNCTION", "unixepoch"),
        ("SELECT randomblob(4), date('now')", "FUNCTION", "randomblob"),
        ("SELECT name FROM sqlite_master WHERE date('now') > ''", "READ", "sqlite_master.name"),
        ("DELETE FROM orders WHERE date('now') > ''", "DELETE", "orders"),
    ],
)
def test_pinned_connection_keeps_the_authorizer(pinned, sql, action, target):
    with pytest.raises(AccessDenied) as caught:
        pinned(sql)
    assert (caught.value.action, caught.value.target) == (action, target)


def test_pinned_connection_keeps_the_step_budget_and_size_limits(pinned):
    with pytest.raises(QueryTimeout):
        pinned(
            "SELECT COUNT(*) FROM numbers AS a, numbers AS b, numbers AS c "
            "WHERE date('now') IS NOT NULL"
        )
    huge = "'aaaaaaaaaa'"
    for _ in range(7):  # a 100 MB string, over the 10 MB value limit
        huge = f"REPLACE({huge}, 'a', 'aaaaaaaaaa')"
    with pytest.raises(ResultTooLarge, match="too big"):
        pinned(f"SELECT date('now') || {huge}")


def test_the_clock_is_fixed_for_the_life_of_an_executor(db, pinned_executor, pinned_sandbox):
    with pytest.raises(ValueError, match="clock"):
        pinned_executor.execute("SELECT 1", limits=PRODUCTION)
    with pytest.raises(ValueError, match="clock"):
        pinned_sandbox.run("SELECT 1", None, PRODUCTION)
    with SandboxedExecutor(db) as unpinned, pytest.raises(ValueError, match="clock"):
        unpinned.execute("SELECT 1", limits=BENCHMARK)
    assert pinned_executor.execute("SELECT 1").rows == ((1,),)  # still usable


@pytest.mark.parametrize("clock", ["2026-10-16", "now", "2026-10-16T12:00:00", ""])
def test_clock_must_be_a_full_timestamp(clock):
    with pytest.raises(ValueError, match="YYYY-MM-DD HH:MM:SS"):
        ExecutionLimits(clock=clock)
