"""Stage 3 schema linking: embedding shortlist, two small-model selection passes, recall first.

1. Embedding pass: the question, the evidence and each keyword are embedded and matched against
   the column documents (`columns.py`); each query's top columns form the shortlist.
2. LLM pass, run twice: the small model sees the schema in catalog order and in reverse order
   (tables and columns), each a fixed prefix per database so both stay in the prompt cache, plus
   the matched values, the shortlist as hints, the evidence and the question, and returns the
   tables and columns a query may need. The two answers are unioned (MCS-SQL unions shuffled
   prompts; two fixed orders keep the prefixes cacheable).
3. Value-matched columns and the top `SHORTLIST_COLUMNS` of the shortlist are added, then
   `assemble` keeps every primary key of a selected table, the declared foreign-key columns
   joining selected tables, and same-named key columns that selected tables share (most BIRD
   databases declare few foreign keys, so `transactions_1k.CustomerID` would otherwise be lost
   when both `transactions_1k` and `customers` are selected).

The model sees the whole schema when its rendering fits `FULL_VIEW_MAX_TOKENS`, which every
Mini-Dev and SaaS database does: a cached full schema costs less than an uncached per-question
subset and lets the model pick join tables the shortlist missed. Wider schemas are shown only
through the tables the shortlist and the matched values touch (the ADR-008 design).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from text2sql.catalog import Catalog, estimate_tokens, render_matched_values, render_schema
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import ReasoningEffort
from text2sql.llm import CallMeta, Message, StructuredCallFailed
from text2sql.prompts import load_prompt
from text2sql.retrieval.calls import RetrievalLLM, embed, structured_call
from text2sql.retrieval.columns import ColumnIndex, query_texts
from text2sql.retrieval.types import LinkResult, QuestionAnalysis, ValueMatches
from text2sql.retrieval.values import name_tokens

PROMPT = "schema_linking"
PURPOSE = "retrieval.linking"
TOP_PER_QUERY = 5
"""CHESS's context retrieval keeps the top 5 columns per query."""
MAX_HINTS = 15
SHORTLIST_COLUMNS = 5
"""Top shortlist columns kept even when neither pass selects them: on the dev split they lifted
full recall from 89.1% to 94.0% for 4.3 more columns per question (docs/adr/011-retrieval.md)."""
FULL_VIEW_MAX_TOKENS = 12_000
DEFAULT_LINKING_EFFORT: ReasoningEffort = "none"
"""The effort the recall numbers in docs/adr/011-retrieval.md were measured with."""
MAX_OUTPUT_TOKENS = 3_000
"""A selection is 50-400 tokens; the rest leaves room for reasoning at higher efforts."""


class LinkedColumn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    table: str
    column: str


class LinkSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tables: list[str]
    columns: list[LinkedColumn]


async def link_schema(
    llm: RetrievalLLM,
    catalog: Catalog,
    *,
    question: str,
    evidence: str | None,
    analysis: QuestionAnalysis,
    values: ValueMatches,
    model: str,
    effort: ReasoningEffort,
    columns: ColumnIndex | None = None,
) -> LinkResult:
    """The linked schema for one question. `columns` defaults to the stored column index of
    `catalog.db_id`; pass it to avoid reloading it per question."""
    index = columns or ColumnIndex.load(catalog.db_id)
    if not index.matches(catalog):
        raise ValueError(f"column index of {catalog.db_id} is stale; rebuild the indexes")
    shortlist, embed_meta = await _shortlist(llm, index, question, evidence, analysis.keywords)
    view = _view(catalog, [*(t for t, _ in shortlist), *(t for t, _ in values)])
    passes = await asyncio.gather(
        *(
            _select(
                llm,
                ordered,
                question=question,
                evidence=evidence,
                values=values,
                hints=shortlist[:MAX_HINTS],
                model=model,
                effort=effort,
            )
            for ordered in (view, _reversed(view))
        )
    )
    selected = [_resolve(catalog, s) for s, _ in passes]
    tables = {t for found_tables, _ in selected for t in found_tables}
    extra = [*values, *shortlist[:SHORTLIST_COLUMNS]]
    schema = assemble(
        catalog.schema(), [*(c for _, cols in selected for c in cols), *extra], tables
    )
    return LinkResult(
        schema=schema,
        columns=frozenset((t.name, c.name) for t in schema.tables for c in t.columns),
        calls=(embed_meta, *(m for _, m in passes)),
        shortlist=tuple(shortlist),
        passes=tuple(frozenset(cols) for _, cols in selected),
    )


def assemble(
    full: DatabaseSchema, columns: Iterable[tuple[str, str]], tables: Iterable[str] = ()
) -> DatabaseSchema:
    """The linked schema for the selected columns, plus tables selected without columns: every
    kept table's primary key, declared foreign keys among kept tables, and key columns that
    kept tables share by name (a primary key in one of them, or an `id` in the name)."""
    keep: dict[str, set[str]] = {}
    for name in tables:
        if (table := full.table(name)) is not None:
            keep.setdefault(table.name, set())
    for name, column in columns:
        if (table := full.table(name)) is not None and table.column(column) is not None:
            keep.setdefault(table.name, set()).add(column)
    kept = [t for t in full.tables if t.name in keep]
    for i, a in enumerate(kept):
        for b in kept[i + 1 :]:
            for col_a in a.columns:
                col_b = b.column(col_a.name)
                if col_b is not None and (
                    col_a.primary_key or col_b.primary_key or "id" in name_tokens(col_a.name)
                ):
                    keep[a.name].add(col_a.name)
                    keep[b.name].add(col_b.name)
    return full.subset(keep)


async def _shortlist(
    llm: RetrievalLLM,
    index: ColumnIndex,
    question: str,
    evidence: str | None,
    keywords: Sequence[str],
) -> tuple[list[tuple[str, str]], CallMeta]:
    vectors, meta = await embed(llm, query_texts(question, evidence, keywords), purpose=PURPOSE)
    return [col for col, _ in index.nearest(vectors, TOP_PER_QUERY)], meta


def _view(catalog: Catalog, touched: Iterable[str]) -> Catalog:
    """The whole catalog when it renders small enough, else only the touched tables."""
    if estimate_tokens(render_schema(catalog)) <= FULL_VIEW_MAX_TOKENS:
        return catalog
    wanted = {t.lower() for t in touched}
    return catalog.model_copy(
        update={"tables": tuple(t for t in catalog.tables if t.name.lower() in wanted)}
    )


def _reversed(catalog: Catalog) -> Catalog:
    return catalog.model_copy(
        update={
            "tables": tuple(
                t.model_copy(update={"columns": tuple(reversed(t.columns))})
                for t in reversed(catalog.tables)
            )
        }
    )


async def _select(
    llm: RetrievalLLM,
    view: Catalog,
    *,
    question: str,
    evidence: str | None,
    values: ValueMatches,
    hints: Sequence[tuple[str, str]],
    model: str,
    effort: ReasoningEffort,
) -> tuple[LinkSelection, CallMeta]:
    """One selection pass; a failed structured call selects nothing (the other pass, the
    matched values and the keys still link), and its cost is kept."""
    template = load_prompt(PROMPT)
    instructions = template.render("instructions")
    schema = template.render("schema", schema=render_schema(view))
    user = template.render(
        "user",
        matched_values=render_matched_values(view, values) or "【Matched values】 none",
        hints=", ".join(f"{t}.{c}" for t, c in hints) or "none",
        evidence=(evidence or "").strip() or "(none)",
        question=question.strip(),
    )
    messages = [
        Message("developer", f"{instructions}\n\n{schema}", cache_breakpoint=True),
        Message("user", user),
    ]
    try:
        answer = await structured_call(
            llm,
            model=model,
            messages=messages,
            output=LinkSelection,
            effort=effort,
            purpose=f"{PURPOSE} {template.tag}",
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except StructuredCallFailed as exc:
        return LinkSelection(tables=[], columns=[]), exc.meta
    return answer.value, answer.meta


def _resolve(catalog: Catalog, selection: LinkSelection) -> tuple[set[str], set[tuple[str, str]]]:
    """One selection's tables and columns in catalog spelling; unknown names are dropped."""
    tables: set[str] = set()
    columns: set[tuple[str, str]] = set()
    for name in [*selection.tables, *(pick.table for pick in selection.columns)]:
        if (table := catalog.table(_bare(name))) is not None:
            tables.add(table.name)
    for pick in selection.columns:
        table = catalog.table(_bare(pick.table))
        column = table.column(_bare(pick.column)) if table is not None else None
        if table is not None and column is not None:
            columns.add((table.name, column.name))
    return tables, columns


def _bare(name: str) -> str:
    return name.strip().strip('`"')
