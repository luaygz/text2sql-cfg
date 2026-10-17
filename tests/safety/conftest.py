from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from safety_fixture import POLICY, Row, build_rows, visible_rows, write_db

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.safety import ScopeContext


@pytest.fixture(scope="session")
def rows() -> dict[str, list[Row]]:
    return build_rows()


@pytest.fixture(scope="session")
def crm_db(tmp_path_factory: pytest.TempPathFactory, rows: dict[str, list[Row]]) -> Path:
    return write_db(tmp_path_factory.mktemp("crm") / "crm.sqlite", rows)


@pytest.fixture(scope="session")
def full_schema(crm_db: Path) -> DatabaseSchema:
    return introspect_sqlite(crm_db)


@pytest.fixture(scope="session")
def visible_schema(full_schema: DatabaseSchema) -> DatabaseSchema:
    return POLICY.visible_schema(full_schema)


@pytest.fixture(scope="session")
def oracle_db(
    tmp_path_factory: pytest.TempPathFactory, rows: dict[str, list[Row]]
) -> Callable[[ScopeContext], Path]:
    """Database holding only what `ctx` may see (built once per identity)."""
    cache: dict[ScopeContext, Path] = {}

    def get(ctx: ScopeContext) -> Path:
        if ctx not in cache:
            directory = tmp_path_factory.mktemp(f"oracle-{ctx.tenant_id}-{ctx.user_id}")
            cache[ctx] = write_db(directory / "oracle.sqlite", visible_rows(rows, ctx))
        return cache[ctx]

    return get
