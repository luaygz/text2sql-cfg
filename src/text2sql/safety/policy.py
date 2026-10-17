"""Tenant / user scoping contract.

`ScopePolicy` is static configuration describing which tables are tenant- or owner-scoped and
which columns must never be visible to the model. `ScopeContext` is the runtime identity of the
caller; it comes from the authenticated session, never from the model, the question or the SQL.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from text2sql.catalog.schema import DatabaseSchema
from text2sql.safety.parsing import fold


@dataclass(frozen=True, slots=True)
class ScopeContext:
    tenant_id: int
    user_id: int | None = None
    """When set, owner-scoped tables are additionally filtered to rows this user owns."""

    def __post_init__(self) -> None:
        # Identities are integers by contract; anything else is a programming error upstream.
        if type(self.tenant_id) is not int:
            raise TypeError("tenant_id must be an int from the authenticated session")
        if self.user_id is not None and type(self.user_id) is not int:
            raise TypeError("user_id must be an int from the authenticated session")


@dataclass(frozen=True, slots=True)
class ScopePolicy:
    """Table and column names are matched case-insensitively (ASCII), as SQLite does."""

    tenant_column: str = "tenant_id"
    owner_column: str = "owner_user_id"
    tenant_tables: frozenset[str] = frozenset()
    owner_tables: frozenset[str] = frozenset()
    """Tables also filtered by `owner_column` in user mode; must be tenant tables as well."""
    hidden_columns: Mapping[str, frozenset[str]] = field(default_factory=dict)
    """Extra per-table columns never exposed to the model (e.g. `users.password_hash`)."""

    def __post_init__(self) -> None:
        stray = {fold(t) for t in self.owner_tables} - {fold(t) for t in self.tenant_tables}
        if stray:
            raise ValueError(f"owner tables must also be tenant tables: {sorted(stray)}")

    def is_tenant_scoped(self, table: str) -> bool:
        return fold(table) in {fold(t) for t in self.tenant_tables}

    def is_owner_scoped(self, table: str) -> bool:
        return fold(table) in {fold(t) for t in self.owner_tables}

    def hidden_for(self, table: str) -> frozenset[str]:
        """Columns of `table` the model may neither see nor name, folded to lowercase.

        The tenant column is always hidden: its value is injected by the system. The owner column
        stays visible, an ordinary foreign key the model needs for questions like "deals per
        account manager"; in user mode the guard already limits rows to the caller, so naming it
        can only narrow a result.
        """
        key = fold(table)
        hidden = {
            fold(c) for t, cols in self.hidden_columns.items() if fold(t) == key for c in cols
        }
        if self.is_tenant_scoped(table):
            hidden.add(fold(self.tenant_column))
        return frozenset(hidden)

    def visible_schema(self, schema: DatabaseSchema) -> DatabaseSchema:
        """The schema the model sees and the grammar is built from: no tenant or hidden columns."""
        return schema.without_columns({t.name: self.hidden_for(t.name) for t in schema.tables})

    def readable_columns(self, schema: DatabaseSchema) -> dict[str, frozenset[str]]:
        """Columns a scoped query may read at execution time (executor `AccessPolicy.readable`).

        The visible columns plus the tenant column the injected guards filter on. Columns in
        `hidden_columns` stay unreadable, so a query that reached them would be denied.
        """
        return {
            fold(table.name): frozenset(
                fold(c.name)
                for c in table.columns
                if fold(c.name) not in self.hidden_for(table.name) - {fold(self.tenant_column)}
            )
            for table in schema.tables
        }
