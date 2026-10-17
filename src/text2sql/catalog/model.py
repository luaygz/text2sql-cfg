"""The schema catalog: one JSON document per database, built offline and loaded by every stage.

A catalog is the `DatabaseSchema` plus everything a prompt or a retriever wants to know about
the data: row counts, per-column distinct counts and null rates, a few frequent values, and
descriptions from three sources (BIRD CSVs or the SaaS data dictionary, plus an LLM one-liner).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from text2sql.catalog.schema import Column, DatabaseSchema, ForeignKey, Table

type SampleValue = str | int | float
"""A column value as SQLite returned it; the type is kept so prompts can show `'1'` vs `1`."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CatalogColumn(_Frozen):
    name: str
    type: str = ""
    primary_key: bool = False
    not_null: bool = False
    description: str | None = None
    """Human description: BIRD `database_description` CSV or the SaaS data dictionary."""
    value_description: str | None = None
    """Notes on encodings, units and allowed values (BIRD `value_description`)."""
    llm_description: str | None = None
    """One-line description written by the small model from names, types and samples."""
    distinct_count: int | None = None
    """Distinct non-null values among the profiled rows; `None` when profiling was withheld."""
    null_rate: float | None = None
    """Fraction of profiled rows that are NULL; `None` when profiling was withheld."""
    samples: tuple[SampleValue, ...] = ()
    """Most frequent non-null, non-empty values, most frequent first, long text truncated."""

    @property
    def best_description(self) -> str | None:
        """The human description when there is one, otherwise the LLM one-liner."""
        return self.description or self.llm_description


class CatalogTable(_Frozen):
    name: str
    description: str | None = None
    row_count: int
    profiled_rows: int
    """Rows the column statistics came from; smaller than `row_count` when the table was sampled."""
    samples_withheld: bool = False
    """True for tenant-scoped tables: their values belong to individual tenants, so the catalog
    (which is shared by every tenant's prompts) stores no samples or statistics for them."""
    columns: tuple[CatalogColumn, ...]

    def column(self, name: str) -> CatalogColumn | None:
        key = name.lower()
        return next((c for c in self.columns if c.name.lower() == key), None)


class Catalog(_Frozen):
    format_version: Literal[1] = 1
    db_id: str
    tables: tuple[CatalogTable, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    llm_model: str | None = None
    """Model that wrote `llm_description`; `None` when the catalog was built without the LLM."""
    warnings: tuple[str, ...] = ()
    """Ingestion problems worth a look (unmatched description files or columns, LLM gaps)."""

    def table(self, name: str) -> CatalogTable | None:
        key = name.lower()
        return next((t for t in self.tables if t.name.lower() == key), None)

    def column(self, table: str, column: str) -> CatalogColumn | None:
        t = self.table(table)
        return None if t is None else t.column(column)

    # Shadows pydantic's deprecated v1 `BaseModel.schema()` classmethod (use model_json_schema).
    def schema(self) -> DatabaseSchema:  # type: ignore[override]
        """The identifier-level view used by the grammar builder, validator and scoping layer."""
        return DatabaseSchema(
            db_id=self.db_id,
            tables=tuple(
                Table(
                    name=t.name,
                    description=t.description,
                    columns=tuple(
                        Column(
                            name=c.name,
                            type=c.type,
                            primary_key=c.primary_key,
                            not_null=c.not_null,
                            description=c.best_description,
                            value_description=c.value_description,
                            sample_values=tuple(str(v) for v in c.samples),
                        )
                        for c in t.columns
                    ),
                )
                for t in self.tables
            ),
            foreign_keys=self.foreign_keys,
        )
