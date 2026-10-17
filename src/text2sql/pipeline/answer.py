"""The answer stage: result preview, schema elements and the optional explanation.

Schema elements are read from the chosen SQL with sqlglot rather than asked of a model, so they
are exact. The explanation call sees the question, the SQL and those elements but no result
rows: rows are database values, which may carry planted instructions, and describing what a
query does needs none of them.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import Settings
from text2sql.evals.metrics import GoldColumnsError, gold_columns
from text2sql.evals.records import JsonScalar, ResultPreview
from text2sql.execution import Cell, QueryResult
from text2sql.llm import LLMClient, Message, Structured
from text2sql.prompts import load_prompt

PREVIEW_ROWS = 10
EXPLAIN_PURPOSE = "answer.explain"


class Explanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation: str = Field(
        description="Two or three plain sentences on what the query returns and how it gets "
        "there (tables joined, filters, grouping, ordering), for a non-technical reader."
    )


def preview(result: QueryResult, rows: int = PREVIEW_ROWS) -> ResultPreview:
    return ResultPreview(
        columns=list(result.columns),
        rows=[[_json_cell(cell) for cell in row] for row in result.rows[:rows]],
        row_count=len(result.rows),
    )


def _json_cell(cell: Cell) -> JsonScalar:
    return cell.hex() if isinstance(cell, bytes) else cell


def schema_elements(sql: str, schema: DatabaseSchema) -> list[str]:
    """`table.column` of every base column `sql` reads, sorted; [] if sqlglot cannot resolve it."""
    try:
        columns = gold_columns(sql, schema)
    except GoldColumnsError:
        return []
    return sorted(f"{table}.{column}" for table, column in columns)


def explain_tag() -> str:
    return load_prompt("explain").tag


async def explain(
    llm: LLMClient,
    settings: Settings,
    *,
    question: str,
    sql: str,
    elements: Sequence[str],
) -> Structured[Explanation]:
    """One small-model call; raises StructuredCallFailed like any structured call."""
    template = load_prompt("explain")
    request = template.render(
        "request",
        question=question,
        sql=sql,
        schema_elements=", ".join(elements) or "(none resolved)",
    )
    return await llm.structured(
        model=settings.small_model,
        messages=[
            Message("developer", template.render("instructions")),
            Message("user", request),
        ],
        output=Explanation,
        effort=settings.small_effort,
        purpose=EXPLAIN_PURPOSE,
    )
