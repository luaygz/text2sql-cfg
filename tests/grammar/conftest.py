from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.config import QueryMode
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar

# Identifiers chosen to exercise quoting: a keyword column (`order`), names with spaces and
# parentheses, a mixed-case `Date`, and a table name with a space.
SHOP_DDL = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT, "order" INTEGER,
                        "Signup Date" TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
                     amount REAL, status TEXT, created_at TEXT, Date TEXT);
CREATE TABLE "order items" (order_id INTEGER REFERENCES orders(id), product TEXT,
                            "qty (units)" INTEGER);
INSERT INTO customers VALUES (1, 'Ann', 'Paris', 1, '2020-01-05'), (2, 'Bob', NULL, 2, NULL),
                             (3, 'O''Neil', 'Oslo', 3, '2021-07-01');
INSERT INTO orders VALUES (1, 1, 120.5, 'paid', '2020-02-01', '2020-02-01'),
                          (2, 1, 30, 'refunded', '2020-03-01', NULL),
                          (3, 3, 99.9, 'paid', '2021-08-15', '2021-08-15'),
                          (4, 2, 15, NULL, '2022-01-01', NULL);
INSERT INTO "order items" VALUES (1, 'pen', 3), (1, 'ink', 1), (3, 'pad', 2), (4, 'pen', 1);
"""


@pytest.fixture(scope="session")
def shop_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("grammar") / "shop.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SHOP_DDL)
    conn.commit()
    conn.close()
    return path


@pytest.fixture(scope="session")
def shop_schema(shop_db: Path) -> DatabaseSchema:
    return introspect_sqlite(shop_db, "shop")


@pytest.fixture(scope="session")
def benchmark_grammar(shop_schema: DatabaseSchema) -> SqlGrammar:
    return build_grammar(shop_schema)


@pytest.fixture(scope="session")
def production_grammar(shop_schema: DatabaseSchema) -> SqlGrammar:
    return build_grammar(shop_schema, GrammarOptions(mode=QueryMode.PRODUCTION, max_rows=100))


@pytest.fixture(scope="session")
def tenant_grammar(shop_schema: DatabaseSchema) -> SqlGrammar:
    return build_grammar(
        shop_schema, GrammarOptions(mode=QueryMode.TENANT, max_rows=100, allow_abstain=True)
    )
