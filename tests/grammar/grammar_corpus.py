"""Hand-written queries over the `shop` fixture schema (see conftest.py), in canonical spelling."""

from __future__ import annotations

VALID = [
    # multi-join, aggregation, HAVING, computed-column alias reused in ORDER BY
    "SELECT T1.name, SUM(T2.amount) AS c1 FROM customers AS T1 INNER JOIN orders AS T2"
    " ON T1.id = T2.customer_id LEFT JOIN `order items` AS T3 ON T3.order_id = T2.id"
    " WHERE T2.status = 'paid' GROUP BY T1.name HAVING COUNT(*) > 1 ORDER BY c1 DESC LIMIT 10",
    # nested and correlated subqueries, EXISTS
    "SELECT T1.name FROM customers AS T1 WHERE T1.id IN (SELECT T2.customer_id FROM orders AS T2"
    " WHERE T2.amount > (SELECT AVG(T3.amount) FROM orders AS T3)) AND NOT EXISTS(SELECT 1"
    " FROM orders AS T4 WHERE T4.customer_id = T1.id AND T4.status = 'refunded')",
    # two CTEs, derived columns referenced through an alias and unqualified
    "WITH cte1 AS (SELECT T1.customer_id, COUNT(*) AS c1 FROM orders AS T1 GROUP BY"
    " T1.customer_id), cte2 AS (SELECT MAX(c1) AS c2 FROM cte1) SELECT T2.name FROM cte1 AS T1"
    " INNER JOIN customers AS T2 ON T2.id = T1.customer_id WHERE T1.c1 = (SELECT c2 FROM cte2)",
    # every set operator
    "SELECT city FROM customers UNION SELECT status FROM orders EXCEPT SELECT 'x' INTERSECT"
    " SELECT name FROM customers UNION ALL SELECT product FROM `order items`",
    "SELECT CAST(SUM(CASE WHEN T1.status = 'paid' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*)"
    " FROM orders AS T1",
    "SELECT CASE T1.status WHEN 'paid' THEN 'ok' WHEN 'refunded' THEN 'back' END,"
    " CAST(T1.amount AS INTEGER), CAST(T1.amount AS TEXT), CAST(T1.Date AS NUMERIC)"
    " FROM orders AS T1",
    "SELECT STRFTIME('%Y', T1.created_at), JULIANDAY('now') - JULIANDAY(T1.created_at),"
    " DATE(T1.created_at, '-1 day') FROM orders AS T1"
    " WHERE T1.created_at BETWEEN '2020-01-01' AND '2020-12-31'",
    "SELECT T1.`Signup Date`, T1.`order`, T2.`qty (units)` FROM customers AS T1"
    " INNER JOIN `order items` AS T2 ON T2.order_id = T1.id WHERE T2.`qty (units)` >= 2",
    "SELECT UPPER(TRIM(T1.name)) || ', ' || LOWER(T1.city) FROM customers AS T1"
    " WHERE T1.city IS NOT NULL AND T1.name LIKE 'A%' AND T1.name NOT LIKE '%''s'"
    " AND NOT T1.city IS NULL",
    "SELECT ROUND(ABS(T1.amount), 2), COALESCE(T1.status, 'none'), IIF(T1.amount > 100, 'big',"
    " 'small'), NULLIF(T1.amount, 0), LENGTH(T1.status), SUBSTR(T1.status, 1, 3),"
    " INSTR(T1.status, 'a'), REPLACE(T1.status, 'a', 'b') FROM orders AS T1",
    "SELECT T3.c1 FROM (SELECT T1.city, COUNT(*) AS c1 FROM customers AS T1 GROUP BY T1.city)"
    " AS T3 ORDER BY T3.c1 DESC LIMIT 1 OFFSET 2",
    "SELECT * FROM customers",
    "SELECT T1.* FROM customers AS T1 CROSS JOIN orders AS T2",
    "SELECT COUNT(DISTINCT T1.city), MIN(T1.id), MAX(T1.id) FROM customers AS T1",
    "SELECT DISTINCT T1.city FROM customers AS T1 WHERE NOT T1.id NOT IN (1, 2, 3)",
    "SELECT -T1.amount, T1.amount % 2, T1.amount / 2.5e1 FROM orders AS T1"
    " WHERE T1.amount <> -1 AND T1.amount != 3 OR T1.amount <= 0.5",
    "SELECT STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.created_at) FROM orders AS T1"
    " WHERE T1.Date < CURRENT_DATE AND T1.status IS NULL",
    "SELECT (SELECT COUNT(*) FROM orders) * 1.0 / (SELECT COUNT(*) FROM customers)",
    "SELECT name FROM customers WHERE name = 'O''Neil' AND city NOT BETWEEN 'A' AND 'M'",
    # `--` inside a string literal is data, not a comment
    "SELECT name FROM customers WHERE name = 'a--b /* c */'",
    "SELECT T1.name FROM customers AS T1 ORDER BY T1.name ASC, T1.id DESC LIMIT 1000",
]

INVALID = [
    "DROP TABLE customers",
    "DELETE FROM orders",
    "INSERT INTO orders (id) VALUES (9)",
    "UPDATE orders SET amount = 0",
    "CREATE TABLE x (a)",
    "PRAGMA table_info(customers)",
    "ATTACH DATABASE 'x.db' AS x",
    "SELECT name FROM sqlite_master",
    "SELECT load_extension('evil')",
    "SELECT 1; DROP TABLE customers",
    "SELECT 1;",
    "SELECT name FROM customers -- trailing comment",
    "SELECT name /* comment */ FROM customers",
    "SELECT password FROM customers",
    "SELECT name FROM users",
    "SELECT T10.name FROM customers AS T10",
    "SELECT a.name FROM customers AS a",
    "SELECT customers.name FROM customers",
    "SELECT name AS customer_name FROM customers",
    "WITH big AS (SELECT 1) SELECT * FROM big",
    "WITH RECURSIVE cte1 AS (SELECT 1) SELECT * FROM cte1",
    "SELECT name FROM customers WHERE name = 'O\\'Neil'",
    "SELECT name FROM customers WHERE name = 'unterminated",
    "SELECT name FROM customers WHERE name = 'a;b'",
    "select name from customers",
    "SELECT name  FROM customers",
    "SELECT\nname FROM customers",
    "SELECT name FROM customers ",
    "SELECT GROUP_CONCAT(name) FROM customers",
    "SELECT RANK() OVER (ORDER BY amount) FROM orders",
    "SELECT char(65)",
    "SELECT n\u0430me FROM customers",
    "SELECT name FROM customers LIMIT 1001",
    "SELECT name FROM customers LIMIT 0",
    "SELECT name FROM customers ORDER BY name NULLS LAST",
    "SELECT name FROM customers WHERE id IN customers",
    "SELECT CAST(id AS BLOB) FROM customers",
    "SELECT name FROM customers AS T1 NATURAL JOIN orders AS T2",
    "ABSTAIN: not allowed without the abstain option",
]
