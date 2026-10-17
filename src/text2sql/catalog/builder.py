"""Build a `Catalog` from a SQLite file: introspect, apply the scope policy, attach descriptions,
profile every table.

LLM descriptions are a separate, async step (`text2sql.catalog.describe.describe_columns`) so
building stays synchronous, deterministic and free.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from text2sql.catalog.descriptions import ColumnNotes, Descriptions, load_bird_descriptions
from text2sql.catalog.model import Catalog, CatalogColumn, CatalogTable
from text2sql.catalog.profile import (
    DEFAULT_PROFILE_OPTIONS,
    ColumnStats,
    ProfileOptions,
    connect_readonly,
    count_rows,
    profile_table,
)
from text2sql.catalog.schema import Column, Table, introspect_sqlite

if TYPE_CHECKING:
    from text2sql.safety.policy import ScopePolicy

log = structlog.get_logger(__name__)

_NO_NOTES = ColumnNotes()


def build_catalog(
    db_path: Path,
    db_id: str,
    *,
    description_dir: Path | None = None,
    descriptions: Descriptions | None = None,
    policy: ScopePolicy | None = None,
    options: ProfileOptions = DEFAULT_PROFILE_OPTIONS,
) -> Catalog:
    """Profile `db_path` (opened read-only) into a catalog.

    `description_dir` is a BIRD `database_description` directory; `descriptions` are already
    resolved notes (e.g. the SaaS data dictionary). With a `policy`, hidden columns are removed
    before anything is read, and tenant-scoped tables get no samples or column statistics,
    because the catalog is shared by every tenant's prompts.
    """
    if description_dir is not None and descriptions is not None:
        raise ValueError("pass description_dir or descriptions, not both")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    schema = introspect_sqlite(db_path, db_id)
    withheld: frozenset[str] = frozenset()
    if policy is not None:
        schema = policy.visible_schema(schema)
        withheld = frozenset(t.lower() for t in policy.tenant_tables | policy.owner_tables)
    if description_dir is not None:
        descriptions = load_bird_descriptions(description_dir, schema)
    notes = descriptions or Descriptions()

    with closing(connect_readonly(db_path)) as conn:
        tables = tuple(
            _profiled_table(conn, db_id, t, notes, options, withhold=t.name.lower() in withheld)
            for t in schema
        )
    return Catalog(
        db_id=db_id, tables=tables, foreign_keys=schema.foreign_keys, warnings=notes.warnings
    )


def _profiled_table(
    conn: sqlite3.Connection,
    db_id: str,
    table: Table,
    notes: Descriptions,
    options: ProfileOptions,
    *,
    withhold: bool,
) -> CatalogTable:
    started = time.perf_counter()
    stats: Mapping[str, ColumnStats] = {}
    if withhold:
        row_count = profiled_rows = count_rows(conn, table.name)
    else:
        profile = profile_table(conn, table, options)
        row_count, profiled_rows, stats = profile.row_count, profile.profiled_rows, profile.columns
    log.debug(
        "catalog.table_profiled",
        db_id=db_id,
        table=table.name,
        rows=row_count,
        profiled_rows=profiled_rows,
        seconds=round(time.perf_counter() - started, 3),
    )
    return CatalogTable(
        name=table.name,
        description=notes.tables.get(table.name),
        row_count=row_count,
        profiled_rows=profiled_rows,
        samples_withheld=withhold,
        columns=tuple(
            _column_entry(c, notes.columns.get((table.name, c.name), _NO_NOTES), stats.get(c.name))
            for c in table.columns
        ),
    )


def _column_entry(column: Column, notes: ColumnNotes, stats: ColumnStats | None) -> CatalogColumn:
    return CatalogColumn(
        name=column.name,
        type=column.type,
        primary_key=column.primary_key,
        not_null=column.not_null,
        description=notes.description,
        value_description=notes.value_description,
        distinct_count=None if stats is None else stats.distinct_count,
        null_rate=None if stats is None else stats.null_rate,
        samples=() if stats is None else stats.samples,
    )
