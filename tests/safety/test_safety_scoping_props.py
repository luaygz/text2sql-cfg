"""Layer 4 property: for generated queries, scoped results equal the identity's oracle results."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from safety_fixture import POLICY, TENANTS, foreign_canaries, query, user_ids
from safety_strategies import MAX_ROWS, Query, tenant_queries

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.safety import ScopeContext, ValidationConfig, apply_scope, validate_sql, verify_scope

TENANT = ValidationConfig(QueryMode.TENANT, max_rows=MAX_ROWS, scope=POLICY)

contexts = st.sampled_from(TENANTS).flatmap(
    lambda t: st.sampled_from([ScopeContext(t), *(ScopeContext(t, user_id=u) for u in user_ids(t))])
)


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(q=tenant_queries(), ctx=contexts)
def test_scoped_query_sees_exactly_the_identity_rows(
    q: Query,
    ctx: ScopeContext,
    crm_db: Path,
    full_schema: DatabaseSchema,
    visible_schema: DatabaseSchema,
    oracle_db: Callable[[ScopeContext], Path],
) -> None:
    validate_sql(q.sql, visible_schema, TENANT)
    scoped = apply_scope(q.sql, POLICY, ctx, schema=full_schema)
    verify_scope(scoped.sql, POLICY, user_mode=ctx.user_id is not None)
    assert set(scoped.params.values()) <= {ctx.tenant_id, ctx.user_id}
    got = query(crm_db, scoped.sql, scoped.params)
    assert got == query(oracle_db(ctx), q.sql)
    assert foreign_canaries(got, ctx.tenant_id) == []
