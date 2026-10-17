from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SHOP_DDL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    "Full Name" TEXT NOT NULL,
    city TEXT,
    photo BLOB,
    notes TEXT
);
CREATE TABLE "order" (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    amount REAL,
    status TEXT,
    code
);
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    name TEXT,
    owner_customer_id INTEGER REFERENCES customers(id)
);
CREATE TABLE tags (tag TEXT PRIMARY KEY, label TEXT) WITHOUT ROWID;
CREATE TABLE empty (x INTEGER);
"""

LONG = "x" * 200


def _populate(conn: sqlite3.Connection) -> None:
    cities = ["Paris"] * 4 + ["Berlin"] * 3 + ["Oslo"] + [None] * 2
    notes = [LONG, LONG + "y", "", "   "] + [None] * 6
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            (i + 1, f"Customer {i + 1}", city, b"\x00\xff", note)
            for i, (city, note) in enumerate(zip(cities, notes, strict=True))
        ],
    )
    conn.executemany(
        'INSERT INTO "order" VALUES (?, ?, ?, ?, ?)',
        [
            (1, 1, 10.0, "b", 1),
            (2, 1, 10.0, "a", "1"),
            (3, 2, 5.5, "c", 1),
            (4, 3, 7, None, None),
            (5, 3, 7, "O'Brien", None),
            (6, None, None, None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO accounts VALUES (?, ?, ?, ?)",
        [(1, 1, "Acme Secret One", 1), (2, 2, "Globex Secret Two", 2)],
    )
    conn.executemany("INSERT INTO tags VALUES (?, ?)", [(f"t{i}", "label") for i in range(50)])


@pytest.fixture
def shop_db(tmp_path: Path) -> Path:
    path = tmp_path / "shop.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SHOP_DDL)
    _populate(conn)
    conn.commit()
    conn.close()
    return path
