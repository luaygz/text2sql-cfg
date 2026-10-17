"""summary.md and failures.md for one run's report directory."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC

from text2sql.evals import markdown as md
from text2sql.evals.metrics import GroupSummary, RunSummary
from text2sql.evals.records import SAFETY_LAYERS, QuestionRecord, ResultPreview, RunRecord
from text2sql.evals.registry import override_label

PREVIEW_ROWS = 5
_GROUP_HEADER = ["n", "EX (95% CI)", "pass@N", "Cost / q"]


def run_status(run: RunRecord, answered: int) -> str:
    if run.partial:
        return f"partial: {answered} of {run.questions_planned} questions ({run.partial_reason})"
    return f"complete: {answered} questions"


def evidence_setting(run: RunRecord) -> str:
    if run.dataset == "saas":
        return "n/a"
    return "on" if run.with_evidence else "off"


def _group_table(title: str, groups: dict[str, GroupSummary]) -> list[str]:
    rows = [
        [
            md.cell(name),
            str(g.n),
            md.rate_ci(g.ex),
            md.pct(g.pass_at_n.value),
            md.usd(g.cost_per_question_usd),
        ]
        for name, g in groups.items()
    ]
    return md.table([title, *_GROUP_HEADER], rows)


def render_summary(run: RunRecord, summary: RunSummary) -> str:
    spend = run.spend
    header = [
        ["Config", f"`{md.cell(run.config_name)}` (overrides: {override_label(run.overrides)})"],
        ["Dataset", f"{run.dataset} / {run.split}, evidence {evidence_setting(run)}"],
        ["Git SHA", f"`{run.git_sha}`"],
        ["Started", f"{run.timestamp.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC"],
        ["Status", md.cell(run_status(run, summary.overall.n))],
        ["Candidates / effort", f"{run.n_candidates} / {run.effort}"],
        [
            "Spend",
            f"{md.usd(spend.billed_usd)} billed, {md.usd(spend.priced_usd)} at list price, "
            f"budget {md.usd(spend.budget_usd)}; {spend.calls} calls, "
            f"{spend.cache_hits} cache hits",
        ],
    ]
    s = summary.safety
    lines = [
        f"# Run {md.cell(run.run_id)}",
        "",
        *md.table(["Field", "Value"], header),
        "",
        "## Metrics",
        "",
        "Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.",
        "",
        *md.table(["Metric", "Value"], _metric_rows(run, summary)),
        "",
        "## By difficulty",
        "",
        *_group_table("Difficulty", summary.by_difficulty),
        "",
        "## By database",
        "",
        *_group_table("Database", summary.by_db),
        "",
    ]
    if summary.by_bucket:
        lines += ["## By SaaS bucket", "", *_group_table("Bucket", summary.by_bucket), ""]
    lines += [
        "## Safety",
        "",
        f"Adversarial questions: {s.adversarial_questions}. "
        f"Questions where an unsafe effect reached the database: {s.database_violations}.",
        "",
        *md.table(
            ["Layer", "Queries stopped", "Questions affected"],
            [
                [layer, str(s.events_by_layer[layer]), str(s.questions_stopped_by_layer[layer])]
                for layer in SAFETY_LAYERS
            ],
        ),
        "",
        "## Failure taxonomy",
        "",
        *md.table(
            ["Label", "Failures"], [[md.cell(k), str(v)] for k, v in summary.failure_labels.items()]
        ),
    ]
    return "\n".join(lines) + "\n"


def _metric_rows(run: RunRecord, summary: RunSummary) -> list[list[str]]:
    o = summary.overall
    ex = o.ex
    selection = o.selection_accuracy
    rows = [
        [
            "EX",
            f"{md.rate_ci(ex)} [{md.pct(ex.wilson_low)}-{md.pct(ex.wilson_high)}], {ex.k}/{ex.n}",
        ],
        [f"Oracle pass@{run.n_candidates}", md.rate_ci(o.pass_at_n)],
        ["Selection accuracy (EX / pass@N)", md.pct(selection) if selection is not None else "n/a"],
        [
            "Cost / question",
            f"{md.usd(o.cost_per_question_usd)} (total {md.usd(summary.cost_total_usd)})",
        ],
        ["Latency p50 / p95", f"{md.seconds(o.latency_p50_s)} / {md.seconds(o.latency_p95_s)}"],
    ]
    r = summary.grammar_rejections
    rejections = (
        "no grammar calls"
        if r.rate is None
        else f"{md.pct(r.rate)} ({r.rejections} of {r.calls} calls)"
    )
    rows.append(["Grammar rejection rate", rejections])
    if summary.grammar_coverage:
        cov = summary.grammar_coverage.overall
        rows.append(["Grammar coverage of gold SQL", f"{md.rate_ci(cov)}, {cov.k}/{cov.n}"])
    if summary.linking:
        link = summary.linking
        rows.append(
            [
                "Linking recall (all gold columns linked)",
                f"{md.rate_ci(link.full_recall)}; mean column recall "
                f"{md.pct(link.mean_column_recall)} over {link.n} questions",
            ]
        )
    if summary.abstention:
        a = summary.abstention
        precision = md.rate_ci(a.precision) if a.precision else "n/a"
        recall = md.rate_ci(a.recall) if a.recall else "n/a"
        rows.append(["Abstain precision / recall", f"{precision} / {recall}"])
    if summary.rves is not None:
        rows.append(["R-VES", f"{summary.rves:.2f}"])
    rows.append(["Gold-suspect failures", f"{summary.gold_suspect_failures} of {summary.failures}"])
    return rows


def render_failures(run: RunRecord, questions: Sequence[QuestionRecord]) -> str:
    failures = [q for q in questions if not q.correct]
    lines = [
        f"# Failures: {md.cell(run.config_name)} on {run.dataset} / {run.split}",
        "",
        f"{len(failures)} of {len(questions)} questions failed. Evidence "
        f"{evidence_setting(run)}, git `{run.git_sha}`, "
        f"{md.cell(run_status(run, len(questions)))}.",
    ]
    for q in failures:
        lines += ["", *_failure(q)]
    return "\n".join(lines) + "\n"


def _label_line(q: QuestionRecord) -> str:
    label = q.failure_label
    if label is None:
        return "Label: unlabelled"
    by = label.source + (f", {md.cell(label.model)}" if label.model else "")
    return f"Label: `{label.label.value}` ({by}): {md.cell(label.rationale, max_chars=400)}"


def _failure(q: QuestionRecord) -> list[str]:
    lines = [
        f"## {md.cell(q.question_id)} / {md.cell(q.db_id)} / {md.cell(q.difficulty or 'unknown')}",
        "",
        _label_line(q),
        "",
    ]
    if q.gold_suspect:
        lines += ["Gold label suspect: yes.", ""]
    lines += ["Question:", "", *md.fence(q.question, "text"), ""]
    if q.evidence:
        lines += ["Evidence:", "", *md.fence(q.evidence, "text"), ""]
    lines += ["Gold SQL:", "", *md.fence(q.gold_sql or "(none: should abstain)", "sql"), ""]
    predicted = q.final_sql or ("(abstained)" if q.abstained else "(no SQL)")
    lines += ["Predicted SQL:", "", *md.fence(predicted, "sql")]
    errors = q.candidate_errors()
    if errors:
        lines += ["", "Errors:", "", *(f"- {md.cell(e, max_chars=300)}" for e in errors)]
    diff = _result_diff(q.gold_preview, q.predicted_preview)
    if diff:
        lines += ["", *diff]
    return lines


def _preview_table(preview: ResultPreview) -> list[str]:
    header = [md.cell(c, max_chars=40) for c in preview.columns] or ["(no columns)"]
    rows = [[md.cell(v, max_chars=40) for v in row] for row in preview.rows[:PREVIEW_ROWS]]
    return md.table(header, rows)


def _result_diff(gold: ResultPreview | None, predicted: ResultPreview | None) -> list[str]:
    if gold is None and predicted is None:
        return []
    lines = ["Result diff:"]
    if gold is not None and predicted is not None:
        gold_rows = {tuple(r) for r in gold.rows[:PREVIEW_ROWS]}
        pred_rows = {tuple(r) for r in predicted.rows[:PREVIEW_ROWS]}
        lines += [
            "",
            f"Gold {gold.row_count} rows, predicted {predicted.row_count} rows. Within the "
            f"previews: {len(gold_rows - pred_rows)} rows only in gold, "
            f"{len(pred_rows - gold_rows)} only in predicted.",
        ]
    for name, preview in (("Gold", gold), ("Predicted", predicted)):
        if preview is not None:
            shown = min(PREVIEW_ROWS, len(preview.rows))
            lines += [
                "",
                f"{name} (first {shown} of {preview.row_count} rows):",
                "",
                *_preview_table(preview),
            ]
    return lines
