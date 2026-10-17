"""One-line LLM descriptions per column (pipeline stage 1), one small-model call per table.

The model sees the table's column names, types, documentation, value notes and samples, and
returns `{column, description}` pairs. Requests are deterministic for a given catalog, so the
LLM client's response cache makes rebuilding free; descriptions are also stored in the
catalog JSON. Database content goes in as JSON data and the instructions (prompt
`prompts/catalog_describe.yaml`) say to treat it as such.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from text2sql.catalog.descriptions import clean_text
from text2sql.catalog.model import Catalog, CatalogTable
from text2sql.config import ReasoningEffort
from text2sql.llm.types import Message, Structured, StructuredCallFailed
from text2sql.prompts import load_prompt

PURPOSE = "catalog.describe"
PROMPT_NAME = "catalog_describe"
PAYLOAD_FORMAT = "catalog.describe/1"
"""Labels the layout of the user-message JSON (built in code, unlike the YAML instructions).
It is part of the cached request text, so change it only together with the layout."""
MAX_OUTPUT_TOKENS = 25_000
"""The output cap the committed cached responses were recorded with. It is part of the request,
and so of the cache key: changing it makes every offline rebuild miss."""


class ColumnDescription(BaseModel):
    column: str
    description: str


class TableDescriptions(BaseModel):
    columns: list[ColumnDescription]


class StructuredLLM(Protocol):
    """The part of `text2sql.llm.client.LLMClient` this module uses."""

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        max_output_tokens: int | None = None,
    ) -> Structured[T]: ...


@dataclass(frozen=True, slots=True)
class DescribeReport:
    catalog: Catalog
    calls: int
    cache_hits: int
    cost_usd: float


async def describe_columns(
    catalog: Catalog, llm: StructuredLLM, *, model: str, effort: ReasoningEffort = "low"
) -> DescribeReport:
    """Return `catalog` with `llm_description` filled in, plus what the calls cost.

    A table whose call fails structurally (refusal, truncation, bad JSON) keeps no LLM
    descriptions and gets a catalog warning; budget and offline-cache errors propagate.
    """
    targets = [t for t in catalog.tables if t.columns]  # a policy can hide every column
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(_describe_table(llm, catalog, t, model=model, effort=effort))
                for t in targets
            ]
    except ExceptionGroup as group_error:
        # Callers handle BudgetExceeded / CacheMiss by type, not as an ExceptionGroup.
        raise group_error.exceptions[0] from group_error
    results = {t.name: task.result() for t, task in zip(targets, tasks, strict=True)}

    tables: list[CatalogTable] = []
    warnings = list(catalog.warnings)
    hits = 0
    cost = 0.0
    for table in catalog.tables:
        result = results.get(table.name)
        if result is None:
            tables.append(table)
            continue
        hits += result.meta.cache_hit
        cost += result.meta.cost_usd
        if isinstance(result, StructuredCallFailed):
            warnings.append(f"llm descriptions for table {table.name!r} failed: {result}")
            tables.append(table)
            continue
        merged, table_warnings = _merge(table, result.value)
        tables.append(merged)
        warnings.extend(table_warnings)
    described = catalog.model_copy(
        update={"tables": tuple(tables), "llm_model": model, "warnings": tuple(warnings)}
    )
    return DescribeReport(catalog=described, calls=len(results), cache_hits=hits, cost_usd=cost)


async def _describe_table(
    llm: StructuredLLM,
    catalog: Catalog,
    table: CatalogTable,
    *,
    model: str,
    effort: ReasoningEffort,
) -> Structured[TableDescriptions] | StructuredCallFailed:
    messages = [
        Message(role="developer", text=load_prompt(PROMPT_NAME).render("instructions")),
        Message(role="user", text=table_payload(catalog, table)),
    ]
    try:
        return await llm.structured(
            model=model,
            messages=messages,
            output=TableDescriptions,
            effort=effort,
            purpose=PURPOSE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except StructuredCallFailed as exc:
        return exc


def table_payload(catalog: Catalog, table: CatalogTable) -> str:
    """The user message for one table: JSON, with keys in a fixed order for stable cache keys."""
    refs = {
        fk.column.lower(): f"{fk.ref_table}.{fk.ref_column}"
        for fk in catalog.foreign_keys
        if fk.table.lower() == table.name.lower()
    }
    columns: list[dict[str, Any]] = []
    for c in table.columns:
        entry: dict[str, Any] = {"name": c.name, "type": c.type or None}
        if c.primary_key:
            entry["primary_key"] = True
        if c.name.lower() in refs:
            entry["references"] = refs[c.name.lower()]
        if c.description:
            entry["documentation"] = c.description
        if c.value_description:
            entry["value_notes"] = c.value_description
        if c.samples:
            entry["frequent_values"] = list(c.samples)
        if c.null_rate is not None:
            entry["null_fraction"] = c.null_rate
        columns.append(entry)
    payload = {
        "prompt_version": PAYLOAD_FORMAT,
        "database": catalog.db_id,
        "table": table.name,
        "table_documentation": table.description,
        "row_count": None if table.samples_withheld else table.row_count,
        "columns": columns,
    }
    return json.dumps(payload, ensure_ascii=False)


def _merge(table: CatalogTable, answer: TableDescriptions) -> tuple[CatalogTable, list[str]]:
    by_name: dict[str, str] = {}
    warnings: list[str] = []
    for item in answer.columns:
        column = table.column(item.column.strip())
        text = clean_text(item.description)
        if column is None:
            warnings.append(f"llm described unknown column {table.name}.{item.column!r}")
        elif text is not None:
            by_name.setdefault(column.name, text)
    columns = tuple(
        c.model_copy(update={"llm_description": by_name.get(c.name)}) for c in table.columns
    )
    missing = [c.name for c in table.columns if c.name not in by_name]
    if missing:
        warnings.append(f"llm gave no description for {table.name} columns {missing}")
    return table.model_copy(update={"columns": columns}), warnings
