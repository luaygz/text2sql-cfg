"""Prompt pieces shared by the LLM selectors: result previews and the schema they are shown."""

from __future__ import annotations

import json
from collections.abc import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from text2sql.catalog import Catalog, render_schema
from text2sql.catalog.schema import DatabaseSchema
from text2sql.evals.metrics import GoldColumnsError, gold_columns
from text2sql.selection.clustering import ExecutedCandidate

PREVIEW_ROWS = 10
"""Rows shown per result (XiYan-SQL shows 10, CHESS 20; ADR-008)."""
_MAX_VALUE_CHARS = 200


def render_result(cand: ExecutedCandidate, *, limit: int = PREVIEW_ROWS) -> str:
    """Column names, row count and the first `limit` rows, one JSON array per row."""
    count = f"more than {len(cand.rows)} (truncated)" if cand.truncated else str(len(cand.rows))
    lines = [
        f"columns: {json.dumps(list(cand.columns), ensure_ascii=False)}",
        f"total rows: {count}",
    ]
    if len(cand.rows) > limit:
        lines.append(f"first {limit} rows:")
    lines.extend(
        json.dumps([_preview_value(v) for v in row], ensure_ascii=False)
        for row in cand.rows[:limit]
    )
    return "\n".join(lines)


def schema_for(
    sqls: Iterable[str],
    *,
    fallback: str,
    catalog: Catalog | None,
    schema: DatabaseSchema | None,
) -> str:
    """The rendered union of the tables and columns the queries read (CHASE-SQL's selector
    schema), with primary and foreign keys of those tables kept.

    `schema` is what the candidates were written against (the visible schema in tenant mode);
    it defaults to the catalog's full schema. Returns `fallback` without a catalog, when a
    query cannot be resolved, or when the queries name no known table.
    """
    if catalog is None:
        return fallback
    base = schema if schema is not None else catalog.schema()
    keep: dict[str, set[str]] = {}
    try:
        for sql in sqls:
            for table in sqlglot.parse_one(sql, dialect="sqlite").find_all(exp.Table):
                known = base.table(table.name)
                if known is not None:
                    keep.setdefault(known.name, set())
            for table_name, column in gold_columns(sql, base):
                keep.setdefault(table_name, set()).add(column)
    except (SqlglotError, GoldColumnsError):
        return fallback
    if not keep:
        return fallback
    return render_schema(catalog, subset=base.subset(keep))


def evidence_text(evidence: str | None) -> str:
    return evidence.strip() if evidence and evidence.strip() else "(none)"


def _preview_value(value: object) -> object:
    if value is None or isinstance(value, int | float):
        return value
    if isinstance(value, bytes):
        return f"<blob, {len(value)} bytes>"
    text = str(value)
    return text if len(text) <= _MAX_VALUE_CHARS else text[:_MAX_VALUE_CHARS] + "..."
