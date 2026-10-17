"""normalize_sql: canonical spelling for gold SQL, without changing what a query returns."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from text2sql.catalog.schema import DatabaseSchema
from text2sql.grammar import NormalizationError, SqlGrammar, normalize_sql


@pytest.mark.parametrize(
    ("gold", "expected"),
    [
        (
            'select t.name from customers t where t.city = "Paris"',
            "SELECT T1.name FROM customers AS T1 WHERE T1.city = 'Paris'",
        ),
        (
            "SELECT name, count(*) as n FROM customers GROUP BY name ORDER BY n DESC LIMIT 5, 10",
            "SELECT name, COUNT(*) AS c1 FROM customers AS T1 GROUP BY name ORDER BY c1 DESC"
            " LIMIT 10 OFFSET 5",
        ),
        (
            "WITH big AS (SELECT * FROM orders WHERE amount > 100) SELECT COUNT(*) FROM big",
            "WITH cte1 AS (SELECT * FROM orders AS T1 WHERE amount > 100) SELECT COUNT(*)"
            " FROM cte1",
        ),
        (
            'SELECT `order`, "Signup Date", [city] FROM CUSTOMERS',
            "SELECT `order`, `Signup Date`, city FROM customers AS T1",
        ),
        (
            "SELECT T2.name FROM customers AS T2 JOIN orders AS a ON a.customer_id = T2.id",
            "SELECT T2.name FROM customers AS T2 JOIN orders AS T1 ON T1.customer_id = T2.id",
        ),
        (
            "SELECT customers.name FROM customers, orders WHERE orders.customer_id = customers.id",
            "SELECT T1.name FROM customers AS T1 CROSS JOIN orders AS T2"
            " WHERE T2.customer_id = T1.id",
        ),
        (
            "SELECT IFNULL(status, 'x'), substr(status, 2) FROM orders WHERE amount != 1"
            " AND id NOT IN (1) AND status IS NOT NULL",
            "SELECT COALESCE(status, 'x'), SUBSTR(status, 2) FROM orders AS T1 WHERE amount <> 1"
            " AND NOT id IN (1) AND NOT status IS NULL",
        ),
    ],
)
def test_canonical_spelling(shop_schema: DatabaseSchema, gold: str, expected: str) -> None:
    assert normalize_sql(gold, shop_schema) == expected


def test_cast_keeps_the_type_affinity(shop_schema: DatabaseSchema) -> None:
    gold = (
        "SELECT CAST(Date AS DATE), CAST(status AS VARCHAR(10)), CAST(amount AS FLOAT),"
        " CAST(amount AS BIGINT), CAST(amount AS DECIMAL(5, 2)) FROM orders"
    )
    assert normalize_sql(gold, shop_schema) == (
        "SELECT CAST(Date AS NUMERIC), CAST(status AS TEXT), CAST(amount AS REAL),"
        " CAST(amount AS INTEGER), CAST(amount AS NUMERIC) FROM orders AS T1"
    )


def test_aliases_that_are_schema_columns_are_kept(shop_schema: DatabaseSchema) -> None:
    gold = "SELECT T.city AS CITY FROM (SELECT city FROM customers) AS T ORDER BY CITY"
    assert normalize_sql(gold, shop_schema) == (
        "SELECT T1.city AS city FROM (SELECT city FROM customers AS T2) AS T1 ORDER BY city"
    )


def test_without_schema_only_spelling_and_aliases_change() -> None:
    assert normalize_sql("select x as total from t where y = 1") == (
        "SELECT x AS total FROM t AS T1 WHERE y = 1"
    )


@pytest.mark.parametrize(
    "gold",
    [
        "SELECT 1; SELECT 2",
        "DROP TABLE customers",
        "SELECT FROM WHERE",
        "WITH a AS (SELECT 1), b AS (SELECT 1), c AS (SELECT 1), d AS (SELECT 1),"
        " e AS (SELECT 1), f AS (SELECT 1) SELECT 1",
        "SELECT 1 FROM t AS a, t AS b, t AS c, t AS d, t AS e, t AS f, t AS g, t AS h, t AS i,"
        " t AS j",
    ],
)
def test_unnormalizable_input_raises(gold: str) -> None:
    with pytest.raises(NormalizationError):
        normalize_sql(gold)


SAME_RESULT = [
    "select c.name, count(o.id) cnt from customers c left join orders o on o.customer_id = c.id"
    " group by c.name order by cnt desc, c.name",
    'SELECT name FROM customers WHERE city = "Paris" OR city IS NULL',
    "SELECT CAST(Date AS DATE), CAST(amount AS INT) / 2 FROM orders",
    "WITH s AS (SELECT customer_id, SUM(amount) total FROM orders GROUP BY customer_id)"
    " SELECT customers.name, s.total FROM customers JOIN s ON s.customer_id = customers.id",
    "SELECT name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders"
    " WHERE status = 'paid') LIMIT 1, 5",
    "SELECT o.status FROM orders o WHERE o.amount > (SELECT AVG(o.amount) FROM orders o)",
    "SELECT `qty (units)` * 2 FROM `order items` WHERE product LIKE 'p%'",
    "SELECT name FROM customers WHERE city <> '(-none)' OR name IN ('+', '-1', '.x')",
]


@pytest.mark.parametrize("gold", SAME_RESULT)
def test_normalized_sql_returns_the_same_rows_and_parses(
    shop_db: Path, shop_schema: DatabaseSchema, benchmark_grammar: SqlGrammar, gold: str
) -> None:
    normalized = normalize_sql(gold, shop_schema)
    conn = sqlite3.connect(f"file:{shop_db}?mode=ro", uri=True)
    try:
        before = Counter(conn.execute(gold).fetchall())
        after = Counter(conn.execute(normalized).fetchall())
    finally:
        conn.close()
    assert before == after
    assert benchmark_grammar.accepts(normalized), normalized


def test_literals_opening_with_trap_punctuation_become_concatenations() -> None:
    assert normalize_sql("SELECT a FROM t WHERE b = '(none)' AND c = '+' AND d = '-1 day'") == (
        "SELECT a FROM t AS T1 WHERE b = ('(' || 'none)') AND c = '+' AND d = '-1 day'"
    )
    assert normalize_sql("SELECT '*+1'") == "SELECT ('*' || '+1')"
