"""Write the adversarial suite report: JSON, a Markdown summary and the stops-per-layer chart.

The SVG is reproducible for the same counts and matplotlib version (fixed hash salt, no date).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from text2sql.config import REPO_ROOT
from text2sql.evals.safety_suite.results import (
    EXECUTED,
    CaseResult,
    LayerOutcome,
    SafetySuiteReport,
)
from text2sql.safety.leaks import LAYER_ORDER

REPORT_DIR: Final = REPO_ROOT / "reports" / "safety"
JSON_FILE: Final = "safety_suite.json"
MARKDOWN_FILE: Final = "safety_suite.md"
CHART_FILE: Final = "stops_per_layer.svg"
MAX_SQL_CHARS: Final = 90

_MARK: Final = {"stopped": "stop", "passed": "pass", "executed": "ran", "leaked": "LEAK"}


def write_safety_report(report: SafetySuiteReport, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    chart = out_dir / CHART_FILE
    plot_stops_per_layer(report, chart)
    markdown = out_dir / MARKDOWN_FILE
    markdown.write_text(render_markdown(report), encoding="utf-8")
    data = out_dir / JSON_FILE
    data.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return [data, markdown, chart]


def plot_stops_per_layer(report: SafetySuiteReport, path: Path) -> None:
    import matplotlib as mpl
    from matplotlib.figure import Figure

    labels = [*LAYER_ORDER, "ran, no leak"]
    first = [report.stops_by_layer[key] for key in (*LAYER_ORDER, EXECUTED)]
    alone = [report.isolation_by_layer[layer].get("stopped", 0) for layer in LAYER_ORDER]
    positions = list(range(len(labels)))
    width = 0.38
    with mpl.rc_context({"svg.hashsalt": "text2sql-safety", "svg.fonttype": "path"}):
        fig = Figure(figsize=(8, 4), layout="constrained")
        axes = fig.add_subplot(1, 1, 1)
        bars = axes.bar(
            [p - width / 2 for p in positions], first, width, color="black", label="full guard"
        )
        axes.bar_label(bars, fontsize="small")
        bars = axes.bar(
            [p + width / 2 for p in positions[: len(alone)]],
            alone,
            width,
            color="grey",
            label="layer alone",
        )
        axes.bar_label(bars, fontsize="small")
        axes.set_xticks(positions, labels)
        axes.set_ylabel("adversarial cases")
        axes.legend(fontsize="small")
        axes.grid(axis="y", alpha=0.3)
        axes.set_title(
            f"Where {report.n_cases} attacks stop: first layer under the full guard vs. each"
            f" layer on its own\n{report.violations_at_db} violations reached the database",
            fontsize="medium",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, format="svg", metadata={"Date": None})


def render_markdown(report: SafetySuiteReport) -> str:
    lines = [
        "# Adversarial safety suite",
        "",
        f"Generated {report.created_at:%Y-%m-%d %H:%M} UTC at `{report.git_sha}` by"
        " `text2sql safety`; SaaS database sha256 `"
        f"{report.db_sha256[:16]}`, cases sha256 `{report.cases_sha256[:16]}`.",
        "",
        f"Result: **{'pass' if report.passed else 'FAIL'}** on {report.n_cases} SQL-level cases.",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| Violations reaching layer 3 | {report.violations_at_executor} |",
        f"| Violations reaching the database | {report.violations_at_db} |",
        f"| Responsible layer that failed on its own | {report.isolation_failures} |",
        f"| Stops without exactly one logged safety event | {report.unlogged_stops} |",
        f"| Database file unchanged | {'yes' if report.db_unchanged else 'no'} |",
        "",
        f"![Stops per layer]({CHART_FILE})",
        "",
        "## Where the full guard stopped each case",
        "",
        "Layers run in request order: grammar, validator, scoping, executor.",
        "",
        "| Layer | Cases | Rules |",
        "| --- | --- | --- |",
    ]
    for key, count in report.stops_by_layer.items():
        rules = report.rules_by_layer.get(key, {})
        listed = ", ".join(f"{rule} {n}" for rule, n in rules.items()) or "-"
        label = "ran to completion, no leak" if key == EXECUTED else key
        lines.append(f"| {label} | {count} | {listed} |")
    lines += [
        "",
        "## Each layer on its own",
        "",
        "Every case also runs through each layer alone, with the layers before it switched off."
        " A case lists the layers responsible for it; each of those must stop it (for `contain`"
        " cases: stop it or run it without a leak).",
        "",
        "| Layer | Responsible for | Held | Stopped (all cases) | Leaked (all cases) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for layer in LAYER_ORDER:
        resp = report.responsible_by_layer[layer]
        counts = report.isolation_by_layer[layer]
        lines.append(
            f"| {layer} | {resp.cases} | {resp.held} | {counts.get('stopped', 0)}"
            f" | {counts.get('leaked', 0)} |"
        )
    lines += [
        "",
        "Leaks in this table come from layers that are not responsible for that case (layer 3"
        " alone cannot filter rows by tenant); they show why the other layers exist.",
        "",
        "## Cases by category",
        "",
        "| Category | Cases |",
        "| --- | --- |",
        *(f"| {name} | {n} |" for name, n in sorted(report.cases_by_category.items())),
        "",
        "## All cases",
        "",
        "Isolation columns: `stop`, `pass`, `ran` (no leak), `LEAK`; `*` marks a responsible"
        " layer.",
        "",
        "| Case | Category | Expect | Full guard | Grammar | Validator | Scoping | Executor |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *(_case_row(r) for r in report.results),
        "",
    ]
    return "\n".join(lines)


def _case_row(r: CaseResult) -> str:
    guard = f"{r.guard.stopped_at}: {r.guard.rule}" if r.guard.stopped_at else r.guard.detail
    if r.guard.leaks:
        guard += " LEAK"
    cells = [_isolation_cell(r.isolation[layer], layer in r.layers) for layer in LAYER_ORDER]
    return f"| `{r.id}` | {r.category} | {r.expect} | {guard} | {' | '.join(cells)} |"


def _isolation_cell(outcome: LayerOutcome, responsible: bool) -> str:
    return _MARK[outcome.outcome] + ("*" if responsible else "")
