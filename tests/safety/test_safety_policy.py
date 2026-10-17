from __future__ import annotations

import pytest
from safety_fixture import POLICY

from text2sql.catalog.schema import DatabaseSchema
from text2sql.safety import ScopePolicy


def test_tenant_column_and_extra_hidden_columns_are_hidden() -> None:
    assert POLICY.hidden_for("users") == {"tenant_id", "password_hash"}
    assert POLICY.hidden_for("DEALS") == {"tenant_id"}
    assert POLICY.hidden_for("plans") == frozenset()


def test_names_match_case_insensitively_ascii_only() -> None:
    policy = ScopePolicy(
        tenant_tables=frozenset({"Deals"}), hidden_columns={"USERS": frozenset({"Secret"})}
    )
    assert policy.is_tenant_scoped("deals")
    assert policy.hidden_for("users") == {"secret"}
    assert not policy.is_tenant_scoped("\u212aeals")  # Kelvin sign is not K to SQLite


def test_owner_tables_must_be_tenant_tables() -> None:
    with pytest.raises(ValueError, match="owner tables"):
        ScopePolicy(tenant_tables=frozenset({"deals"}), owner_tables=frozenset({"accounts"}))


def test_visible_schema_drops_hidden_columns_and_keeps_owner(
    full_schema: DatabaseSchema,
) -> None:
    visible = POLICY.visible_schema(full_schema)
    users, deals = visible.table("users"), visible.table("deals")
    assert users is not None and deals is not None
    assert users.column_names == ("id", "name", "email")
    assert "tenant_id" not in deals.column_names
    assert "owner_user_id" in deals.column_names


def test_readable_columns_add_back_only_the_tenant_column(full_schema: DatabaseSchema) -> None:
    readable = POLICY.readable_columns(full_schema)
    assert readable["users"] == {"id", "tenant_id", "name", "email"}
    assert readable["plans"] == {"id", "name", "monthly_price"}
    assert "tenant_id" in readable["deals"]
