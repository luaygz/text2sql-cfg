"""Measure stages 2-3 on the BIRD Mini-Dev dev split: schema-linking recall against the columns
the gold SQL reads, linked-schema size against the full schema, and how often value retrieval
returns the exact literals the gold SQL compares columns with.

Runs analysis, value matching and linking for every question (cached calls replay for free),
writes one JSON line per question plus a summary under data/indexes/measurements/, and prints
the summary. Linking variants (one pass, both passes, plus shortlist columns) are recomputed
from the stored per-question data, so comparing them costs no extra calls.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import sqlglot
from pydantic import BaseModel, ConfigDict
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.schema import MappingSchema

from text2sql.catalog import Catalog, estimate_tokens, load_catalog, render_schema
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import get_settings
from text2sql.data.bird import BirdExample, load_split
from text2sql.evals.metrics import GoldColumnsError, Rate, gold_columns, rate
from text2sql.retrieval.analysis import DEFAULT_ANALYSIS_EFFORT, analyze_question
from text2sql.retrieval.calls import RetrievalLLM
from text2sql.retrieval.columns import ColumnIndex
from text2sql.retrieval.linking import (
    DEFAULT_LINKING_EFFORT,
    SHORTLIST_COLUMNS,
    assemble,
    link_schema,
)
from text2sql.retrieval.lsh import normalize
from text2sql.retrieval.store import index_root
from text2sql.retrieval.values import ValueIndex

type ColumnRef = tuple[str, str]
type GoldLiteral = tuple[str, str, str]
"""(table, column, literal) in catalog spelling."""


class QuestionMeasure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: int
    db_id: str
    difficulty: str
    gold_columns: list[ColumnRef] | None
    """None when the gold SQL could not be resolved against the schema."""
    linked_columns: list[ColumnRef]
    passes: list[list[ColumnRef]]
    shortlist: list[ColumnRef]
    value_columns: list[ColumnRef]
    full_columns: int
    full_tokens: int
    linked_tokens: int
    gold_literals: list[GoldLiteral]
    literal_retrievable: list[bool]
    """The literal is among the indexed values of its column."""
    literal_hits: list[bool]
    """Value retrieval returned the literal (case-insensitively) for its column."""
    cost_usd: float


class LinkingVariant(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    full_recall: Rate
    mean_column_recall: float
    mean_columns: float


class MeasureSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    questions: int
    gold_resolved: int
    variants: list[LinkingVariant]
    """The first one is what `link_schema` returns."""
    table_recall: Rate
    full_recall_by_difficulty: dict[str, Rate]
    mean_full_columns: float
    mean_full_tokens: float
    mean_linked_tokens: float
    literals: int
    retrievable_literals: int
    literal_hit_rate: Rate | None
    """Hits among retrievable literals."""
    cost_usd: float


def gold_literals(sql: str, schema: DatabaseSchema) -> set[GoldLiteral]:
    """String literals the query compares a base-table column with by `=`, `<>`, `IN` or a
    wildcard-free `LIKE`, with aliases resolved. Raises GoldColumnsError if unresolvable."""
    mapping = MappingSchema(
        {t.name: dict.fromkeys(t.column_names, "TEXT") for t in schema.tables}, dialect="sqlite"
    )
    try:
        tree = qualify(
            sqlglot.parse_one(sql, dialect="sqlite"),
            schema=mapping,
            dialect="sqlite",
            validate_qualify_columns=False,
            quote_identifiers=False,
            identify=False,
        )
        scopes = traverse_scope(tree)
    except SqlglotError as e:
        raise GoldColumnsError(f"cannot resolve {sql!r}: {e}") from e
    found: set[GoldLiteral] = set()
    for scope in scopes:
        for column in scope.columns:
            table = _base_table(scope, column.table)
            t = schema.table(table) if table else None
            c = t.column(column.name) if t else None
            if t is None or c is None:
                continue
            found.update((t.name, c.name, lit) for lit in _compared_strings(column))
    return found


def _compared_strings(column: exp.Column) -> list[str]:
    parent = column.parent
    if isinstance(parent, exp.In) and parent.this is column:
        return [e.this for e in parent.expressions if isinstance(e, exp.Literal) and e.is_string]
    if isinstance(parent, exp.EQ | exp.NEQ | exp.Like):
        other = parent.expression if parent.this is column else parent.this
        if isinstance(other, exp.Literal) and other.is_string:
            if isinstance(parent, exp.Like) and any(ch in other.this for ch in "%_"):
                return []
            return [other.this]
    return []


def _base_table(scope: Scope | None, alias: str) -> str | None:
    while scope is not None:
        source = scope.sources.get(alias)
        if isinstance(source, exp.Table):
            return source.name
        if source is not None:
            return None
        scope = scope.parent
    return None


async def measure_question(
    llm: RetrievalLLM,
    example: BirdExample,
    catalog: Catalog,
    values: ValueIndex,
    columns: ColumnIndex,
) -> QuestionMeasure:
    settings = get_settings()
    schema = catalog.schema()
    analysis = await analyze_question(
        llm,
        question=example.question,
        evidence=example.evidence,
        model=settings.small_model,
        effort=DEFAULT_ANALYSIS_EFFORT,
    )
    matches, value_calls = await values.match(analysis.value, question=example.question, llm=llm)
    link = await link_schema(
        llm,
        catalog,
        question=example.question,
        evidence=example.evidence,
        analysis=analysis.value,
        values=matches,
        model=settings.small_model,
        effort=DEFAULT_LINKING_EFFORT,
        columns=columns,
    )
    try:
        gold: list[ColumnRef] | None = sorted(gold_columns(example.gold_sql, schema))
        literals = sorted(gold_literals(example.gold_sql, schema))
    except GoldColumnsError:
        gold, literals = None, []
    matched = {(t.lower(), c.lower()): {normalize(v) for v in vs} for (t, c), vs in matches.items()}
    calls = [analysis.meta, *value_calls, *link.calls]
    return QuestionMeasure(
        question_id=example.question_id,
        db_id=example.db_id,
        difficulty=example.difficulty,
        gold_columns=gold,
        linked_columns=sorted(link.columns),
        passes=[sorted(p) for p in link.passes],
        shortlist=list(link.shortlist),
        value_columns=sorted(matches),
        full_columns=sum(len(t.columns) for t in schema.tables),
        full_tokens=estimate_tokens(render_schema(catalog)),
        linked_tokens=estimate_tokens(render_schema(catalog, subset=link.schema)),
        gold_literals=literals,
        literal_retrievable=[
            normalize(lit) in {normalize(v) for v in values.column_values(t, c)}
            for t, c, lit in literals
        ],
        literal_hits=[
            normalize(lit) in matched.get((t.lower(), c.lower()), set()) for t, c, lit in literals
        ],
        cost_usd=sum(m.cost_usd for m in calls),
    )


async def measure_split(llm: RetrievalLLM, *, limit: int | None = None) -> list[QuestionMeasure]:
    """Every dev-split question, all at once: with flex-tier retries waiting minutes, a
    database-by-database order would wait for each database's slowest question."""
    examples = load_split("dev")[:limit]
    resources = {
        db: (load_catalog(db), ValueIndex.load(db), ColumnIndex.load(db))
        for db in sorted({e.db_id for e in examples})
    }
    results = await asyncio.gather(
        *(measure_question(llm, e, *resources[e.db_id]) for e in examples)
    )
    return sorted(results, key=lambda r: r.question_id)


def summarize(
    results: Sequence[QuestionMeasure], schemas: Mapping[str, DatabaseSchema]
) -> MeasureSummary:
    """Aggregate per-question results; `schemas` (by db_id) re-derive the linking variants."""
    resolved = [r for r in results if r.gold_columns]
    retrievable = [
        hit
        for r in results
        for hit, ok in zip(r.literal_hits, r.literal_retrievable, strict=True)
        if ok
    ]
    return MeasureSummary(
        questions=len(results),
        gold_resolved=len(resolved),
        variants=_variants(resolved, schemas),
        table_recall=rate(
            [_tables(r.gold_columns or []) <= _tables(r.linked_columns) for r in resolved]
        ),
        full_recall_by_difficulty={
            level: rate([_recall(r.gold_columns or [], r.linked_columns) == 1.0 for r in group])
            for level in sorted({r.difficulty for r in resolved})
            if (group := [r for r in resolved if r.difficulty == level])
        },
        mean_full_columns=_mean(r.full_columns for r in results),
        mean_full_tokens=_mean(r.full_tokens for r in results),
        mean_linked_tokens=_mean(r.linked_tokens for r in results),
        literals=sum(len(r.gold_literals) for r in results),
        retrievable_literals=len(retrievable),
        literal_hit_rate=rate(retrievable) if retrievable else None,
        cost_usd=sum(r.cost_usd for r in results),
    )


def _tables(columns: Iterable[ColumnRef]) -> set[str]:
    return {t.lower() for t, _ in columns}


def _variants(
    resolved: Sequence[QuestionMeasure], schemas: Mapping[str, DatabaseSchema]
) -> list[LinkingVariant]:
    """The returned linking, then what `assemble` gives with parts left out. Tables a pass
    selected without any column are not stored, so the variants can only be smaller."""

    def linked(r: QuestionMeasure, *parts: Iterable[ColumnRef]) -> set[ColumnRef]:
        schema = assemble(schemas[r.db_id], [c for part in parts for c in part])
        return {(t.name, c.name) for t in schema.tables for c in t.columns}

    def top(r: QuestionMeasure) -> list[ColumnRef]:
        return r.shortlist[:SHORTLIST_COLUMNS]

    variants: dict[str, list[set[ColumnRef]]] = {
        "returned": [set(r.linked_columns) for r in resolved],
        "without shortlist columns": [
            linked(r, r.passes[0], r.passes[1], r.value_columns) for r in resolved
        ],
        "pass 1 only": [linked(r, r.passes[0], r.value_columns, top(r)) for r in resolved],
        "pass 2 only": [linked(r, r.passes[1], r.value_columns, top(r)) for r in resolved],
        "no LLM pass: shortlist columns and values": [
            linked(r, r.value_columns, top(r)) for r in resolved
        ],
    }
    out = []
    for name, sets in variants.items():
        recalls = [
            _recall(r.gold_columns or [], cols) for r, cols in zip(resolved, sets, strict=True)
        ]
        out.append(
            LinkingVariant(
                name=name,
                full_recall=rate([x == 1.0 for x in recalls]),
                mean_column_recall=_mean(recalls),
                mean_columns=_mean(len(c) for c in sets),
            )
        )
    return out


def _recall(gold: Sequence[ColumnRef], linked: Iterable[ColumnRef]) -> float:
    want = {(t.lower(), c.lower()) for t, c in gold}
    have = {(t.lower(), c.lower()) for t, c in linked}
    return len(want & have) / len(want)


def _mean(xs: Iterable[float]) -> float:
    values = list(xs)
    return sum(values) / len(values) if values else 0.0


def write_results(results: Sequence[QuestionMeasure], summary: MeasureSummary) -> Path:
    directory = index_root() / "measurements"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dev_questions.jsonl").write_text(
        "".join(r.model_dump_json() + "\n" for r in results), encoding="utf-8"
    )
    path = directory / "dev_summary.json"
    path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return path
