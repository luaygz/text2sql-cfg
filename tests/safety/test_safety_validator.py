"""Layer 2 unit tests: one accepted and at least one rejected example per rule and branch."""

from __future__ import annotations

import pytest
from safety_fixture import POLICY
from sqlglot import exp

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.safety import ALLOWED_FUNCTIONS, Rule, ValidationConfig, ValidationError, validate_sql

BENCH = ValidationConfig(QueryMode.BENCHMARK)
PROD = ValidationConfig(QueryMode.PRODUCTION, max_rows=100)
TENANT = ValidationConfig(QueryMode.TENANT, max_rows=100, scope=POLICY)


def rejection(sql: str, schema: DatabaseSchema, config: ValidationConfig) -> ValidationError:
    with pytest.raises(ValidationError) as info:
        validate_sql(sql, schema, config)
    return info.value


ACCEPTED_IN_TENANT_MODE = [
    "SELECT name FROM accounts LIMIT 5",
    "SELECT T1.name, T2.title FROM accounts AS T1 JOIN deals AS T2 ON T2.account_id = T1.id "
    "LIMIT 5",
    "SELECT T1.name, T2.title FROM accounts AS T1 LEFT OUTER JOIN deals AS T2 "
    "ON T2.account_id = T1.id WHERE T2.id IS NULL LIMIT 5",
    "SELECT T1.name FROM accounts AS T1 INNER JOIN plans AS T2 ON T2.id = T1.plan_id "
    "CROSS JOIN users AS T3 LIMIT 5",
    "SELECT T1.name, T2.name FROM accounts AS T1, plans AS T2 LIMIT 5",
    "SELECT name FROM accounts WHERE id IN (SELECT account_id FROM deals WHERE amount > 100) "
    "LIMIT 5",
    "SELECT T1.name FROM accounts AS T1 WHERE NOT EXISTS "
    "(SELECT 1 FROM deals AS T2 WHERE T2.account_id = T1.id) LIMIT 5",
    "SELECT T1.name FROM accounts AS T1 WHERE EXISTS (SELECT 1 FROM deals AS T2 WHERE "
    "T2.account_id = T1.id AND T2.amount > (SELECT AVG(T3.amount) FROM deals AS T3 "
    "WHERE T3.owner_user_id = T1.owner_user_id)) LIMIT 5",
    "SELECT T1.name FROM accounts AS T1 WHERE T1.id IN (SELECT T2.account_id FROM deals AS T2 "
    "UNION SELECT T3.id FROM accounts AS T3 WHERE T3.name = T1.name) LIMIT 5",
    "SELECT (SELECT MAX(amount) FROM deals) AS c1 FROM plans LIMIT 1",
    "WITH cte1 AS (SELECT account_id, SUM(amount) AS c1 FROM deals GROUP BY account_id), "
    "cte2 AS (SELECT account_id FROM cte1 WHERE c1 > 100) "
    "SELECT T1.name, T2.c1 FROM accounts AS T1 JOIN cte1 AS T2 ON T2.account_id = T1.id "
    "WHERE T1.id IN (SELECT account_id FROM cte2) LIMIT 5",
    "WITH cte1(n, total) AS (SELECT name, plan_id FROM accounts) SELECT n, total FROM cte1 LIMIT 5",
    "SELECT name FROM accounts UNION ALL SELECT title FROM deals ORDER BY name LIMIT 5",
    "SELECT name AS c1 FROM accounts UNION SELECT title AS c2 FROM deals ORDER BY c2 LIMIT 5",
    "SELECT name FROM accounts INTERSECT SELECT title FROM deals EXCEPT SELECT name FROM plans "
    "LIMIT 5",
    "SELECT x.name FROM (SELECT name FROM accounts UNION SELECT title FROM deals) AS x LIMIT 5",
    "SELECT T2.c1 FROM (SELECT stage, COUNT(*) AS c1 FROM deals GROUP BY stage) AS T2 LIMIT 5",
    "SELECT stage, COUNT(*) AS c1, COUNT(DISTINCT account_id), SUM(amount), AVG(amount), "
    "MIN(amount), MAX(amount) FROM deals GROUP BY stage HAVING COUNT(*) > 1 "
    "ORDER BY c1 DESC LIMIT 5",
    "SELECT ROUND(AVG(amount), 2), ABS(-amount), CAST(amount AS REAL) / 3, "
    "COALESCE(country, 'none'), NULLIF(country, 'US'), IIF(amount > 100, 'big', 'small') "
    "FROM deals JOIN accounts ON accounts.id = deals.account_id LIMIT 5",
    "SELECT LENGTH(title), UPPER(title), LOWER(title), TRIM(title), SUBSTR(title, 1, 3), "
    "INSTR(title, 'deal'), REPLACE(title, 'deal', 'opportunity') FROM deals LIMIT 5",
    "SELECT STRFTIME('%Y', created_at), DATE(created_at, '+1 month'), "
    "JULIANDAY('now') - JULIANDAY(created_at), CURRENT_DATE, CURRENT_TIMESTAMP, CURRENT_TIME "
    "FROM deals LIMIT 5",
    "SELECT CASE WHEN amount > 100 THEN 'big' WHEN amount > 10 THEN 'mid' ELSE 'small' END, "
    "CASE stage WHEN 'won' THEN 1 ELSE 0 END FROM deals LIMIT 5",
    "SELECT amount * 2 AS c1 FROM deals WHERE c1 > 10 GROUP BY c1 HAVING c1 < 1000 "
    "ORDER BY c1 LIMIT 5",
    "SELECT DISTINCT name FROM accounts WHERE name LIKE 'A%' AND NOT plan_id BETWEEN 2 AND 3 "
    "AND country IN ('US', 'DE') AND country IS NOT NULL OR name || 'x' <> 'y' LIMIT 5",
    "SELECT title FROM deals WHERE stage = 'won' AND TRUE ORDER BY amount DESC, title "
    "LIMIT 5 OFFSET 10",
    "SELECT title FROM deals LIMIT 10, 5",
    'SELECT "accounts"."name" FROM "accounts" '
    'JOIN `plans` ON `plans`.id = "accounts".plan_id '
    "JOIN [deals] ON [deals].account_id = accounts.id LIMIT 5",
    "SELECT title FROM 'deals' LIMIT 5",
    "SELECT name FROM accounts WHERE name = 'Ünïcødé — ok in literals' LIMIT 5",
    "SELECT name FROM accounts WHERE name = 'a--b /* c */; it''s' LIMIT 5",
    "SELECT owner_user_id FROM deals LIMIT 5",
    "SELECT COUNT(*) FROM deals LIMIT 1",
    "SELECT 1 LIMIT 1",
    "SELECT name FROM accounts LIMIT 100",
]


@pytest.mark.parametrize("sql", ACCEPTED_IN_TENANT_MODE)
def test_accepts_grammar_shaped_queries(sql: str, visible_schema: DatabaseSchema) -> None:
    for config in (BENCH, PROD, TENANT):
        assert isinstance(validate_sql(sql, visible_schema, config), exp.Query)


def test_returns_the_parsed_statement(visible_schema: DatabaseSchema) -> None:
    tree = validate_sql("SELECT name FROM accounts LIMIT 5", visible_schema, TENANT)
    assert isinstance(tree, exp.Select)
    assert tree.sql(dialect="sqlite") == "SELECT name FROM accounts LIMIT 5"


T = TENANT
B = BENCH
# fmt: off
REJECTED = [
    # parsing and statement shape
    ("SELECT FROM WHERE", T, Rule.PARSE_ERROR),
    ("SELECT name FROM accounts WHERE id = ?1 LIMIT 5", T, Rule.PARSE_ERROR),
    ("SELECT 1 /* /* */ , 2 */", T, Rule.PARSE_ERROR),
    ("", T, Rule.PARSE_ERROR),
    ("   ", T, Rule.PARSE_ERROR),
    ("SELECT name FROM accounts LIMIT 5 -- trailing", T, Rule.COMMENT),
    ("/* hint */ SELECT name FROM accounts LIMIT 5", T, Rule.COMMENT),
    ("SELECT name /**/ FROM accounts LIMIT 5", T, Rule.COMMENT),
    ("SELECT name FROM accounts LIMIT 5; DROP TABLE accounts", T, Rule.MULTIPLE_STATEMENTS),
    ("SELECT name FROM accounts LIMIT 5;", T, Rule.MULTIPLE_STATEMENTS),
    ("SELECT n\u0430me FROM accounts LIMIT 5", T, Rule.NON_ASCII),  # Cyrillic a
    ("SELECT\u00a0name FROM accounts LIMIT 5", T, Rule.NON_ASCII),  # no-break space
    ("SELECT na\u200bme FROM accounts LIMIT 5", T, Rule.NON_ASCII),  # zero-width space
    ("INSERT INTO plans VALUES (9, 'x', 1)", T, Rule.NOT_SELECT),
    ("REPLACE INTO plans VALUES (9, 'x', 1)", T, Rule.NOT_SELECT),
    ("UPDATE plans SET name = 'x'", T, Rule.NOT_SELECT),
    ("DELETE FROM plans", T, Rule.NOT_SELECT),
    ("DROP TABLE plans", T, Rule.NOT_SELECT),
    ("CREATE TABLE x (a INT)", T, Rule.NOT_SELECT),
    ("CREATE TEMP VIEW deals AS SELECT 1", T, Rule.NOT_SELECT),
    ("ALTER TABLE plans ADD COLUMN x INT", T, Rule.NOT_SELECT),
    ("PRAGMA table_info(accounts)", T, Rule.NOT_SELECT),
    ("ATTACH 'other.db' AS other", T, Rule.NOT_SELECT),
    ("DETACH other", T, Rule.NOT_SELECT),
    ("BEGIN", T, Rule.NOT_SELECT),
    ("COMMIT", T, Rule.NOT_SELECT),
    ("VACUUM", T, Rule.NOT_SELECT),
    ("ANALYZE", T, Rule.NOT_SELECT),
    ("EXPLAIN SELECT name FROM accounts", T, Rule.NOT_SELECT),
    ("WITH c AS (SELECT 1) INSERT INTO plans SELECT * FROM c", T, Rule.NOT_SELECT),
    ("VALUES (1)", T, Rule.NOT_SELECT),
    ("(SELECT name FROM accounts LIMIT 5)", T, Rule.NOT_SELECT),
    # constructs outside the allowlist
    ("SELECT SUM(amount) OVER () FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts WINDOW w AS (PARTITION BY name) LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts RIGHT JOIN deals ON deals.account_id = accounts.id LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts FULL OUTER JOIN plans ON 1 LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts NATURAL JOIN plans LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals JOIN accounts USING (id) LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals OUTER JOIN accounts ON 1 LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals WHERE account_id IN accounts LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals WHERE title LIKE 'a!%' ESCAPE '!' LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals WHERE title GLOB 'a*' LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals WHERE stage IS NOT DISTINCT FROM 'won' LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title FROM deals WHERE (id, amount) IN (SELECT 1, 2) LIMIT 5", T,
     Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT amount & 1 FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT x'00' FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT title INTO copy FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM (accounts) LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts INDEXED BY ix LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT name FROM accounts NOT INDEXED LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT a.x FROM accounts AS a(x) LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT d.x FROM (SELECT name FROM accounts) AS d(x) LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT SUM(*) FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT COUNT(deals.*) FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT CAST(title AS VARCHAR(10)) FROM deals LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    ("SELECT v.column1 FROM (VALUES (1)) AS v LIMIT 5", T, Rule.FORBIDDEN_CONSTRUCT),
    # bind parameters: the model must never supply a value the server binds
    ("SELECT title FROM deals WHERE owner_user_id = :tenant_id LIMIT 5", T, Rule.PLACEHOLDER),
    ("SELECT :user_id FROM deals LIMIT 5", T, Rule.PLACEHOLDER),
    ("SELECT title FROM deals WHERE id = ? LIMIT 5", T, Rule.PLACEHOLDER),
    ("SELECT title FROM deals WHERE id = @p LIMIT 5", T, Rule.PLACEHOLDER),
    ("SELECT title FROM deals WHERE id = $tenant_id LIMIT 5", T, Rule.PLACEHOLDER),
    # functions
    ("SELECT IFNULL(country, 'x') FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT SUBSTRING(name, 1, 2) FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT LTRIM(name) FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT load_extension('evil') FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT RANDOM() FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT HEX(name) FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT printf('%s', name) FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT GROUP_CONCAT(name) FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT sqlite_version() FROM accounts LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT DATETIME(created_at) FROM deals LIMIT 5", T, Rule.FUNCTION_NOT_ALLOWED),
    ("SELECT name FROM accounts ORDER BY name COLLATE NOCASE LIMIT 5", T,
     Rule.FUNCTION_NOT_ALLOWED),
    # tables
    ("SELECT name FROM main.accounts LIMIT 5", T, Rule.SCHEMA_QUALIFIER),
    ("SELECT name FROM temp.accounts LIMIT 5", T, Rule.SCHEMA_QUALIFIER),
    ("SELECT main.accounts.name FROM accounts LIMIT 5", T, Rule.SCHEMA_QUALIFIER),
    ("SELECT name FROM sqlite_master LIMIT 5", T, Rule.SYSTEM_TABLE),
    ("SELECT name FROM SQLITE_SCHEMA LIMIT 5", T, Rule.SYSTEM_TABLE),
    ("SELECT sql FROM sqlite_temp_master LIMIT 5", T, Rule.SYSTEM_TABLE),
    ("SELECT name FROM invoices LIMIT 5", T, Rule.UNKNOWN_TABLE),
    ("SELECT value FROM json_each('[1]') LIMIT 5", T, Rule.UNKNOWN_TABLE),
    ("SELECT name FROM \"\u0430ccounts\" LIMIT 5", T, Rule.UNKNOWN_TABLE),
    ("WITH cte1 AS (SELECT name FROM cte2), cte2 AS (SELECT name FROM accounts) "
     "SELECT name FROM cte1 LIMIT 5", T, Rule.UNKNOWN_TABLE),
    # CTEs
    ("WITH RECURSIVE cte1(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM cte1) "
     "SELECT n FROM cte1 LIMIT 5", T, Rule.INVALID_CTE),
    ("WITH cte1 AS (SELECT 1 AS n), cte1 AS (SELECT 2 AS n) SELECT n FROM cte1 LIMIT 5", T,
     Rule.INVALID_CTE),
    ("WITH accounts AS (SELECT title AS name FROM deals) SELECT name FROM accounts LIMIT 5", T,
     Rule.INVALID_CTE),
    ("WITH sqlite_x AS (SELECT 1 AS n) SELECT n FROM sqlite_x LIMIT 5", T, Rule.INVALID_CTE),
    ("SELECT T1.name FROM accounts AS T1 JOIN deals AS T1 ON 1 LIMIT 5", T, Rule.SCOPE_ERROR),
    # columns
    ("SELECT nickname FROM accounts LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT T9.name FROM accounts AS T1 LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT T1.title FROM accounts AS T1 LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT rowid FROM accounts LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT name FROM accounts WHERE name = \"Acme\" LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT d.name FROM (SELECT title FROM deals) AS d LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT x.title FROM (SELECT name FROM accounts UNION SELECT title FROM deals) AS x "
     "LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("WITH cte1(n) AS (SELECT name FROM accounts) SELECT name FROM cte1 LIMIT 5", T,
     Rule.UNKNOWN_COLUMN),
    ("SELECT name FROM accounts UNION SELECT title FROM deals ORDER BY accounts.name LIMIT 5", T,
     Rule.UNKNOWN_COLUMN),
    ("SELECT name AS c1 FROM accounts WHERE EXISTS (SELECT 1 FROM deals WHERE title = c1) "
     "LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT T1.name FROM accounts AS T1 JOIN (SELECT title FROM deals WHERE "
     "account_id = T1.id) AS T2 ON 1 LIMIT 5", T, Rule.UNKNOWN_COLUMN),
    ("SELECT x.* FROM accounts LIMIT 5", B, Rule.UNKNOWN_COLUMN),
    ("SELECT id FROM accounts JOIN deals ON deals.account_id = accounts.id LIMIT 5", T,
     Rule.AMBIGUOUS_COLUMN),
    # scope and hidden columns, wherever they appear
    ("SELECT tenant_id FROM deals LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT T1.tenant_id FROM deals AS T1 LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT title FROM deals WHERE tenant_id = 2 LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT title FROM deals WHERE tenant_id = 1 OR 1 = 1 LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT stage FROM deals GROUP BY tenant_id LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT stage FROM deals GROUP BY stage HAVING SUM(tenant_id) > 0 LIMIT 5", T,
     Rule.HIDDEN_COLUMN),
    ("SELECT title FROM deals ORDER BY tenant_id LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT T1.title FROM deals AS T1 JOIN accounts AS T2 ON T2.tenant_id = T1.tenant_id "
     "LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT name FROM plans AS p WHERE EXISTS (SELECT 1 FROM accounts AS a "
     "WHERE a.tenant_id = p.id) LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT p.name FROM plans AS p JOIN accounts AS a ON a.plan_id = p.id "
     "WHERE p.id IN (SELECT tenant_id FROM users) LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("WITH cte1 AS (SELECT tenant_id AS t FROM deals) SELECT t FROM cte1 LIMIT 5", T,
     Rule.HIDDEN_COLUMN),
    ("SELECT name FROM accounts UNION SELECT tenant_id FROM deals LIMIT 5", T,
     Rule.HIDDEN_COLUMN),
    ("SELECT password_hash FROM users LIMIT 5", T, Rule.HIDDEN_COLUMN),
    ("SELECT name FROM users WHERE LENGTH(password_hash) > 3 LIMIT 5", T, Rule.HIDDEN_COLUMN),
    # SELECT * in tenant mode
    ("SELECT * FROM deals LIMIT 5", T, Rule.STAR_IN_TENANT_MODE),
    ("SELECT T1.* FROM deals AS T1 LIMIT 5", T, Rule.STAR_IN_TENANT_MODE),
    ("SELECT x.title FROM (SELECT * FROM deals) AS x LIMIT 5", T, Rule.STAR_IN_TENANT_MODE),
    # LIMIT / OFFSET
    ("SELECT name FROM accounts LIMIT -1", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT (SELECT 5)", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT 5.5", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT '5'", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT 1e2", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT 0x10", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT 5 OFFSET -1", T, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT -1", B, Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts WHERE id IN (SELECT account_id FROM deals LIMIT -1)", B,
     Rule.INVALID_LIMIT),
    ("SELECT name FROM accounts LIMIT 101", T, Rule.LIMIT_TOO_LARGE),
    ("SELECT name FROM accounts LIMIT 2, 101", PROD, Rule.LIMIT_TOO_LARGE),
    ("SELECT name FROM accounts", T, Rule.MISSING_LIMIT),
    ("SELECT name FROM accounts", PROD, Rule.MISSING_LIMIT),
    ("SELECT name FROM accounts WHERE id IN (SELECT account_id FROM deals LIMIT 5)", T,
     Rule.MISSING_LIMIT),
]
# fmt: on


@pytest.mark.parametrize(("sql", "config", "rule"), REJECTED)
def test_rejects_with_stable_rule(
    sql: str, config: ValidationConfig, rule: Rule, visible_schema: DatabaseSchema
) -> None:
    assert rejection(sql, visible_schema, config).rule == rule


def test_every_rule_has_a_rejection_example() -> None:
    covered = {rule for _, _, rule in REJECTED} | {Rule.TOO_LONG}
    assert covered == set(Rule)


def test_error_carries_rule_and_detail(visible_schema: DatabaseSchema) -> None:
    error = rejection("SELECT tenant_id FROM deals LIMIT 5", visible_schema, TENANT)
    assert error.rule == "hidden_column"
    assert "tenant_id" in error.detail
    assert error.layer == "validator"
    assert str(error) == f"[hidden_column] {error.detail}"


def test_length_cap_is_checked_before_parsing(visible_schema: DatabaseSchema) -> None:
    config = ValidationConfig(QueryMode.TENANT, scope=POLICY, max_sql_chars=40)
    sql = "SELECT name FROM accounts LIMIT 5"
    assert validate_sql(sql, visible_schema, config)
    padded = sql.replace("SELECT", "SELECT" + " " * 10)
    assert rejection(padded, visible_schema, config).rule == Rule.TOO_LONG


def test_deep_nesting_is_a_parse_error_not_a_crash(visible_schema: DatabaseSchema) -> None:
    sql = "SELECT " + "(" * 3000 + "1" + ")" * 3000 + " LIMIT 1"
    config = ValidationConfig(QueryMode.TENANT, scope=POLICY, max_sql_chars=10_000)
    assert rejection(sql, visible_schema, config).rule == Rule.PARSE_ERROR


def test_limit_cap_only_applies_outside_benchmark_mode(visible_schema: DatabaseSchema) -> None:
    sql = "SELECT name FROM accounts LIMIT 5000 OFFSET 5000"
    assert validate_sql(sql, visible_schema, BENCH)
    assert rejection(sql, visible_schema, PROD).rule == Rule.LIMIT_TOO_LARGE
    assert validate_sql("SELECT name FROM accounts", visible_schema, BENCH)


def test_offset_is_not_capped(visible_schema: DatabaseSchema) -> None:
    assert validate_sql("SELECT name FROM accounts LIMIT 5 OFFSET 5000", visible_schema, PROD)


def test_star_is_allowed_outside_tenant_mode(visible_schema: DatabaseSchema) -> None:
    for sql in (
        "SELECT * FROM deals LIMIT 5",
        "SELECT T1.*, T2.name FROM deals AS T1 JOIN accounts AS T2 ON T2.id = T1.account_id "
        "LIMIT 5",
        "SELECT d.title FROM (SELECT * FROM deals) AS d LIMIT 5",
        "SELECT d.title FROM (SELECT T1.* FROM deals AS T1) AS d LIMIT 5",
        "SELECT x.title FROM (SELECT * FROM plans JOIN deals ON 1) AS x LIMIT 5",
    ):
        assert validate_sql(sql, visible_schema, PROD)


def test_hidden_columns_need_the_policy_for_their_rule(
    full_schema: DatabaseSchema, visible_schema: DatabaseSchema
) -> None:
    sql = "SELECT tenant_id FROM deals LIMIT 5"
    # The visible schema alone already hides the column; the policy names the reason.
    assert rejection(sql, visible_schema, PROD).rule == Rule.UNKNOWN_COLUMN
    # Given the full schema, the policy strips scope and hidden columns itself.
    assert rejection(sql, full_schema, TENANT).rule == Rule.HIDDEN_COLUMN
    assert validate_sql(sql, full_schema, PROD)


def test_cte_may_not_shadow_a_scoped_table_missing_from_the_linked_schema(
    visible_schema: DatabaseSchema,
) -> None:
    linked = visible_schema.subset({"accounts": None, "plans": None})
    sql = "WITH deals AS (SELECT name FROM accounts) SELECT name FROM deals LIMIT 5"
    assert rejection(sql, linked, TENANT).rule == Rule.INVALID_CTE
    assert validate_sql(sql, linked, PROD)


def test_function_allowlist_is_configurable(visible_schema: DatabaseSchema) -> None:
    no_iif = ValidationConfig(QueryMode.PRODUCTION, functions=ALLOWED_FUNCTIONS - {"IIF"})
    # CASE branches are represented as IF nodes internally; they are not IIF calls.
    case = "SELECT CASE WHEN amount > 1 THEN 1 ELSE 0 END FROM deals LIMIT 5"
    assert validate_sql(case, visible_schema, no_iif)
    for sql in (
        "SELECT IIF(amount > 1, 1, 0) FROM deals LIMIT 5",
        "SELECT CASE WHEN amount > 1 THEN 1 ELSE IIF(amount > 0, 2, 3) END FROM deals LIMIT 5",
    ):
        assert rejection(sql, visible_schema, no_iif).rule == Rule.FUNCTION_NOT_ALLOWED

    no_case = ValidationConfig(QueryMode.PRODUCTION, functions=ALLOWED_FUNCTIONS - {"CASE"})
    assert rejection(case, visible_schema, no_case).rule == Rule.FUNCTION_NOT_ALLOWED

    no_strftime = ValidationConfig(QueryMode.PRODUCTION, functions=ALLOWED_FUNCTIONS - {"STRFTIME"})
    strftime = "SELECT STRFTIME('%Y', created_at) FROM deals LIMIT 5"
    assert validate_sql(strftime, visible_schema, PROD)
    assert rejection(strftime, visible_schema, no_strftime).rule == Rule.FUNCTION_NOT_ALLOWED

    lowercase = ValidationConfig(QueryMode.PRODUCTION, functions=frozenset({"count"}))
    assert validate_sql("SELECT count(*) FROM deals LIMIT 5", visible_schema, lowercase)
