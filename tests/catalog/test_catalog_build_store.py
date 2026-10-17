from __future__ import annotations

import json
from pathlib import Path

import pytest

from text2sql.catalog import Catalog, build_catalog, load_catalog, render_schema, save_catalog
from text2sql.catalog.descriptions import Descriptions
from text2sql.safety.policy import ScopePolicy

POLICY = ScopePolicy(
    tenant_tables=frozenset({"accounts"}),
    hidden_columns={"customers": frozenset({"notes"})},
)


def test_catalog_records_schema_profile_and_foreign_keys(shop_db: Path) -> None:
    catalog = build_catalog(shop_db, "shop")
    assert [t.name for t in catalog.tables] == ["customers", "order", "accounts", "tags", "empty"]
    order = catalog.table("ORDER")
    assert order is not None
    assert (order.row_count, order.profiled_rows) == (6, 6)
    customer_id = catalog.column("order", "customer_id")
    assert customer_id is not None
    assert (customer_id.distinct_count, customer_id.null_rate) == (3, round(1 / 6, 4))
    assert [(fk.table, fk.column, fk.ref_table, fk.ref_column) for fk in catalog.foreign_keys] == [
        ("order", "customer_id", "customers", "id"),
        ("accounts", "owner_customer_id", "customers", "id"),
    ]
    schema = catalog.schema()
    customers, order_table = schema.table("customers"), schema.table("order")
    assert customers is not None
    assert order_table is not None
    full_name, order_id = customers.column("full name"), order_table.column("order_id")
    assert full_name is not None
    assert full_name.not_null
    assert order_id is not None
    assert order_id.primary_key


def test_policy_hides_columns_and_withholds_tenant_values(shop_db: Path) -> None:
    catalog = build_catalog(shop_db, "shop", policy=POLICY)
    accounts = catalog.table("accounts")
    assert accounts is not None
    assert accounts.samples_withheld
    assert [c.name for c in accounts.columns] == ["account_id", "name", "owner_customer_id"]
    assert all(c.samples == () and c.distinct_count is None for c in accounts.columns)
    assert catalog.column("customers", "notes") is None
    text = render_schema(catalog)
    assert "tenant_id" not in text
    assert "Secret" not in text  # another tenant's values never reach a shared prompt
    assert "notes" not in text
    # The FK from a tenant table to a global one survives the column filter.
    assert "accounts.owner_customer_id=customers.id" in text


def test_description_sources_are_exclusive(shop_db: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not both"):
        build_catalog(shop_db, "shop", description_dir=tmp_path, descriptions=Descriptions())


def test_missing_database_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_catalog(tmp_path / "absent.sqlite", "absent")


def test_json_round_trip_keeps_value_types(shop_db: Path, tmp_path: Path) -> None:
    catalog = build_catalog(shop_db, "shop")
    path = save_catalog(catalog, tmp_path)
    assert path == tmp_path / "shop.json"
    loaded = load_catalog("shop", tmp_path)
    assert loaded == catalog
    code = loaded.column("order", "code")
    amount = loaded.column("order", "amount")
    assert code is not None
    assert amount is not None
    assert [type(v) for v in code.samples] == [int, str]
    assert [type(v) for v in amount.samples] == [float, float, float]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["format_version"] == 1


def test_load_missing_catalog_names_the_build_command(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"text2sql\.catalog build"):
        load_catalog("nothing", tmp_path)


def test_unknown_fields_are_rejected(shop_db: Path) -> None:
    data = json.loads(build_catalog(shop_db, "shop").model_dump_json())
    data["tables"][0]["columns"][0]["descripton"] = "typo"
    with pytest.raises(ValueError, match="descripton"):
        Catalog.model_validate(data)
