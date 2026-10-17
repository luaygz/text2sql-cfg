"""SaaS data dictionary, schema loading and the scope policy the model's view is built from."""

from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from text2sql.catalog.schema import DatabaseSchema
from text2sql.data.saas import load_saas_schema, saas_scope_policy
from text2sql.data.saas.generate import generate_database
from text2sql.safety import ALLOWED_FUNCTIONS

GLOBAL_TABLES = {"currencies", "countries", "industries", "plans"}
SCOPED_TABLES = {
    "accounts",
    "contacts",
    "deals",
    "invoices",
    "payments",
    "subscriptions",
    "tickets",
    "users",
    "activities",
}
SECRETS = {("users", "password_hash"), ("tenants", "api_key")}


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("saas_schema") / "crm.sqlite"
    generate_database(path)
    return path


@pytest.fixture(scope="module")
def schema(db: Path) -> DatabaseSchema:
    return load_saas_schema(db)


def test_schema_size_and_reference_tables(schema: DatabaseSchema) -> None:
    assert 12 <= len(schema.tables) <= 20
    for name in GLOBAL_TABLES:
        table = schema.table(name)
        assert table is not None
        assert table.column("tenant_id") is None


def test_policy_scopes_exactly_the_tables_with_scope_columns(schema: DatabaseSchema) -> None:
    policy = saas_scope_policy()
    with_tenant = {t.name for t in schema.tables if t.column("tenant_id")}
    with_owner = {t.name for t in schema.tables if t.column("owner_user_id")}
    assert set(policy.tenant_tables) == with_tenant
    assert set(policy.owner_tables) == with_owner
    assert with_tenant >= SCOPED_TABLES
    assert not GLOBAL_TABLES & with_tenant
    assert with_owner <= with_tenant
    owner_fks = {
        fk.table
        for fk in schema.foreign_keys
        if fk.column == "owner_user_id" and (fk.ref_table, fk.ref_column) == ("users", "user_id")
    }
    assert owner_fks == with_owner


def test_visible_schema_hides_tenant_and_secret_columns(schema: DatabaseSchema) -> None:
    visible = saas_scope_policy().visible_schema(schema)
    assert visible.table_names == schema.table_names
    columns = {(t.name, c.name) for t in visible.tables for c in t.columns}
    assert not any(column == "tenant_id" for _, column in columns)
    assert not columns & SECRETS
    assert ("accounts", "owner_user_id") in columns
    assert all("tenant_id" not in (fk.column, fk.ref_column) for fk in visible.foreign_keys)
    tenants = visible.table("tenants")
    assert tenants is not None
    assert tenants.column_names == ("name", "country_code", "default_currency_code", "signed_up_at")


def test_every_table_and_column_the_model_sees_is_described(schema: DatabaseSchema) -> None:
    visible = saas_scope_policy().visible_schema(schema)
    for table in visible.tables:
        assert table.description, table.name
        for column in table.columns:
            assert column.description, f"{table.name}.{column.name}"
            text = f"{column.description} {column.value_description or ''}"
            assert "tenant" not in text.lower(), f"{table.name}.{column.name} mentions tenants"


def test_descriptions_only_recommend_functions_the_model_may_use(schema: DatabaseSchema) -> None:
    visible = saas_scope_policy().visible_schema(schema)
    texts = [t.description or "" for t in visible.tables] + [
        f"{c.description} {c.value_description or ''}" for t in visible.tables for c in t.columns
    ]
    named = {m for text in texts for m in re.findall(r"\b([A-Z][A-Z_]*)\(", text)}
    assert {"JULIANDAY", "INSTR", "LOWER"} <= named
    assert named <= ALLOWED_FUNCTIONS


def test_misleading_payment_amount_is_disambiguated(schema: DatabaseSchema) -> None:
    payments = schema.table("payments")
    assert payments is not None
    amount = payments.column("amount")
    assert amount is not None
    assert "cents" in f"{amount.description} {amount.value_description}".lower()


def test_loading_a_database_with_undocumented_columns_fails(db: Path, tmp_path: Path) -> None:
    drifted = tmp_path / "drifted.sqlite"
    shutil.copyfile(db, drifted)
    conn = sqlite3.connect(drifted)
    conn.execute("ALTER TABLE accounts ADD COLUMN internal_notes TEXT")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match=r"accounts\.internal_notes"):
        load_saas_schema(drifted)


def test_loading_a_database_with_an_undocumented_table_fails(db: Path, tmp_path: Path) -> None:
    drifted = tmp_path / "drifted.sqlite"
    shutil.copyfile(db, drifted)
    conn = sqlite3.connect(drifted)
    conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, entry TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="audit_log"):
        load_saas_schema(drifted)
