"""Write the synthetic SaaS CRM database.

    uv run --frozen python -m text2sql.data.saas.generate --out data/saas/crm.sqlite

The file is byte-for-byte reproducible for a given SQLite library version: the same seed, the
same insert order, a fixed page size and a final VACUUM. SQLite records its own version in the
file header, so hashes from different SQLite builds differ even when the content is identical.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

from text2sql.data.saas.dictionary import DEFAULT_DB_PATH, TABLES, TableSpec, create_table_sql
from text2sql.data.saas.profile import SAAS_SEED
from text2sql.data.saas.reference import COUNTRIES, CURRENCIES, INDUSTRIES, PLANS, RefRow
from text2sql.data.saas.synth import build_records
from text2sql.data.saas.world import Cell, Record

SCHEMA_VERSION = 1
"""Stored as PRAGMA user_version; bump when the dictionary or generator changes the output."""

PAGE_SIZE = 4096

_REFERENCE_ROWS: dict[str, tuple[RefRow, ...]] = {
    "currencies": CURRENCIES,
    "countries": COUNTRIES,
    "industries": INDUSTRIES,
    "plans": tuple(p.as_row() for p in PLANS),
}


def generate_database(out: Path = DEFAULT_DB_PATH) -> str:
    """Build the database at `out`, replacing any existing file; return its SHA-256."""
    records = build_records(SAAS_SEED)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        _write(conn, records)
    finally:
        conn.close()
    tmp.replace(out)
    return file_sha256(out)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        return {
            t.name: int(conn.execute(f"SELECT COUNT(*) FROM {t.name}").fetchone()[0])
            for t in TABLES
        }
    finally:
        conn.close()


def _write(conn: sqlite3.Connection, records: dict[str, list[Record]]) -> None:
    conn.execute(f"PRAGMA page_size = {PAGE_SIZE}")
    for spec in TABLES:
        conn.execute(create_table_sql(spec))
        scope_columns = {"tenant": "tenant_id", "owner": "tenant_id, owner_user_id"}
        if spec.scope in scope_columns and spec.name != "tenants":
            conn.execute(
                f"CREATE INDEX idx_{spec.name}_scope ON {spec.name} ({scope_columns[spec.scope]})"
            )
    for spec in TABLES:
        placeholders = ", ".join("?" for _ in spec.columns)
        sql = f"INSERT INTO {spec.name} VALUES ({placeholders})"
        if spec.scope == "global":
            conn.executemany(sql, _REFERENCE_ROWS[spec.name])
        else:
            conn.executemany(sql, [_row(spec, r) for r in records[spec.name]])
    conn.commit()
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"generated data breaks foreign keys, e.g. {violations[:3]}")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.execute("VACUUM")


def _row(spec: TableSpec, record: Record) -> tuple[str | int | float | None, ...]:
    names = [c.name for c in spec.columns[1:]]  # the first column is the integer primary key
    if record.values.keys() != set(names):
        raise ValueError(f"{spec.name} row does not match the dictionary: {sorted(record.values)}")
    return (record.id, *(_cell(record.values[n]) for n in names))


def _cell(value: Cell) -> str | int | float | None:
    return value.id if isinstance(value, Record) else value


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic SaaS CRM database.")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"output path (default: {DEFAULT_DB_PATH})",
    )
    out: Path = parser.parse_args(argv).out
    started = time.perf_counter()
    digest = generate_database(out)
    elapsed = time.perf_counter() - started
    size_mb = out.stat().st_size / 1e6
    print(f"wrote {out} ({size_mb:.1f} MB) in {elapsed:.1f}s, SQLite {sqlite3.sqlite_version}")
    print(f"sha256 {digest}")
    for table, count in row_counts(out).items():
        print(f"  {table:<20}{count:>7}")


if __name__ == "__main__":
    main()
