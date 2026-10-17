"""Behaviour of the sandbox, checked both in-process and through the worker process (`run`)."""

from __future__ import annotations

import dataclasses
import math
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext

import pytest

from text2sql.execution import (
    AccessDenied,
    AccessPolicy,
    ExecutionLimits,
    QueryFailed,
    QueryTimeout,
    ResultTooLarge,
)
from text2sql.execution.sandbox import Sandbox
from text2sql.sqlite_budget import CHECK_INTERVAL, STEPS_PER_SECOND

# (statement, authorizer action that must refuse it). `{dir}` is the database's directory, so a
# successful VACUUM INTO or ATTACH would leave a file next to it.
DENIED = [
    ("INSERT INTO customers (tenant_id) VALUES (1)", "INSERT"),
    ("UPDATE customers SET email = 'x'", "UPDATE"),
    ("DELETE FROM orders", "DELETE"),
    ("REPLACE INTO customers (id, tenant_id) VALUES (1, 1)", "INSERT"),
    ("INSERT INTO customers (id, tenant_id) VALUES (1, 1) ON CONFLICT(id) DO NOTHING", "INSERT"),
    ("WITH c AS (SELECT 1) INSERT INTO numbers SELECT * FROM c", "INSERT"),
    ("WITH c AS (SELECT 1) DELETE FROM numbers", "DELETE"),
    ("WITH c AS (SELECT 1) UPDATE numbers SET n = 0", "UPDATE"),
    ("DROP TABLE customers", None),
    ("DROP VIEW customer_emails", None),
    ("DROP INDEX orders_customer", None),
    ("ALTER TABLE customers ADD COLUMN x INTEGER", "ALTER_TABLE"),
    ("ALTER TABLE customers RENAME TO people", "ALTER_TABLE"),
    ("CREATE TABLE evil (a)", None),
    ("CREATE TEMP TABLE evil (a)", None),
    ("CREATE TEMP VIEW evil AS SELECT 1", None),
    ("CREATE TEMP TRIGGER evil AFTER INSERT ON customers BEGIN SELECT 1; END", None),
    ("CREATE INDEX evil ON customers (email)", None),
    ("CREATE VIRTUAL TABLE evil USING fts5(a)", None),
    ("REINDEX", "REINDEX"),
    ("REINDEX orders_customer", "REINDEX"),
    ("ANALYZE", "ANALYZE"),
    ("VACUUM", "ATTACH"),
    ("VACUUM INTO '{dir}/copy.db'", "ATTACH"),
    ("PRAGMA query_only = OFF", "PRAGMA"),
    ("PRAGMA writable_schema = ON", "PRAGMA"),
    ("PRAGMA table_info(customers)", "PRAGMA"),
    ("SELECT * FROM pragma_table_info('customers')", "READ"),
    ("SELECT name FROM pragma_database_list", "READ"),
    ("ATTACH DATABASE ':memory:' AS other", "ATTACH"),
    ("ATTACH DATABASE '{dir}/other.db' AS other", "ATTACH"),
    ("DETACH DATABASE main", "DETACH"),
    ("BEGIN IMMEDIATE", "TRANSACTION"),
    ("COMMIT", "TRANSACTION"),
    ("ROLLBACK", "TRANSACTION"),
    ("SAVEPOINT s", "SAVEPOINT"),
    ("RELEASE s", "SAVEPOINT"),
    ("SELECT count(*) FROM sqlite_master", "READ"),
    ("WITH c AS MATERIALIZED (SELECT 1) SELECT count(*) FROM sqlite_master", "READ"),
    ("SELECT count(*) FROM pragma_table_info('customers')", "PRAGMA"),
    ("SELECT count(*) FROM dbstat", "READ"),
    ("SELECT * FROM sqlite_master", "READ"),
    ("SELECT sql FROM sqlite_schema", "READ"),
    ("SELECT * FROM main.sqlite_master", "READ"),
    ("SELECT * FROM sqlite_temp_master", "READ"),
    ("SELECT * FROM temp.sqlite_master", "READ"),
    ("SELECT * FROM sqlite_sequence", "READ"),
    ("SELECT * FROM sqlite_stat1", "READ"),
    ("WITH c AS (SELECT name FROM sqlite_master) SELECT * FROM c", "READ"),
    ("SELECT (SELECT sql FROM sqlite_master LIMIT 1)", "READ"),
    ("SELECT id FROM customers WHERE email IN (SELECT name FROM sqlite_master)", "READ"),
    ("SELECT * FROM (SELECT * FROM sqlite_master)", "READ"),
    ("SELECT email FROM customers UNION SELECT name FROM sqlite_master", "READ"),
    ("SELECT id FROM customers WHERE EXISTS (SELECT 1 FROM sqlite_master)", "READ"),
    ("SELECT c.id FROM customers AS c JOIN sqlite_master AS m ON m.name = c.email", "READ"),
    ("SELECT * FROM json_each('[1]')", "READ"),
    ("SELECT * FROM dbstat", "READ"),
    ("SELECT load_extension('x')", "FUNCTION"),
    ("SELECT randomblob(8)", "FUNCTION"),
    ("SELECT zeroblob(8)", "FUNCTION"),
    ("SELECT printf('%s', email) FROM customers", "FUNCTION"),
    ("SELECT format('%s', email) FROM customers", "FUNCTION"),
    ("SELECT sqlite_version()", "FUNCTION"),
    ("SELECT sqlite_compileoption_get(0)", "FUNCTION"),
    ("SELECT fts3_tokenizer('simple')", "FUNCTION"),
    ("SELECT hex(password_hash) FROM customers", "FUNCTION"),
    ("SELECT char(65)", "FUNCTION"),
    ("SELECT json('{{}}')", "FUNCTION"),
    ("SELECT group_concat(email) FROM customers", "FUNCTION"),
    ("SELECT id FROM customers WHERE email GLOB 'c*'", "FUNCTION"),
    ("WITH c AS (SELECT randomblob(8) AS r) SELECT * FROM c", "FUNCTION"),
    ("SELECT id FROM customers WHERE id = abs(random())", "FUNCTION"),
    (
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT x FROM c",
        "RECURSIVE",
    ),
    # SQLite treats a self-referencing CTE as recursive even without the keyword.
    ("WITH c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT x FROM c", "RECURSIVE"),
]

# Rejected by SQLite itself before the authorizer is involved; must still never run.
FAILED = [
    ("SELECT readfile('/etc/passwd')", "no such function: readfile"),
    ("SELECT writefile('{dir}/x', 'y')", "no such function: writefile"),
    ("SELECT id FROM customers WHERE email REGEXP 'c'", "no such function: REGEXP"),
    ("SELECT * FROM generate_series(1, 3)", "no such table: generate_series"),
    ("SELECT 1; DROP TABLE customers", "one statement at a time"),
    ("SELECT 1; ATTACH DATABASE ':memory:' AS other", "one statement at a time"),
]


@pytest.mark.parametrize(("sql", "action"), DENIED)
def test_unsafe_statement_is_denied_and_db_untouched(run, db, digest, sql, action):
    before, files = digest(db), sorted(db.parent.iterdir())
    with pytest.raises(AccessDenied) as caught:
        run(sql.format(dir=db.parent))
    if action is not None:
        assert caught.value.action == action
    assert digest(db) == before
    assert sorted(db.parent.iterdir()) == files


@pytest.mark.parametrize(("sql", "message"), FAILED)
def test_unknown_function_or_second_statement_fails(run, db, digest, sql, message):
    before, files = digest(db), sorted(db.parent.iterdir())
    with pytest.raises(QueryFailed, match=message):
        run(sql.format(dir=db.parent))
    assert digest(db) == before
    assert sorted(db.parent.iterdir()) == files


def test_denial_names_what_was_refused(run):
    with pytest.raises(AccessDenied, match=r"READ sqlite_master\.sql") as caught:
        run("SELECT (SELECT sql FROM sqlite_master LIMIT 1)")
    assert caught.value.target == "sqlite_master.sql"


def test_select_returns_columns_and_plain_rows(run):
    result = run(
        'SELECT c.id, c."Full Name", o.amount, o.receipt, NULL AS missing '
        "FROM customers AS c JOIN orders AS o ON o.customer_id = c.id "
        "WHERE c.id = 2 ORDER BY o.id LIMIT 2"
    )
    assert result.columns == ("id", "Full Name", "amount", "receipt", "missing")
    assert result.rows == (
        (2, "Customer 1", 2.5, bytes([1, 0, 255]), None),
        (2, "Customer 1", 27.5, bytes([11, 0, 255]), None),
    )
    assert not result.truncated
    assert result.elapsed_s >= 0


def test_allowlisted_functions_and_operators_work(run):
    result = run(
        "SELECT COUNT(*), SUM(amount), ROUND(AVG(amount), 2), MIN(id), MAX(id), "
        "ABS(-1), COALESCE(NULL, 'x'), IIF(1 > 0, 'y', 'n'), NULLIF(1, 1), "
        "LENGTH('abc'), UPPER('a'), LOWER('A'), TRIM(' a '), SUBSTR('abc', 2), INSTR('abc', 'c'), "
        "REPLACE('aa', 'a', 'b'), STRFTIME('%Y', '2024-05-01'), DATE('2024-05-01'), "
        "JULIANDAY('2024-05-02') - JULIANDAY('2024-05-01'), CAST('7' AS INTEGER), "
        "CASE WHEN 1 THEN 'case' END, 'a' LIKE 'A', 2 BETWEEN 1 AND 3, 1 IN (1, 2), 'a' || 'b' "
        "FROM orders"
    )
    assert result.rows == (
        (
            30,
            1087.5,
            36.25,
            1,
            30,
            1,
            "x",
            "y",
            None,
            3,
            "A",
            "a",
            "a",
            "bc",
            3,
            "bb",
            "2024",
            "2024-05-01",
            1.0,
            7,
            "case",
            1,
            1,
            1,
            "ab",
        ),
    )


def test_time_keywords_boolean_literals_and_not_like_work(run):
    result = run(
        "SELECT CURRENT_TIMESTAMP IS NOT NULL, CURRENT_DATE IS NOT NULL, "
        "CURRENT_TIME IS NOT NULL, TRUE, FALSE, 'a' NOT LIKE 'b'"
    )
    assert result.rows == ((1, 1, 1, 1, 0, 1),)


def test_cte_subquery_set_operation_and_view_are_allowed(run):
    result = run(
        "WITH big AS (SELECT customer_id FROM orders WHERE amount > 60) "
        "SELECT email FROM customer_emails WHERE id IN (SELECT customer_id FROM big) "
        "UNION SELECT email FROM customers WHERE id = 1 ORDER BY 1"
    )
    emails = tuple((f"c{i}@example.com",) for i in (0, 5, 6, 7, 8, 9))
    assert result.rows == emails


@pytest.mark.parametrize(
    ("sql", "count"),
    [
        ("WITH c AS (SELECT 1 AS a UNION ALL SELECT 2) SELECT count(*) FROM c", 2),
        ("WITH c AS MATERIALIZED (SELECT id FROM customers) SELECT count(*) FROM c", 10),
        ("SELECT count(*) FROM (SELECT id FROM customers UNION SELECT 99)", 11),
        ("SELECT count(*) FROM customer_emails", 10),
    ],
)
def test_counting_rows_of_a_cte_subquery_or_view_is_allowed(run, sql, count):
    assert run(sql).rows == ((count,),)


def test_named_parameters_are_bound_not_interpolated(run):
    injected = "1 OR 1 = 1"
    assert run("SELECT id FROM customers WHERE id = :id", {"id": injected}).rows == ()
    result = run(
        "SELECT COUNT(*) FROM orders WHERE tenant_id = :tenant_id AND amount >= :floor",
        {"tenant_id": 2, "floor": 10.0},
    )
    assert result.rows == ((13,),)


def test_missing_parameter_is_a_query_failure(run):
    with pytest.raises(QueryFailed, match="bindings"):
        run("SELECT id FROM customers WHERE tenant_id = :tenant_id")


def test_out_of_range_parameter_is_a_query_failure(run):
    with pytest.raises(QueryFailed, match="too large"):
        run("SELECT :big", {"big": 2**70})


def test_sqlite_error_text_is_kept_for_repair(run):
    with pytest.raises(QueryFailed) as caught:
        run("SELECT nosuch FROM customers")
    assert str(caught.value) == "no such column: nosuch"


@pytest.mark.parametrize(
    ("max_rows", "returned", "truncated"),
    [(5, 5, True), (10, 10, False), (11, 10, False), (0, 0, True)],
)
def test_row_cap(run, max_rows, returned, truncated):
    result = run("SELECT id FROM customers", limits=ExecutionLimits(max_rows=max_rows))
    assert len(result.rows) == returned
    assert result.truncated is truncated
    assert result.columns == ("id",)


def test_heavy_cross_join_is_interrupted(run):
    started = time.monotonic()
    with pytest.raises(QueryTimeout) as caught:
        run(
            "SELECT COUNT(*) FROM numbers AS a, numbers AS b, numbers AS c",
            limits=ExecutionLimits(timeout_s=0.3),
        )
    assert caught.value.timeout_s == 0.3
    assert time.monotonic() - started < 3.0  # the step budget, long before the 10.3 s kill
    assert run("SELECT COUNT(*) FROM numbers").rows == ((2000,),)  # still usable afterwards


@contextmanager
def gil_contention(threads: int = 4) -> Iterator[None]:
    """Busy Python threads: SQLite runs without the GIL, but every progress-handler call has to
    win it back, so the query slows down by orders of magnitude."""
    done = threading.Event()

    def spin() -> None:
        while not done.is_set():
            pass

    spinners = [threading.Thread(target=spin, daemon=True) for _ in range(threads)]
    for spinner in spinners:
        spinner.start()
    try:
        yield
    finally:
        done.set()
        for spinner in spinners:
            spinner.join()


def test_step_budget_outcome_does_not_depend_on_contention(sandbox, db, steps_used):
    sql = "SELECT COUNT(*) FROM numbers AS a, numbers AS b WHERE a.n < b.n AND a.n < 20"
    steps = steps_used(db, sql)
    enough = ExecutionLimits(
        timeout_s=(steps + CHECK_INTERVAL // 2) / STEPS_PER_SECOND, wall_clock=False
    )
    short = ExecutionLimits(
        timeout_s=(steps - CHECK_INTERVAL // 2) / STEPS_PER_SECOND, wall_clock=False
    )
    for contended in (False, True, False, True):
        with gil_contention() if contended else nullcontext():
            result = sandbox.run(sql, None, enough)
            with pytest.raises(QueryTimeout):
                sandbox.run(sql, None, short)
        assert result.rows == ((39_790,),)
        if contended:  # the wall-clock limit, when on, does stop it
            assert result.elapsed_s > 2 * enough.timeout_s
            with gil_contention(), pytest.raises(QueryTimeout):
                sandbox.run(sql, None, dataclasses.replace(enough, wall_clock=True))


def test_extreme_float_survives_the_round_trip(run):
    assert run("SELECT 1e999, -1e999, 0.1").rows == ((math.inf, -math.inf, 0.1),)


def test_unicode_and_surrogates(run):
    assert run("SELECT 'naïve ☃'").rows == (("naïve ☃",),)
    with pytest.raises(QueryFailed, match="surrogates"):
        run("SELECT '\ud800'")


def test_limits_validation():
    with pytest.raises(ValueError, match="timeout_s"):
        ExecutionLimits(timeout_s=0)
    with pytest.raises(ValueError, match="max_rows"):
        ExecutionLimits(max_rows=-1)
    with pytest.raises(ValueError, match="max_value_bytes"):
        ExecutionLimits(max_value_bytes=0)
    with pytest.raises(ValueError, match="max_result_bytes"):
        ExecutionLimits(max_result_bytes=0)
    with pytest.raises(ValueError, match="max_memory_bytes"):
        ExecutionLimits(max_memory_bytes=0)


def nested_replace(depth: int) -> str:
    """A grammar-valid query whose result grows tenfold per REPLACE."""
    expr = "'aaaaaaaaaa'"
    for _ in range(depth):
        expr = f"REPLACE({expr}, 'a', 'aaaaaaaaaa')"
    return f"SELECT LENGTH({expr})"


def test_value_size_limit_stops_string_amplification(run):
    started = time.monotonic()
    with pytest.raises(ResultTooLarge, match="too big"):
        run(nested_replace(7))  # would build a 100 MB string
    assert time.monotonic() - started < 1.0
    small = run(nested_replace(5), limits=ExecutionLimits(max_value_bytes=2_000_000))
    assert small.rows == ((1_000_000,),)
    with pytest.raises(ResultTooLarge, match="too big"):
        run(nested_replace(5), limits=ExecutionLimits(max_value_bytes=999_999))


def test_result_size_limit_stops_a_large_value_repeated_on_every_row(run, big_text):
    (value,) = run(f"SELECT {big_text} AS v").rows[0]  # one 9.75 MB value fits
    assert len(value) == 9_753_750
    started = time.monotonic()
    with pytest.raises(ResultTooLarge, match="result exceeds 10000000 bytes") as caught:
        run(f"SELECT {big_text} AS v FROM numbers LIMIT 40")  # 390 MB without the limit
    assert isinstance(caught.value, QueryFailed)  # the repair loop handles it like any failure
    assert time.monotonic() - started < 1.0


def test_result_size_counts_names_and_cells_but_not_the_truncation_probe(run):
    sql = "SELECT 'abcd' AS v, NULL AS w, x'00ff' AS b FROM numbers"
    # 8 per name and per cell, plus the length of each name, string and blob.
    size = 3 * (8 + 1) + 3 * ((8 + 4) + 8 + (8 + 2))
    exact = run(sql + " LIMIT 3", limits=ExecutionLimits(max_result_bytes=size))
    assert exact.rows == (("abcd", None, b"\x00\xff"),) * 3
    with pytest.raises(ResultTooLarge):
        run(sql + " LIMIT 3", limits=ExecutionLimits(max_result_bytes=size - 1))
    capped = run(sql, limits=ExecutionLimits(max_rows=3, max_result_bytes=size))
    assert capped.truncated
    assert len(capped.rows) == 3


def test_repeating_a_query_does_not_shift_its_step_count(sandbox, db, steps_used):
    """SQLite starts each run's progress checks from the steps the prepared statement ran
    before; with Python's statement cache a repeated BIRD query was counted as 260,000 and
    270,000 steps on alternate runs, so a query at the edge of its budget flipped."""
    sql = "SELECT COUNT(*) FROM numbers AS a, numbers AS b WHERE a.n < b.n AND a.n < 200"
    steps = steps_used(db, sql)
    enough = ExecutionLimits(
        timeout_s=(steps + CHECK_INTERVAL // 2) / STEPS_PER_SECOND, wall_clock=False
    )
    for _ in range(4):
        assert sandbox.run(sql, None, enough).rows == ((379_900,),)
        sandbox.run("SELECT COUNT(*) FROM orders", None, enough)  # other statements in between


class TestColumnPolicy:
    """A tenant-mode policy: password_hash hidden, tenant_id readable for injected predicates."""

    POLICY = AccessPolicy(
        readable={
            "Customers": frozenset({"id", "tenant_id", "Full Name", "email"}),
            "orders": frozenset({"id", "tenant_id", "customer_id", "amount"}),
            "customer_emails": frozenset({"id", "email"}),
            "sqlite_master": frozenset({"name", "sql"}),  # listing it must not make it readable
            "no_such_table": frozenset({"x"}),
        }
    )

    @pytest.fixture
    def scoped(self, db):
        sandbox = Sandbox(db, self.POLICY)
        yield lambda sql, params=None: sandbox.run(sql, params, ExecutionLimits())
        sandbox.close()

    @pytest.mark.parametrize(
        ("sql", "target"),
        [
            ("SELECT password_hash FROM customers", "customers.password_hash"),
            ("SELECT * FROM customers", "customers.password_hash"),
            ("SELECT id FROM customers WHERE password_hash = 'hash1'", "customers.password_hash"),
            ("SELECT id FROM customers ORDER BY password_hash", "customers.password_hash"),
            (
                "WITH c AS (SELECT password_hash AS p FROM customers) SELECT 1 FROM c",
                "customers.password_hash",
            ),
            ("SELECT receipt FROM orders", "orders.receipt"),
            ("SELECT n FROM numbers", "numbers.n"),
            ("SELECT COUNT(*) FROM numbers", "numbers"),
            ("SELECT COUNT(*) FROM (SELECT n FROM numbers)", "numbers.n"),
            # A CTE that shadows a hidden table is refused too: a harmless false positive.
            ("WITH numbers AS (SELECT 1) SELECT COUNT(*) FROM numbers", "numbers"),
            ("SELECT name FROM sqlite_master", "sqlite_master.name"),
        ],
    )
    def test_hidden_columns_and_tables_are_denied(self, scoped, sql, target):
        with pytest.raises(AccessDenied) as caught:
            scoped(sql)
        assert caught.value.action == "READ"
        assert caught.value.target == target

    def test_visible_columns_and_scoping_predicate_are_allowed(self, scoped):
        result = scoped(
            'SELECT c."Full Name", COUNT(*) FROM customers AS c JOIN orders AS o '
            "ON o.customer_id = c.id WHERE c.tenant_id = :tenant_id AND o.tenant_id = :tenant_id "
            "GROUP BY c.id ORDER BY c.id LIMIT 2",
            {"tenant_id": 1},
        )
        assert result.rows == (("Customer 0", 3), ("Customer 2", 3))
        assert scoped("SELECT COUNT(*) FROM customers").rows == ((10,),)
        emails = scoped("SELECT email FROM customer_emails WHERE id = 1")
        assert emails.rows == (("c0@example.com",),)

    def test_scoping_rewrite_shape_is_allowed(self, scoped):
        """The tenant rewrite wraps each scoped table in a filtered derived table."""
        result = scoped(
            'SELECT T1."Full Name", COUNT(*) FROM '
            '(SELECT "id", "Full Name" FROM "customers" '
            'WHERE "customers"."tenant_id" = :tenant_id) AS T1 '
            'JOIN (SELECT "customer_id" FROM "orders" '
            'WHERE "orders"."tenant_id" = :tenant_id) AS T2 '
            'ON T2."customer_id" = T1."id" GROUP BY T1."id" ORDER BY T1."id" LIMIT 1',
            {"tenant_id": 2},
        )
        assert result.rows == (("Customer 1", 3),)
        counted = scoped(
            'SELECT COUNT(*) FROM (SELECT "id" FROM "customers" '
            'WHERE "customers"."tenant_id" = :tenant_id) AS T1',
            {"tenant_id": 2},
        )
        assert counted.rows == ((5,),)


def test_authorizer_is_not_the_only_write_barrier(db, digest):
    """Each layer assumes the others failed: with the authorizer removed, mode=ro still holds."""
    sandbox = Sandbox(db, AccessPolicy())
    sandbox._con.set_authorizer(None)  # simulate an authorizer bug
    before = digest(db)
    try:
        for sql in ("DELETE FROM orders", "CREATE TABLE evil (a)", "UPDATE numbers SET n = 0"):
            with pytest.raises(AccessDenied) as caught:
                sandbox.run(sql, None, ExecutionLimits())
            assert caught.value.action == "WRITE"
        sandbox._con.execute("PRAGMA query_only = OFF")
        with pytest.raises(AccessDenied, match="readonly database"):
            sandbox.run("DELETE FROM orders", None, ExecutionLimits())
    finally:
        sandbox.close()
    assert digest(db) == before


class TestRecursiveCtes:
    @pytest.fixture
    def recursive(self, db):
        sandbox = Sandbox(db, AccessPolicy(allow_recursive=True))
        yield sandbox
        sandbox.close()

    def test_bounded_recursion_runs_when_allowed(self, recursive):
        result = recursive.run(
            "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 5) "
            "SELECT SUM(x) FROM c",
            None,
            ExecutionLimits(),
        )
        assert result.rows == ((15,),)

    def test_infinite_recursion_is_stopped_by_the_timeout(self, recursive):
        started = time.monotonic()
        with pytest.raises(QueryTimeout):
            recursive.run(
                "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) "
                "SELECT COUNT(*) FROM c",
                None,
                ExecutionLimits(timeout_s=0.3),
            )
        assert time.monotonic() - started < 3.0


def test_open_failures_are_reported(tmp_path):
    with pytest.raises(sqlite3.OperationalError, match="unable to open"):
        Sandbox(tmp_path / "missing.db", AccessPolicy())
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"not a database" * 100)
    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        Sandbox(garbage, AccessPolicy())
