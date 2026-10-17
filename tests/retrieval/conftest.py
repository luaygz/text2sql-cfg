from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from text2sql.catalog import Catalog, build_catalog
from text2sql.config import get_settings
from text2sql.safety.policy import ScopePolicy

GEO_DDL = """
CREATE TABLE country (country_id INTEGER PRIMARY KEY, name TEXT, code TEXT);
CREATE TABLE city (
    city_id INTEGER PRIMARY KEY,
    country_id INTEGER REFERENCES country(country_id),
    name TEXT,
    homepage_url TEXT,
    founded TEXT,
    population TEXT,
    candidate TEXT
);
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    name TEXT,
    stage TEXT
);
"""

CITIES = ["New York", "Newark", "New Orleans", "Berlin", "Paris", "Munich", "Hamburg", "york"]

TENANT_POLICY = ScopePolicy(tenant_tables=frozenset({"accounts"}))


def _populate(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO country VALUES (?, ?, ?)",
        [(1, "United States", "US"), (2, "Germany", "DE"), (3, "France", "FR")],
    )
    rows = [
        (i + 1, 1 if i < 3 else 2, name, f"https://{i}.example", f"18{i:02d}-01-01", str(i), "Lee")
        for i, name in enumerate(CITIES)
    ]
    conn.executemany("INSERT INTO city VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.executemany(
        "INSERT INTO accounts VALUES (?, ?, ?, ?)",
        [
            (1, 1, "Acme Secret One", "won"),
            (2, 1, "Shared Co", "lost"),
            (3, 1, "Initech", "pending"),
            (4, 2, "Globex Secret Two", "won"),
            (5, 2, "Shared Co", "lost"),
        ],
    )


@pytest.fixture
def geo_db(tmp_path: Path) -> Path:
    path = tmp_path / "geo.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(GEO_DDL)
    _populate(conn)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def geo_catalog(geo_db: Path) -> Catalog:
    return build_catalog(geo_db, "geo")


@pytest.fixture
def tenant_catalog(geo_db: Path) -> Catalog:
    return build_catalog(geo_db, "geo", policy=TENANT_POLICY)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point Settings.data_dir (and so data/indexes) at a temporary directory."""
    directory = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(directory))
    get_settings.cache_clear()
    yield directory
    get_settings.cache_clear()
