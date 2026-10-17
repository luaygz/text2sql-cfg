"""Scope policy of the SaaS CRM database, derived from the data dictionary."""

from __future__ import annotations

from text2sql.data.saas.dictionary import TABLES
from text2sql.safety.policy import ScopePolicy


def saas_scope_policy() -> ScopePolicy:
    """Tenant tables carry `tenant_id`, owner tables also `owner_user_id`; secrets are hidden.

    `tenants` is tenant-scoped on its own primary key, so a request sees exactly its own
    organisation row and never another tenant's.
    """
    return ScopePolicy(
        tenant_column="tenant_id",
        owner_column="owner_user_id",
        tenant_tables=frozenset(t.name for t in TABLES if t.scope != "global"),
        owner_tables=frozenset(t.name for t in TABLES if t.scope == "owner"),
        hidden_columns={
            t.name: frozenset(c.name for c in t.columns if c.sensitive)
            for t in TABLES
            if any(c.sensitive for c in t.columns)
        },
    )
