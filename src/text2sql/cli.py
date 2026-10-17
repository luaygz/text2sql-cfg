"""The `text2sql` command line: ask, eval, reproduce, report, spend, grammar, catalog, index,
cache, safety and demo.

Commands that need the OpenAI SDK, the pipeline or FastAPI import them in their body, so that
`text2sql --help`, `spend` and `report` start quickly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from text2sql.catalog.cli import app as catalog_app
from text2sql.config import PRESETS, PipelineConfig, QueryMode
from text2sql.data.saas import SAAS_DB_ID
from text2sql.evals import markdown as md
from text2sql.evals.records import Dataset, Split
from text2sql.llm.cli import app as cache_app
from text2sql.observability import configure_logging
from text2sql.retrieval.cli import app as index_app

if TYPE_CHECKING:
    from text2sql.evals.reproduce import Reproduction
    from text2sql.pipeline import Answer, PipelineTrace, Request
    from text2sql.pipeline import Dataset as DatasetKind

app = typer.Typer(
    name="text2sql",
    help="Grammar-constrained text-to-SQL on the OpenAI Responses API.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
app.add_typer(catalog_app, name="catalog", help="Build schema catalogs (data/catalog/).")
app.add_typer(index_app, name="index", help="Build value and few-shot indexes (data/indexes/).")
app.add_typer(cache_app, name="cache", help="Sync the response cache with its committed shards.")
console = Console()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
SQL_PREVIEW_CHARS = 90


def _check_preset(value: str) -> str:
    if value not in PRESETS:
        raise typer.BadParameter(f"unknown preset {value!r}; known: {', '.join(sorted(PRESETS))}")
    return value


PresetOption = Annotated[
    str, typer.Option(callback=_check_preset, help="Named pipeline configuration.")
]
SetOption = Annotated[
    list[str] | None,
    typer.Option("--set", help="Override a pipeline setting, e.g. --set n_candidates=3."),
]
OfflineOption = Annotated[
    bool, typer.Option("--offline", help="Replay from the response cache; a miss is an error.")
]


def _configure(
    preset: str, sets: list[str] | None, *, with_evidence: bool = True
) -> tuple[dict[str, str], PipelineConfig]:
    """Parse `--set key=value` pairs and apply them to the preset, as `text2sql eval` would."""
    from text2sql.evals.runner import configure

    overrides: dict[str, str] = {}
    for pair in sets or []:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise typer.BadParameter(f"expected key=value, got {pair!r}", param_hint="--set")
        overrides[key.strip()] = value
    try:
        config, _ = configure(preset, overrides, with_evidence=with_evidence)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--set") from exc
    return overrides, config


def _mode(db: str, mode: QueryMode | None) -> QueryMode:
    """The pipeline's mode for `db`: the SaaS database is only served in tenant mode, and BIRD
    databases have no tenants."""
    if db == SAAS_DB_ID:
        if mode not in (None, QueryMode.TENANT):
            message = f"{SAAS_DB_ID} is only served in tenant mode"
            raise typer.BadParameter(message, param_hint="--mode")
        return QueryMode.TENANT
    if mode is QueryMode.TENANT:
        raise typer.BadParameter("BIRD databases have no tenants", param_hint="--mode")
    return mode or QueryMode.BENCHMARK


@app.callback()
def main(
    log_level: Annotated[
        LogLevel, typer.Option(help="Level of the JSON log written to stderr.")
    ] = "WARNING",
) -> None:
    """Grammar-constrained text-to-SQL on the OpenAI Responses API."""
    configure_logging(log_level)


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="The question, in natural language.")],
    *,
    db: Annotated[str, typer.Option(help=f"A BIRD db_id, or {SAAS_DB_ID} (multi-tenant).")],
    tenant: Annotated[
        int | None, typer.Option(help=f"Caller's tenant id; required for {SAAS_DB_ID}.")
    ] = None,
    user: Annotated[
        int | None, typer.Option(help="Caller's user id: also scope owned rows to this user.")
    ] = None,
    preset: PresetOption = "fast",
    mode: Annotated[
        QueryMode | None,
        typer.Option(help=f"Default: tenant for {SAAS_DB_ID}, benchmark otherwise."),
    ] = None,
    evidence: Annotated[str | None, typer.Option(help="BIRD-style external knowledge.")] = None,
    sets: SetOption = None,
    offline: OfflineOption = False,
) -> None:
    """Answer one question and show the trace: grammar, candidates, vote, final SQL, rows."""
    from text2sql.pipeline import Request
    from text2sql.safety import ScopeContext

    is_saas = db == SAAS_DB_ID
    if is_saas and tenant is None:
        raise typer.BadParameter(f"{SAAS_DB_ID} needs the caller's tenant", param_hint="--tenant")
    if not is_saas and (tenant is not None or user is not None):
        raise typer.BadParameter("BIRD databases have no tenants", param_hint="--tenant/--user")
    _, config = _configure(preset, sets)
    request = Request(
        question=question,
        evidence=evidence,
        db_id=db,
        mode=_mode(db, mode),
        scope=ScopeContext(tenant, user) if tenant is not None else None,
    )
    try:
        answer, trace = asyncio.run(_ask(request, config, offline=offline))
    except FileNotFoundError as exc:
        _missing_input(exc)
    _render_trace(answer, trace)


async def _ask(
    request: Request, config: PipelineConfig, *, offline: bool
) -> tuple[Answer, PipelineTrace]:
    from text2sql.config import get_settings
    from text2sql.llm import LLMClient, RunBudget
    from text2sql.pipeline import DatabaseResources, Pipeline

    base = get_settings()
    # The flag can switch replay on, never off: OFFLINE=true in the environment still holds.
    settings = base.model_copy(update={"offline": offline or base.offline})
    budget = RunBudget.from_settings(settings)
    dataset: DatasetKind = "saas" if request.db_id == SAAS_DB_ID else "bird"
    try:
        with DatabaseResources.load(request.db_id, dataset=dataset, mode=request.mode) as res:
            async with LLMClient(settings, budget=budget) as llm:
                pipeline = Pipeline(llm, config, settings=settings, resources=[res])
                try:
                    return await pipeline.run(request)
                finally:
                    pipeline.close()
    finally:
        console.print(budget.summary().render(), style="dim")


def _render_trace(answer: Answer, trace: PipelineTrace) -> None:
    grammars = Table("view", "chars", "API load", "fits", "built from", title="Grammars")
    for view, info in trace.grammars.items():
        grammars.add_row(
            view, f"{info.chars:,}", f"{info.api_load:.2f}", str(info.fits_api_budget),
            info.built_from,
        )  # fmt: skip
    console.print(grammars)

    candidates = Table("#", "strategy", "model", "status", "repairs", "rows", "SQL or reason",
                       title="Candidates")  # fmt: skip
    for c in trace.candidates:
        text = c.sql or c.abstain_reason or c.exec_error or c.validator_error or ""
        rows = "-" if c.row_count is None else str(c.row_count)
        candidates.add_row(
            str(c.index), c.strategy, f"{c.model} ({c.effort})", c.status, str(c.repairs), rows,
            escape(md.cell(text, max_chars=SQL_PREVIEW_CHARS)),
        )  # fmt: skip
    console.print(candidates)

    if trace.clusters:
        clusters = Table("result", "candidates", "representative", title="Result clusters")
        for cluster in trace.clusters:
            members = ", ".join(map(str, cluster.members))
            clusters.add_row(cluster.fingerprint[:12], members, str(cluster.representative))
        console.print(clusters)
    if (selection := trace.selection) is not None:
        console.print(
            f"selection: {selection.method}, candidate {selection.index}, vote share "
            f"{selection.vote_share:.2f} over {selection.n_clusters} cluster(s)"
            + (", cheap path" if trace.cheap_path_taken else "")
        )
    for event in trace.safety_events:
        console.print(f"[yellow]safety[/] {event.layer}/{event.rule}: {escape(event.detail)}")

    console.rule(f"{answer.status} (confidence {answer.confidence:.2f})")
    if answer.sql is not None:
        console.print(Syntax(answer.sql, "sql", word_wrap=True))
    if answer.explanation:
        console.print(escape(answer.explanation))
    if answer.reason:
        console.print(f"reason: {escape(answer.reason)}")
    if answer.preview is not None:
        result = Table(*map(escape, answer.preview.columns),
                       title=f"{answer.preview.row_count} row(s)")  # fmt: skip
        for values in answer.preview.rows:
            result.add_row(*(escape(str(v)) for v in values))
        console.print(result)
    console.print(
        f"model cost {md.usd(trace.cost_usd)} at list price ({md.usd(trace.billed_usd)} billed), "
        f"model latency {md.seconds(trace.model_latency_s)}, wall {md.seconds(trace.elapsed_s)}",
        style="dim",
    )


@app.command("eval")
def eval_command(
    *,
    dataset: Annotated[Dataset, typer.Option(help="Result table to evaluate.")] = "bird_minidev",
    split: Annotated[
        Split, typer.Option(help="dev (tuning), test (held out; needs --allow-test) or all.")
    ] = "dev",
    preset: PresetOption = "best",
    sets: SetOption = None,
    limit: Annotated[
        int | None, typer.Option(min=1, help="Evaluate a seeded sample of this many questions.")
    ] = None,
    no_evidence: Annotated[
        bool, typer.Option("--no-evidence", help="Withhold BIRD's evidence field.")
    ] = False,
    offline: OfflineOption = False,
    allow_test: Annotated[
        bool, typer.Option("--allow-test", help="Allow the held-out test split (once, at the end).")
    ] = False,
    concurrency: Annotated[int, typer.Option(min=1, help="Questions in flight at once.")] = 8,
) -> None:
    """Evaluate a preset on a dataset split, write reports/<run>/ and regenerate RESULTS.md."""
    from text2sql.evals.runner import HeldOutSplitError, RunAbortedError, run_eval
    from text2sql.llm import CacheMiss

    overrides, _ = _configure(preset, sets, with_evidence=not no_evidence)
    try:
        directory = asyncio.run(
            run_eval(
                dataset=dataset,
                split=split,
                preset=preset,
                overrides=overrides,
                limit=limit,
                with_evidence=not no_evidence,
                offline=offline,
                allow_test=allow_test,
                concurrency=concurrency,
            )
        )
    except HeldOutSplitError as exc:
        console.print(f"[red]{escape(str(exc))}")
        raise typer.Exit(2) from exc
    except (CacheMiss, RunAbortedError) as exc:
        console.print(f"[red]{type(exc).__name__}: {escape(str(exc))}")
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        _missing_input(exc)
    _render_report(directory)


def _missing_input(exc: FileNotFoundError) -> NoReturn:
    """Data, catalogs and indexes are built locally (`make data`, `make catalog`, `make index`);
    say which one is missing instead of printing a traceback."""
    console.print(f"[red]missing input: {escape(str(exc))}")
    console.print("build it with `make data`, `make catalog` or `make index` (see the README)")
    raise typer.Exit(1) from exc


def _render_report(directory: Path) -> None:
    from text2sql.evals.registry import RESULTS_FILE, read_report

    report = read_report(directory / RESULTS_FILE)
    run, summary = report.run, report.summary
    o = summary.overall
    table = Table("metric", "value", title=f"{run.config_name} on {run.dataset}/{run.split}")
    table.add_row("questions", f"{o.n} of {run.questions_planned}")
    table.add_row("EX (95% CI)", md.rate_ci(o.ex))
    table.add_row(f"pass@{run.n_candidates}", md.rate_ci(o.pass_at_n))
    selection = o.selection_accuracy
    table.add_row("selection accuracy", "n/a" if selection is None else md.pct(selection))
    if summary.linking is not None:
        table.add_row("linking recall (all gold columns)", md.rate_ci(summary.linking.full_recall))
    if summary.grammar_coverage is not None:
        table.add_row("gold SQL in grammar", md.rate_ci(summary.grammar_coverage.overall))
    rejections = summary.grammar_rejections
    table.add_row("grammar rejections", f"{rejections.rejections} of {rejections.calls} calls")
    if summary.abstention is not None:
        a = summary.abstention
        precision = "n/a" if a.precision is None else md.rate_ci(a.precision)
        table.add_row("abstain precision", precision)
        table.add_row("abstain recall", "n/a" if a.recall is None else md.rate_ci(a.recall))
    if run.dataset == "saas":
        table.add_row("safety violations at the database", str(summary.safety.database_violations))
    table.add_row("cost per question (list price)", md.usd(o.cost_per_question_usd))
    p50, p95 = md.seconds(o.latency_p50_s), md.seconds(o.latency_p95_s)
    table.add_row("model latency p50 / p95", f"{p50} / {p95}")
    if run.partial:
        table.add_row("[red]partial", escape(run.partial_reason or ""))
    console.print(table)
    console.print(f"report: {directory}")


@app.command()
def reproduce(
    reports: Annotated[
        list[Path] | None,
        typer.Argument(help="Report directories to replay. Default: every report."),
    ] = None,
    concurrency: Annotated[int, typer.Option(min=1, help="Questions in flight at once.")] = 8,
) -> None:
    """Replay reports offline; fail unless each comes out identical and RESULTS.md is current."""
    from text2sql.config import get_settings
    from text2sql.evals.registry import RESULTS_FILE
    from text2sql.evals.reproduce import reproduce_all, results_md_problem

    for directory in reports or []:
        if not (directory / RESULTS_FILE).is_file():
            raise typer.BadParameter(f"{directory} has no {RESULTS_FILE}", param_hint="REPORTS")
    settings = get_settings().model_copy(update={"offline": True})
    try:
        results = asyncio.run(
            reproduce_all(settings=settings, only=reports or (), concurrency=concurrency)
        )
    except FileNotFoundError as exc:
        _missing_input(exc)
    if not results:
        console.print("no reports under reports/ to reproduce")
    for result in results:
        _render_reproduction(result)
    stale = results_md_problem()
    if stale is not None:
        console.print(f"[red]{escape(stale)}")
    if stale is not None or any(r.status != "match" for r in results):
        raise typer.Exit(1)


def _render_reproduction(result: Reproduction) -> None:
    colour = "green" if result.status == "match" else "red"
    console.print(
        f"[{colour}]{result.status}[/] {result.directory.name} ({result.questions} questions)"
    )
    for problem in result.problems[:20]:
        console.print(f"  {escape(problem)}")
    if len(result.problems) > 20:
        console.print(f"  ... and {len(result.problems) - 20} more")


@app.command()
def report() -> None:
    """Regenerate RESULTS.md and the N-sweep figures from reports/."""
    from text2sql.evals.report import RESULTS_MD, regenerate_results_md

    regenerate_results_md()
    console.print(f"wrote {RESULTS_MD}")


@app.command()
def spend() -> None:
    """Total API spend from the ledger, by phase and model."""
    from text2sql.llm import spend_report

    console.print(spend_report().render(), soft_wrap=True)


@app.command()
def compare(
    reference: Annotated[Path, typer.Argument(help="Report directory of the reference run.")],
    variant: Annotated[Path, typer.Argument(help="Report directory of the variant run.")],
) -> None:
    """Paired comparison of two runs on their shared questions: EX delta, CI, McNemar, cost."""
    from text2sql.evals.metrics import compare_paired
    from text2sql.evals.registry import RESULTS_FILE, RegisteredReport, read_report

    runs: list[RegisteredReport] = []
    for directory in (reference, variant):
        if not (directory / RESULTS_FILE).is_file():
            raise typer.BadParameter(f"{directory} has no {RESULTS_FILE}")
        report = read_report(directory / RESULTS_FILE)
        runs.append(RegisteredReport(directory, report.run, report.summary))
    ref, var = runs
    try:
        result = compare_paired(ref.questions, var.questions)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    shared = {(q.db_id, q.question_id) for q in ref.questions} & {
        (q.db_id, q.question_id) for q in var.questions
    }

    def cost(entry: RegisteredReport) -> float:
        return sum(q.cost_usd for q in entry.questions if (q.db_id, q.question_id) in shared)

    table = Table("", "reference", "variant", title=f"{result.n} shared questions")
    table.add_row("run", escape(ref.directory.name), escape(var.directory.name))
    table.add_row("EX", f"{result.reference_ex:.1%}", f"{result.variant_ex:.1%}")
    table.add_row("only this side correct", str(result.reference_only), str(result.variant_only))
    table.add_row(
        "cost / question",
        f"${cost(ref) / result.n:.4f}",
        f"${cost(var) / result.n:.4f}",
    )
    console.print(table)
    console.print(
        f"delta {result.delta:+.1%} (95% CI {result.delta_ci_low:+.1%} to "
        f"{result.delta_ci_high:+.1%}), exact McNemar p = {result.mcnemar_p:.3f}"
    )


@app.command()
def grammar(
    db: Annotated[str, typer.Option(help=f"A BIRD db_id, or {SAAS_DB_ID}.")],
    show: Annotated[bool, typer.Option("--show", help="Print the Lark definition.")] = False,
    mode: Annotated[
        QueryMode | None,
        typer.Option(help=f"Default: tenant for {SAAS_DB_ID}, benchmark otherwise."),
    ] = None,
    check: Annotated[
        str | None,
        typer.Option(help="Parse this SQL with the grammar locally; exit 1 if it is rejected."),
    ] = None,
) -> None:
    """The full-schema grammar the pipeline sends for a database: size, text (--show), and
    whether a query parses under it (--check)."""
    from text2sql.grammar import GrammarRejection
    from text2sql.pipeline import full_grammar

    chosen = _mode(db, mode)
    built = full_grammar(db, dataset="saas" if db == SAAS_DB_ID else "bird", mode=chosen)
    if show:
        console.print(built.definition, markup=False, highlight=False, soft_wrap=True)
    size = built.size
    console.print(
        f"{db} ({chosen}): {size.chars:,} chars, API load {size.api_load:.2f}, "
        f"{'fits' if size.fits_api_budget else 'exceeds'} the API budget; "
        f"fingerprint {built.fingerprint[:12]}",
        style="dim" if show or check is not None else None,
    )
    if check is None:
        return
    try:
        output = built.parse(check)
    except GrammarRejection as exc:
        console.print(
            f"[bold red]rejected by the grammar:[/] {escape(exc.summary)}", highlight=False
        )
        raise typer.Exit(1) from exc
    console.print(f"[bold green]accepted[/] as {output.kind}")


@app.command()
def safety(
    db: Annotated[
        Path | None, typer.Option(help="SaaS database; default: generate it into a temp dir.")
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Report directory; default reports/safety.")
    ] = None,
) -> None:
    """Run the adversarial suite against the four safety layers (no API calls)."""
    from text2sql.evals.safety_suite import REPORT_DIR, run_safety_suite

    result = run_safety_suite(db_path=db, out_dir=out or REPORT_DIR)
    console.print(result.summary())
    raise typer.Exit(0 if result.passed else 1)


@app.command()
def demo(
    host: Annotated[
        str, typer.Option(help="Bind address; anything but loopback exposes the demo.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="TCP port.")] = 8000,
    preset: PresetOption = "baseline",
) -> None:
    """Serve the web demo of the live pipeline trace."""
    from text2sql.web import serve

    serve(host=host, port=port, preset=preset)
