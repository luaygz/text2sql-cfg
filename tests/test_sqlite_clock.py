from __future__ import annotations

import sqlite3

import pytest

from text2sql.sqlite_clock import BENCHMARK_NOW, pin_clock


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    pin_clock(c)
    return c


def test_every_way_of_reading_the_clock_sees_the_pinned_time(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT date('now'), datetime('NOW', 'start of month'), strftime('%Y', 'now'), "
        "CURRENT_DATE, CURRENT_TIME, CURRENT_TIMESTAMP, julianday('now') - julianday('2026-10-15')"
    ).fetchone()
    assert row == (
        BENCHMARK_NOW[:10],
        "2026-10-01 00:00:00",
        "2026",
        "2026-10-16",
        "12:00:00",
        BENCHMARK_NOW,
        1.5,
    )


def test_other_arguments_behave_like_the_builtin_functions(conn: sqlite3.Connection) -> None:
    plain = sqlite3.connect(":memory:")
    sql = (
        "SELECT strftime('%m-%d', '1999-03-04'), date('2001-01-31', '+1 month'), "
        "julianday('2000-01-01'), time('12:34:56', '+1 hour'), date(NULL), strftime('%Y', 'x')"
    )
    assert conn.execute(sql).fetchone() == plain.execute(sql).fetchone()


def test_ages_computed_from_now_no_longer_depend_on_the_day(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE p (born TEXT)")
    conn.execute("INSERT INTO p VALUES ('1990-10-17'), ('1990-10-16')")
    ages = conn.execute(
        "SELECT CAST(strftime('%Y', 'now') AS INTEGER) - CAST(strftime('%Y', born) AS INTEGER)"
        " - (strftime('%m-%d', 'now') < strftime('%m-%d', born)) FROM p ORDER BY born"
    ).fetchall()
    assert ages == [(36,), (35,)]


def test_an_omitted_time_value_reads_the_pinned_clock(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT date(), datetime(), strftime('%Y'), julianday() - julianday('now')")
    assert row.fetchone() == (BENCHMARK_NOW[:10], BENCHMARK_NOW, "2026", 0.0)


def test_a_clock_read_built_at_run_time_is_pinned_too(conn: sqlite3.Connection) -> None:
    assert conn.execute("SELECT date('n' || 'ow')").fetchone() == (BENCHMARK_NOW[:10],)
