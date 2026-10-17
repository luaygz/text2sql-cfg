from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from text2sql.catalog.profile import (
    DEFAULT_PROFILE_OPTIONS,
    ProfileOptions,
    TableProfile,
    connect_readonly,
    profile_table,
)
from text2sql.catalog.schema import introspect_sqlite


def _profile(
    db: Path, table: str, options: ProfileOptions = DEFAULT_PROFILE_OPTIONS
) -> TableProfile:
    schema = introspect_sqlite(db)
    found = schema.table(table)
    assert found is not None
    with closing(connect_readonly(db)) as conn:
        return profile_table(conn, found, options)


def test_counts_null_rate_and_most_frequent_values(shop_db: Path) -> None:
    profile = _profile(shop_db, "customers")
    assert (profile.row_count, profile.profiled_rows) == (10, 10)
    city = profile.columns["city"]
    assert city.distinct_count == 3
    assert city.null_rate == 0.2
    assert city.samples == ("Paris", "Berlin", "Oslo")  # most frequent first
    assert profile.columns["Full Name"].distinct_count == 10


def test_blobs_blanks_and_long_text_are_kept_out_of_samples(shop_db: Path) -> None:
    profile = _profile(shop_db, "customers", ProfileOptions(max_value_chars=20))
    assert profile.columns["photo"].samples == ()
    notes = profile.columns["notes"]
    # Two long values that share a prefix collapse into one truncated sample; '' and '   ' are
    # counted as distinct values but are not shown.
    assert notes.samples == ("x" * 19 + "…",)
    assert notes.distinct_count == 4
    assert notes.null_rate == 0.6


def test_ties_break_by_value_and_storage_types_survive(shop_db: Path) -> None:
    profile = _profile(shop_db, "order")
    assert profile.columns["status"].samples == ("O'Brien", "a", "b", "c")
    code = profile.columns["code"].samples  # typeless column holding 1 and '1'
    assert code == (1, "1")
    assert [type(v) for v in code] == [int, str]
    assert profile.columns["amount"].samples == (7.0, 10.0, 5.5)


def test_large_tables_are_sampled_deterministically(tmp_path: Path) -> None:
    db = tmp_path / "big.sqlite"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, kind TEXT)")
        conn.executemany(
            "INSERT INTO events VALUES (?, ?)", [(i, f"k{i % 3}") for i in range(1, 1001)]
        )
        conn.commit()
    options = ProfileOptions(max_rows=100)
    first = _profile(db, "events", options)
    assert first.row_count == 1000
    assert first.profiled_rows == 100
    assert first.columns["id"].distinct_count == 100  # a lower bound when sampled
    assert first == _profile(db, "events", options)


def test_without_rowid_table_is_scanned_whole(shop_db: Path) -> None:
    profile = _profile(shop_db, "tags", ProfileOptions(max_rows=10))
    assert profile.profiled_rows == profile.row_count == 50


def test_empty_table_has_no_null_rate(shop_db: Path) -> None:
    profile = _profile(shop_db, "empty")
    assert profile.row_count == 0
    assert profile.columns["x"].null_rate is None
    assert profile.columns["x"].samples == ()


def test_connection_is_read_only_and_leaves_the_file_untouched(shop_db: Path) -> None:
    before = hashlib.sha256(shop_db.read_bytes()).hexdigest()
    with closing(connect_readonly(shop_db)) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM customers")
        _profile(shop_db, "customers", ProfileOptions(max_rows=2))
    assert hashlib.sha256(shop_db.read_bytes()).hexdigest() == before


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(FileNotFoundError):
        connect_readonly(missing)
    assert not missing.exists()
