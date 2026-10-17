"""Grammar coverage of gold SQL: can the full-schema grammar express every gold query?

    uv run --frozen python -m text2sql.grammar.coverage --dataset bird --split dev

For each gold query: normalize it into the grammar's spelling, parse it with lark, replay it
through llguidance (the engine behind the API) and, with `--check-results`, execute the gold
and the normalized query read-only to confirm normalization kept the result. Writes a Markdown
report and a JSON file under `reports/`.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import typer
from lark.exceptions import UnexpectedInput
from pydantic import BaseModel

from text2sql.catalog.schema import Column, DatabaseSchema, Table, introspect_sqlite
from text2sql.config import REPO_ROOT
from text2sql.grammar.builder import build_grammar
from text2sql.grammar.conventions import AGGREGATES, SCALAR_FUNCTIONS
from text2sql.grammar.errors import NormalizationError
from text2sql.grammar.model import GrammarOptions, SqlGrammar
from text2sql.grammar.normalize import normalize_sql
from text2sql.grammar.validate import GuidanceMatcher, lark_parser
from text2sql.sqlite_budget import CHECK_INTERVAL, StepBudget, steps_for

GoldSource = Literal["bird", "arcwise"]
_FUNCTION_CALL = re.compile(r"\b([A-Z_][A-Z0-9_]*)\(")
_KNOWN_CALLS = frozenset((*AGGREGATES, *SCALAR_FUNCTIONS, "CAST", "EXISTS"))


@dataclass(frozen=True)
class GoldQuery:
    question_id: int
    db_id: str
    source: GoldSource
    sql: str


class CaseResult(BaseModel):
    question_id: int
    db_id: str
    source: GoldSource
    gold_sql: str
    normalized: str | None
    covered: bool
    guidance_agrees: bool | None
    """llguidance's verdict equals lark's; None when normalization failed."""
    same_result: bool | None = None
    """Gold and normalized SQL return the same rows; None when not checked or not runnable."""
    category: str | None = None
    detail: str | None = None


class DatabaseGrammar(BaseModel):
    db_id: str
    tables: int
    columns: int
    chars: int
    regex_atoms: int
    symbol_refs: int
    api_load: float


class CoverageReport(BaseModel):
    dataset: str
    split: str
    created_at: str
    options: str
    databases: list[DatabaseGrammar]
    cases: list[CaseResult]

    def coverage(self, source: GoldSource | None = None, db_id: str | None = None) -> float:
        picked = [
            c
            for c in self.cases
            if (source is None or c.source == source) and (db_id is None or c.db_id == db_id)
        ]
        return sum(c.covered for c in picked) / len(picked) if picked else 0.0


def measure_coverage(
    queries: Iterable[GoldQuery],
    schemas: Callable[[str], DatabaseSchema],
    *,
    options: GrammarOptions | None = None,
    db_paths: Callable[[str], Path] | None = None,
) -> tuple[list[CaseResult], dict[str, SqlGrammar]]:
    """Check every query; pass `db_paths` to also compare gold and normalized results."""
    grammars: dict[str, SqlGrammar] = {}
    matchers: dict[str, GuidanceMatcher] = {}
    results = []
    for query in queries:
        if query.db_id not in grammars:
            grammars[query.db_id] = build_grammar(schemas(query.db_id), options or GrammarOptions())
            matchers[query.db_id] = GuidanceMatcher(grammars[query.db_id].definition)
        grammar = grammars[query.db_id]
        result = _check(query, grammar, matchers[query.db_id])
        if db_paths is not None and result.normalized is not None:
            result.same_result = _same_result(db_paths(query.db_id), query.sql, result.normalized)
            if result.same_result is False:
                result.covered = False
                result.category = "normalization changed the result"
        results.append(result)
    return results, grammars


def _check(query: GoldQuery, grammar: SqlGrammar, matcher: GuidanceMatcher) -> CaseResult:
    result = CaseResult(
        question_id=query.question_id,
        db_id=query.db_id,
        source=query.source,
        gold_sql=query.sql,
        normalized=None,
        covered=False,
        guidance_agrees=None,
    )
    try:
        result.normalized = normalize_sql(query.sql, grammar.schema)
    except NormalizationError as exc:
        result.category, result.detail = "normalization failed", str(exc)
        return result
    try:
        lark_parser(grammar.definition).parse(result.normalized)
        result.covered = True
    except UnexpectedInput as exc:
        result.detail = exc.get_context(result.normalized, 50).replace("\n", " | ")
        result.category = _categorize(result.normalized)
    result.guidance_agrees = matcher.accepts(result.normalized) == result.covered
    if not result.guidance_agrees:
        result.category = "lark and llguidance disagree"
    return result


def _categorize(sql: str) -> str:
    if re.search(r"\bOVER \(", sql):
        return "window function"
    if re.search(r" NULLS (?:FIRST|LAST)\b", sql):
        return "NULLS FIRST/LAST"
    unknown = sorted({m for m in _FUNCTION_CALL.findall(sql) if m not in _KNOWN_CALLS})
    if unknown:
        return f"function not in allowlist: {', '.join(unknown)}"
    return "other syntax"


def _same_result(db_path: Path, gold: str, normalized: str, timeout_s: float = 30.0) -> bool | None:
    """Multiset comparison of both results; None if the gold itself fails or times out."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, cached_statements=0)
    try:
        rows: list[Counter[tuple[object, ...]]] = []
        for sql in (gold, normalized):
            conn.set_progress_handler(StepBudget(steps_for(timeout_s)), CHECK_INTERVAL)
            try:
                rows.append(Counter(conn.execute(sql).fetchall()))
            except sqlite3.Error:
                return None if not rows else False
        return rows[0] == rows[1]
    finally:
        conn.close()


def render_markdown(report: CoverageReport) -> str:
    sources = sorted({c.source for c in report.cases})
    lines = [
        f"# Grammar coverage: {report.dataset} {report.split}",
        "",
        f"Generated {report.created_at} by `python -m text2sql.grammar.coverage`."
        f" Grammar options: {report.options}.",
        "",
        "| Gold SQL | Queries | Covered | Coverage | lark/llguidance agree | Result unchanged |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for source in sources:
        picked = [c for c in report.cases if c.source == source]
        checked = [c for c in picked if c.same_result is not None]
        agree = [c for c in picked if c.guidance_agrees is not None]
        result = f"{sum(c.same_result is True for c in checked)}/{len(checked)}"
        lines.append(
            f"| {source} | {len(picked)} | {sum(c.covered for c in picked)} |"
            f" {report.coverage(source):.1%} | {sum(c.guidance_agrees is True for c in agree)}"
            f"/{len(agree)} | {result if checked else 'not run'} |"
        )
    lines += [
        "",
        "## Per database",
        "",
        "| Database | Tables | Columns | Grammar chars | Regex atoms | Rule symbols"
        " | Est. API load | " + " | ".join(sources) + " |",
        "| --- " * (7 + len(sources)) + "|",
    ]
    for db in report.databases:
        cov = " | ".join(f"{report.coverage(s, db.db_id):.1%}" for s in sources)
        lines.append(
            f"| {db.db_id} | {db.tables} | {db.columns} | {db.chars} | {db.regex_atoms} |"
            f" {db.symbol_refs} | {db.api_load:.2f} | {cov} |"
        )
    failures = [c for c in report.cases if not c.covered]
    lines += ["", "## Failures by category", ""]
    for category, count in Counter(c.category for c in failures).most_common():
        lines.append(f"- {category}: {count}")
    lines += ["", "## Failures", ""]
    for case in failures:
        lines += [
            f"### {case.source} {case.question_id} ({case.db_id}): {case.category}",
            "",
            "```sql",
            case.normalized or case.gold_sql,
            "```",
            "",
        ]
        if case.detail:
            lines += [f"Detail: `{case.detail}`", ""]
    return "\n".join(lines)


class Dataset(StrEnum):
    BIRD = "bird"


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"
    MINIDEV = "minidev"


def _bird_queries(split: Split) -> list[GoldQuery]:
    from text2sql.data.bird import load_minidev, load_split

    if split is Split.MINIDEV:
        examples = load_minidev()
    else:
        examples = load_split("dev" if split is Split.DEV else "test")
    queries = [GoldQuery(e.question_id, e.db_id, "bird", e.gold_sql) for e in examples]
    queries += [
        GoldQuery(e.question_id, e.db_id, "arcwise", e.gold_sql_arcwise)
        for e in examples
        if e.gold_sql_arcwise is not None
    ]
    return queries


class FixtureTable(BaseModel):
    name: str
    columns: list[str]


class CoverageFixture(BaseModel):
    """Table and column names plus gold SQL of a split: enough to measure grammar coverage
    (without `--check-results`) where the BIRD databases are not downloaded, as in CI."""

    split: str
    databases: dict[str, list[FixtureTable]]
    queries: list[GoldQuery]

    @classmethod
    def from_schemas(
        cls, split: str, queries: list[GoldQuery], schemas: Iterable[DatabaseSchema]
    ) -> CoverageFixture:
        databases = {
            s.db_id: [FixtureTable(name=t.name, columns=list(t.column_names)) for t in s.tables]
            for s in schemas
        }
        return cls(split=split, databases=databases, queries=queries)

    def database_schema(self, db_id: str) -> DatabaseSchema:
        tables = tuple(
            Table(name=t.name, columns=tuple(Column(name=c) for c in t.columns))
            for t in self.databases[db_id]
        )
        return DatabaseSchema(db_id=db_id, tables=tables)


def main(
    dataset: Annotated[Dataset, typer.Option()] = Dataset.BIRD,
    split: Annotated[Split, typer.Option()] = Split.DEV,
    check_results: Annotated[
        bool, typer.Option(help="Execute gold and normalized SQL and compare results.")
    ] = False,
    out_dir: Annotated[Path, typer.Option()] = REPO_ROOT / "reports",
    write_fixture: Annotated[
        Path | None,
        typer.Option(help="Write the split's schemas and gold SQL to this JSON file and exit."),
    ] = None,
) -> None:
    from text2sql.data.bird import bird_db_path

    queries = _bird_queries(split)
    schema_cache: dict[str, DatabaseSchema] = {}

    def schema(db_id: str) -> DatabaseSchema:
        if db_id not in schema_cache:
            schema_cache[db_id] = introspect_sqlite(bird_db_path(db_id), db_id)
        return schema_cache[db_id]

    if write_fixture is not None:
        db_ids = sorted({q.db_id for q in queries})
        fixture = CoverageFixture.from_schemas(split.value, queries, map(schema, db_ids))
        write_fixture.parent.mkdir(parents=True, exist_ok=True)
        write_fixture.write_text(fixture.model_dump_json(indent=1) + "\n")
        typer.echo(f"wrote {write_fixture}")
        return

    options = GrammarOptions()
    cases, grammars = measure_coverage(
        queries, schema, options=options, db_paths=bird_db_path if check_results else None
    )
    report = CoverageReport(
        dataset=dataset.value,
        split=split.value,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        options=f"mode={options.mode.value}, max_rows={options.max_rows}, full schema",
        databases=[_describe(g) for g in sorted(grammars.values(), key=lambda g: g.schema.db_id)],
        cases=cases,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"grammar_coverage_{split.value}"
    stem.with_suffix(".json").write_text(report.model_dump_json(indent=1))
    stem.with_suffix(".md").write_text(render_markdown(report))
    for source in sorted({c.source for c in cases}):
        picked = [c for c in cases if c.source == source]
        typer.echo(f"{source}: {report.coverage(source):.1%} of {len(picked)} gold queries")
    for db in report.databases:
        typer.echo(
            f"  {db.db_id}: "
            + ", ".join(
                f"{s} {report.coverage(s, db.db_id):.1%}" for s in sorted({c.source for c in cases})
            )
        )
    typer.echo(f"wrote {stem.with_suffix('.md')} and {stem.with_suffix('.json')}")


def _describe(grammar: SqlGrammar) -> DatabaseGrammar:
    size = grammar.size
    return DatabaseGrammar(
        db_id=grammar.schema.db_id,
        tables=len(grammar.schema.tables),
        columns=len({c.name for t in grammar.schema.tables for c in t.columns}),
        chars=size.chars,
        regex_atoms=size.regex_atoms,
        symbol_refs=size.symbol_refs,
        api_load=size.api_load,
    )


if __name__ == "__main__":
    typer.run(main)
