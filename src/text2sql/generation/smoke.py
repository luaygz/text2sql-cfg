r"""Live smoke run of every strategy on a few BIRD dev questions (ADR-012 measurements).

    T2SQL_PHASE=generation MAX_SPEND_USD=0.30 MAX_OUTPUT_TOKENS=8000 \
        uv run --frozen python -m text2sql.generation.smoke [--effort medium] [--force-repair]

Each question gets one candidate per strategy, in a fixed order so that the full-schema
strategies show the prompt cache (a write on the first, reads after). A candidate whose query
fails or returns no rows gets one repair turn. When none does, `--force-repair` sends the
empty-result feedback to one candidate per question (the first that misses gold, else the
first) although its result was not empty: a counterfactual check turn that measures what a
repair turn costs and whether the gentle wording keeps a correct query. Responses are cached
(the key includes `max_output_tokens`, hence the fixed 8,000), so a rerun with the same
settings replays at no cost; OFFLINE=1 forbids API calls.

This harness is not the pipeline: the linked view is every column of the tables the gold SQL
reads (an oracle), there is no value retrieval or question analysis, and the few-shots are the
three train questions most similar in wording. It measures tokens, cost, latency and grammar
validity per strategy; three questions say little about accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from functools import cache

import sqlglot
from sqlglot import exp

from text2sql.catalog import load_catalog, render_schema
from text2sql.catalog.model import Catalog
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode, ReasoningEffort, Settings, get_settings
from text2sql.data.bird import BirdExample, bird_db_path, load_bird_train, load_split
from text2sql.evals.bird_metric import SqlRunError, execute_readonly, execution_match
from text2sql.generation.candidates import generate_candidate, repair_candidate
from text2sql.generation.prompting import GenerationContext, repair_feedback
from text2sql.generation.strategies import STRATEGIES, StrategySpec, model_for
from text2sql.grammar import GrammarOptions, NormalizationError, build_grammar, normalize_sql
from text2sql.llm import CallMeta, GrammarCallFailed, LLMClient, SqlToolCall
from text2sql.retrieval import FewShotExample

DEFAULT_QUESTIONS = (779, 89, 62)
"""superhero (simple), financial (moderate), california_schools (challenging)."""
FEWSHOT_K = 3


@dataclass(frozen=True)
class Case:
    example: BirdExample
    ctx: GenerationContext


@dataclass(frozen=True)
class Row:
    case: Case
    label: str
    effort: ReasoningEffort
    meta: CallMeta
    grammar_ok: bool
    rows: int | None
    """Result rows of the candidate, None when it did not run."""
    correct: bool | None
    sql: str


@dataclass(frozen=True)
class Repair:
    case: Case
    spec: StrategySpec
    previous: SqlToolCall
    feedback: str


def linked_schema(catalog: Catalog, gold_sql: str) -> DatabaseSchema:
    """Every column of the tables the gold query reads (oracle table linking)."""
    schema = catalog.schema()
    tree = sqlglot.parse_one(gold_sql, read="sqlite")
    names = {t.name.lower() for t in tree.find_all(exp.Table)}
    return schema.subset({t.name: None for t in schema.tables if t.name.lower() in names})


@cache
def _train_pool() -> tuple[FewShotExample, ...]:
    shots = []
    for ex in load_bird_train():
        try:
            sql = normalize_sql(ex.gold_sql)
        except NormalizationError:
            sql = ex.gold_sql
        shots.append(FewShotExample(ex.question, ex.evidence or None, sql))
    return tuple(shots)


def similar_fewshots(question: str, k: int = FEWSHOT_K) -> list[FewShotExample]:
    matcher = difflib.SequenceMatcher(b=question.lower(), autojunk=False)
    scored = []
    for shot in _train_pool():
        matcher.set_seq1(shot.question.lower())
        scored.append((-matcher.ratio(), shot.question, shot))
    scored.sort(key=lambda s: (s[0], s[1]))
    return [shot for _, _, shot in scored[:k]]


def case_for(example: BirdExample) -> Case:
    catalog = load_catalog(example.db_id)
    options = GrammarOptions(mode=QueryMode.BENCHMARK)
    linked = linked_schema(catalog, example.gold_sql)
    ctx = GenerationContext(
        db_id=example.db_id,
        question=example.question,
        evidence=example.evidence,
        mode=QueryMode.BENCHMARK,
        schema_text={
            "full": render_schema(catalog),
            "linked": render_schema(catalog, subset=linked),
        },
        grammars={
            "full": build_grammar(catalog.schema(), options),
            "linked": build_grammar(linked, options),
        },
        fewshots=similar_fewshots(example.question),
    )
    return Case(example, ctx)


def score(sql: str, example: BirdExample) -> tuple[int | None, bool | None, str | None]:
    """Rows returned, EX against the original gold, and the SQLite error if the query failed."""
    db = bird_db_path(example.db_id, "minidev")
    try:
        rows = len(execute_readonly(sql, db))
    except SqlRunError as exc:
        return None, False, str(exc)
    return rows, execution_match(sql, example.gold_sql, db), None


async def measure(
    case: Case, spec: StrategySpec, label: str, call: Awaitable[SqlToolCall]
) -> tuple[Row, SqlToolCall | None, str | None]:
    """Await one grammar call and score it; also returns the call and any SQLite error."""
    try:
        result = await call
    except GrammarCallFailed as exc:
        failed = Row(case, label, spec.effort, exc.meta, False, None, None, exc.raw_input or "")
        return failed, None, None
    rows, correct, error = score(result.output.text, case.example)
    row = Row(case, label, spec.effort, result.meta, True, rows, correct, result.output.text)
    return row, result, error


def strategies(names: Sequence[str], effort: ReasoningEffort | None) -> list[StrategySpec]:
    specs = [STRATEGIES[name] for name in names]
    if effort is None:
        return specs
    return [
        s.model_copy(update={"effort": effort}) if s.model_tier == "generator" else s for s in specs
    ]


async def run(
    question_ids: Sequence[int],
    names: Sequence[str],
    effort: ReasoningEffort | None,
    *,
    force_repair: bool,
    settings: Settings,
) -> list[Row]:
    by_id = {e.question_id: e for e in load_split("dev")}
    out: list[Row] = []
    repairs: list[Repair] = []
    checks: list[Repair] = []
    empty = repair_feedback(kind="empty", detail="")
    async with LLMClient(settings) as llm:
        for qid in question_ids:
            case = case_for(by_id[qid])
            ran: list[tuple[bool | None, Repair]] = []
            for spec in strategies(names, effort):
                model = model_for(spec, settings)
                call = generate_candidate(llm, spec, case.ctx, model=model, sample=0)
                row, result, error = await measure(case, spec, spec.name, call)
                out.append(row)
                if result is None:
                    continue
                if error is not None:
                    feedback = repair_feedback(kind="error", detail=error)
                    repairs.append(Repair(case, spec, result, feedback))
                elif row.rows == 0:
                    repairs.append(Repair(case, spec, result, empty))
                else:
                    ran.append((row.correct, Repair(case, spec, result, empty)))
            # The forced check goes to the first candidate that misses gold, else the first.
            wrong = [r for correct, r in ran if not correct]
            if wrong or ran:
                checks.append((wrong or [r for _, r in ran])[0])
        forcing = force_repair and not repairs
        for r in checks if forcing else repairs:
            model = model_for(r.spec, settings)
            call = repair_candidate(
                llm, r.spec, r.case.ctx, r.previous, r.feedback, model=model, attempt=1
            )
            label = f"{r.spec.name} {'forced check' if forcing else 'repair'}"
            row, _, _ = await measure(r.case, r.spec, label, call)
            out.append(row)
    return out


def markdown(rows: list[Row]) -> str:
    lines = [
        "| Q | strategy | effort | input | cached | cache write | output | reasoning | USD |"
        " latency s | grammar | rows | EX |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for r in rows:
        u = r.meta.usage
        ex = r.case.example
        lines.append(
            f"| {ex.question_id} {ex.difficulty} | {r.label} | {r.effort} | {u.input_tokens:,} | "
            f"{u.cached_tokens:,} | {u.cache_write_tokens:,} | {u.output_tokens:,} | "
            f"{u.reasoning_tokens:,} | {r.meta.priced_usd:.5f} | {r.meta.api_latency_s:.1f} | "
            f"{'ok' if r.grammar_ok else 'FAILED'} | {'-' if r.rows is None else r.rows} | "
            f"{'-' if r.correct is None else ('yes' if r.correct else 'no')} |"
        )
    priced = sum(r.meta.priced_usd for r in rows)
    billed = sum(r.meta.cost_usd for r in rows)
    lines.append(f"\nPriced total ${priced:.4f}; billed by this run ${billed:.4f}.\n")
    lines.extend(f"{r.case.example.question_id} {r.label}: {r.sql}" for r in rows)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live smoke run of the generation strategies.")
    parser.add_argument("--questions", type=int, nargs="+", default=list(DEFAULT_QUESTIONS))
    parser.add_argument(
        "--strategies", nargs="+", choices=list(STRATEGIES), default=list(STRATEGIES)
    )
    parser.add_argument(
        "--effort", choices=["low", "medium", "high"], help="override generator-tier effort"
    )
    parser.add_argument("--force-repair", action="store_true")
    args = parser.parse_args()
    rows = asyncio.run(
        run(
            args.questions,
            args.strategies,
            args.effort,
            force_repair=args.force_repair,
            settings=get_settings(),
        )
    )
    print(markdown(rows))


if __name__ == "__main__":
    main()
