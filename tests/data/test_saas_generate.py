"""The generated SaaS CRM database: reproducibility, integrity, canaries, injections, dirty data."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from text2sql.data.saas import (
    CANARY_COLUMNS,
    TABLES,
    PlantedInjection,
    canary_values,
    planted_injections,
)
from text2sql.data.saas.dictionary import TABLE_SPECS
from text2sql.data.saas.generate import file_sha256, generate_database

TENANT_TABLES = [t for t in TABLES if t.scope != "global"]


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("saas") / "crm.sqlite"
    generate_database(path)
    return path


@pytest.fixture(scope="module")
def conn(db: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    yield connection
    connection.close()


def scalar(conn: sqlite3.Connection, sql: str, *params: object) -> object:
    return conn.execute(sql, params).fetchone()[0]


def test_generation_is_byte_identical_in_a_fresh_process_with_another_hash_seed(
    db: Path, tmp_path: Path
) -> None:
    out = tmp_path / "again.sqlite"
    out.write_bytes(b"a stale file that the generator must replace")
    env = {**os.environ, "PYTHONHASHSEED": "12345"}
    subprocess.run(
        [sys.executable, "-m", "text2sql.data.saas.generate", "--out", str(out)],
        check=True,
        env=env,
        capture_output=True,
    )
    assert file_sha256(out) == file_sha256(db)
    assert not out.with_name(out.name + ".tmp").exists()


def test_database_stays_small(db: Path) -> None:
    assert db.stat().st_size < 10_000_000


def test_foreign_keys_hold_and_never_cross_tenants(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    for spec in TENANT_TABLES:
        for col in spec.columns:
            if col.references is None or col.name == "tenant_id":
                continue
            ref_table, ref_col = col.references
            if TABLE_SPECS[ref_table].scope == "global":
                continue
            joined = f"{spec.name} a JOIN {ref_table} b ON a.{col.name} = b.{ref_col}"
            assert scalar(conn, f"SELECT COUNT(*) FROM {joined}"), f"{spec.name}.{col.name} empty"
            crossing = scalar(
                conn, f"SELECT COUNT(*) FROM {joined} WHERE a.tenant_id != b.tenant_id"
            )
            assert crossing == 0, f"{spec.name}.{col.name} points into another tenant"


def test_billing_rows_belong_to_the_account_manager(conn: sqlite3.Connection) -> None:
    for table in ("subscriptions", "invoices"):
        mismatched = scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} x JOIN accounts a "
            "USING (account_id) WHERE x.owner_user_id != a.owner_user_id",
        )
        assert mismatched == 0, table
    for table in ("invoice_line_items", "payments"):
        mismatched = scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} x JOIN invoices i "
            "USING (invoice_id) WHERE x.owner_user_id != i.owner_user_id",
        )
        assert mismatched == 0, table


def test_payment_amounts_are_cents_of_the_invoice_total(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT i.total_amount, SUM(p.amount) FROM invoices i JOIN payments p USING (invoice_id) "
        "WHERE i.status = 'paid' AND p.status = 'succeeded' GROUP BY i.invoice_id"
    ).fetchall()
    assert len(rows) > 1000
    assert all(cents == round(total * 100) for total, cents in rows)
    assert any(total != int(total) for total, _ in rows)  # cents are not just whole units


def test_won_deals_are_exactly_the_deal_backed_subscriptions(conn: sqlite3.Connection) -> None:
    won = {r[0] for r in conn.execute("SELECT deal_id FROM deals WHERE stage = 'closed_won'")}
    linked = {
        r[0] for r in conn.execute("SELECT deal_id FROM subscriptions WHERE deal_id IS NOT NULL")
    }
    assert won == linked


def test_each_tenant_owns_one_canary_per_canary_column(conn: sqlite3.Connection) -> None:
    tokens = canary_values()
    assert 5 <= len(tokens) <= 10
    assert len(set(tokens.values())) == len(tokens)
    assert sorted(tokens) == [r[0] for r in conn.execute("SELECT tenant_id FROM tenants")]
    for table, column in CANARY_COLUMNS:
        for tenant_id, token in tokens.items():
            rows = conn.execute(f"SELECT tenant_id FROM {table} WHERE {column} = ?", (token,))
            assert rows.fetchall() == [(tenant_id,)], f"{table}.{column} tenant {tenant_id}"


def test_no_row_mentions_another_tenants_canary(conn: sqlite3.Connection) -> None:
    tokens = canary_values()
    scanned = 0
    for spec in TENANT_TABLES:
        for col in spec.columns:
            if col.type != "TEXT":
                continue
            rows = conn.execute(
                f"SELECT tenant_id, {col.name} FROM {spec.name} WHERE {col.name} LIKE '%CANARY-T%'"
            ).fetchall()
            for tenant_id, value in rows:
                foreign = [t for tid, t in tokens.items() if tid != tenant_id]
                assert not any(t.lower() in value.lower() for t in foreign), (spec.name, value)
            scanned += len(rows)
    assert scanned >= len(tokens) * len(CANARY_COLUMNS)


def test_canary_rows_are_owned_only_by_the_inactive_canary_user(
    conn: sqlite3.Connection,
) -> None:
    for tenant_id, token in canary_values().items():
        user_id, active = conn.execute(
            "SELECT user_id, is_active FROM users WHERE tenant_id = ? AND full_name = ?",
            (tenant_id, token),
        ).fetchone()
        assert active == 0
        for table, column in CANARY_COLUMNS:
            if TABLE_SPECS[table].scope != "owner":
                continue
            owners = conn.execute(
                f"SELECT owner_user_id FROM {table} WHERE {column} = ?", (token,)
            ).fetchall()
            assert owners == [(user_id,)], table
            others = scalar(
                conn,
                f"SELECT COUNT(*) FROM {table} WHERE owner_user_id = ? AND {column} != ?",
                user_id,
                token,
            )
            assert others == 0, f"canary user owns a real row in {table}"


# (value, sort key) of the two newest rows per tenant: what the innocent question retrieves.
NEWEST: dict[tuple[str, str], str] = {
    ("accounts", "name"): "SELECT name, created_at FROM accounts WHERE tenant_id = ? "
    "ORDER BY created_at DESC LIMIT 2",
    ("tickets", "subject"): "SELECT subject, JULIANDAY(opened_at) FROM tickets WHERE tenant_id = ? "
    "ORDER BY JULIANDAY(opened_at) DESC LIMIT 2",
    ("contacts", "job_title"): "SELECT job_title, created_at FROM contacts WHERE tenant_id = ? "
    "ORDER BY created_at DESC LIMIT 2",
    ("activities", "notes"): "SELECT notes, occurred_at FROM activities WHERE tenant_id = ? "
    "ORDER BY occurred_at DESC LIMIT 2",
    ("invoice_line_items", "description"): (
        "SELECT (SELECT GROUP_CONCAT(description, ' | ') FROM invoice_line_items l "
        "WHERE l.invoice_id = i.invoice_id), issued_at FROM invoices i WHERE tenant_id = ? "
        "ORDER BY issued_at DESC LIMIT 2"
    ),
    ("deals", "name"): "SELECT name, created_at FROM deals WHERE tenant_id = ? "
    "ORDER BY created_at DESC LIMIT 2",
}


@pytest.mark.parametrize("injection", planted_injections(), ids=lambda i: i.table)
def test_injection_is_the_unique_answer_to_its_innocent_question(
    conn: sqlite3.Connection, injection: PlantedInjection
) -> None:
    table, column = injection.table, injection.column
    stored = conn.execute(f"SELECT tenant_id FROM {table} WHERE {column} = ?", (injection.text,))
    assert stored.fetchall() == [(injection.tenant_id,)]
    (newest, newest_key), (_, runner_up_key) = conn.execute(
        NEWEST[table, column], (injection.tenant_id,)
    ).fetchall()
    assert injection.text in newest
    assert newest_key > runner_up_key


def test_due_date_format_follows_the_legacy_cutover(conn: sqlite3.Connection) -> None:
    us_format = "due_date GLOB '[0-1][0-9]/[0-3][0-9]/[0-9][0-9][0-9][0-9]'"
    iso_format = "due_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'"
    malformed = scalar(
        conn, f"SELECT COUNT(*) FROM invoices WHERE NOT ({us_format} OR {iso_format})"
    )
    assert malformed == 0
    assert scalar(conn, f"SELECT COUNT(*) FROM invoices WHERE {us_format}")
    assert scalar(conn, f"SELECT COUNT(*) FROM invoices WHERE {iso_format}")
    wrong = scalar(
        conn, f"SELECT COUNT(*) FROM invoices WHERE (issued_at < '2024-07-01') != ({us_format})"
    )
    assert wrong == 0


def test_documented_due_date_normalisation_gives_the_real_due_date(
    conn: sqlite3.Connection,
) -> None:
    doc = TABLE_SPECS["invoices"].column("due_date")
    assert doc is not None and doc.value_description is not None
    match = re.search(r"(CASE .* END)\.", doc.value_description)
    assert match is not None
    iso = match.group(1)
    assert scalar(conn, "SELECT COUNT(*) FROM invoices WHERE DATE(due_date) IS NULL")
    rows = conn.execute(
        f"SELECT DATE({iso}) = {iso}, JULIANDAY({iso}) - JULIANDAY(i.issued_at), "
        "a.payment_terms_days FROM invoices i JOIN accounts a USING (account_id)"
    ).fetchall()
    assert all(valid and days == terms for valid, days, terms in rows)


def test_ticket_timestamp_format_depends_on_channel(conn: sqlite3.Connection) -> None:
    for column in ("opened_at", "resolved_at"):
        z_format = f"{column} LIKE '____-__-__T__:__:__Z'"
        wrong = scalar(
            conn,
            f"SELECT COUNT(*) FROM tickets WHERE {column} IS NOT NULL AND "
            f"(channel IN ('web', 'api')) != ({z_format})",
        )
        assert wrong == 0, column


def test_documented_ticket_time_functions_order_both_formats(conn: sqlite3.Connection) -> None:
    doc = TABLE_SPECS["tickets"].column("opened_at")
    assert doc is not None and doc.value_description is not None
    match = re.search(r"(REPLACE\(REPLACE\(opened_at, .*?\), .*?\))", doc.value_description)
    assert match is not None
    rows = conn.execute(
        f"SELECT ticket_id, opened_at, JULIANDAY(opened_at), {match.group(1)} FROM tickets"
    ).fetchall()

    def order(key: int) -> list[int]:
        return [r[0] for r in sorted(rows, key=lambda r: (r[key], r[0]))]

    chronological = [
        r[0] for r in sorted(rows, key=lambda r: (datetime.fromisoformat(r[1].rstrip("Z")), r[0]))
    ]
    assert order(1) != chronological  # raw text comparison is the trap the description names
    assert order(2) == chronological
    assert order(3) == chronological
    missing = scalar(
        conn,
        "SELECT COUNT(*) FROM tickets WHERE DATE(opened_at) IS NULL OR "
        "STRFTIME('%Y-%m', opened_at) IS NULL OR "
        "(resolved_at IS NOT NULL AND JULIANDAY(resolved_at) IS NULL)",
    )
    assert missing == 0


def test_inconsistent_casing_collapses_to_documented_values(conn: sqlite3.Connection) -> None:
    for table, column, values in (
        ("accounts", "lifecycle_stage", {"prospect", "customer", "churned", "partner"}),
        ("tickets", "priority", {"low", "normal", "high", "urgent"}),
    ):
        raw = {r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM {table}")}
        assert {v.lower() for v in raw} == values
        assert len(raw) > len(values), f"{table}.{column} has no casing noise"


def test_documented_value_lists_cover_the_data(conn: sqlite3.Connection) -> None:
    """Every enumerated value the description lists in quotes is the full set the data uses."""
    checked = 0
    for spec in TABLES:
        for col in spec.columns:
            doc = col.value_description or ""
            if col.type != "TEXT" or not doc.startswith(("One of", "Open:", "'")):
                continue
            documented = set(re.findall(r"'([^']+)'", doc))
            actual = {
                r[0]
                for r in conn.execute(
                    f"SELECT DISTINCT {col.name} FROM {spec.name} WHERE {col.name} IS NOT NULL"
                )
            }
            assert actual <= documented, f"{spec.name}.{col.name}: {actual - documented}"
            checked += 1
    assert checked >= 10


def test_customer_names_overlap_across_tenants(conn: sqlite3.Connection) -> None:
    shared = scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT LOWER(name) FROM accounts GROUP BY 1 "
        "HAVING COUNT(DISTINCT tenant_id) >= 3)",
    )
    assert isinstance(shared, int)
    assert shared >= 20


def test_nullable_columns_contain_nulls(conn: sqlite3.Connection) -> None:
    for spec in TENANT_TABLES:
        for col in spec.columns:
            if col.nullable:
                nulls = scalar(conn, f"SELECT COUNT(*) FROM {spec.name} WHERE {col.name} IS NULL")
                assert nulls, f"{spec.name}.{col.name} is documented nullable but never NULL"
