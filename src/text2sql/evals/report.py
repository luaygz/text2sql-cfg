"""Write a run's report directory and regenerate the root RESULTS.md.

`write_report` turns one run into `reports/<YYYYmmdd-HHMMSS>-<shortsha>/` holding results.json,
summary.md, per_question.jsonl and failures.md. `regenerate_results_md` rebuilds RESULTS.md and
`reports/figures/` from every report directory (see `registry`). The runner calls both, in
that order, at the end of every run.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from text2sql.config import REPO_ROOT
from text2sql.evals.metrics import summarize_run
from text2sql.evals.records import QuestionRecord, RunRecord
from text2sql.evals.registry import (
    QUESTIONS_FILE,
    RESULTS_FILE,
    ReportFile,
    load_registry,
    read_report,
    report_dir_name,
)
from text2sql.evals.results_md import render_results_md
from text2sql.evals.run_markdown import render_failures, render_summary

REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_MD = REPO_ROOT / "RESULTS.md"
HEADLINE_PRESET = "best"
"""Preset whose runs fill the RESULTS.md headline: its reference runs, ablations and sweeps."""
SECONDARY_PRESETS = ("fast", "baseline")
"""Presets with their own RESULTS.md sections, for the cost and latency of each preset."""
GIT_SHA_ENV = "T2SQL_GIT_SHA"
"""Commit to tag reports with where there is no git checkout (the Docker image sets it)."""
_GIT_SHA = re.compile(r"[0-9a-f]{40}(-dirty)?")
RUN_OUTPUTS = ("runs/spend_ledger.jsonl", "runs/held_out_runs.jsonl", "RESULTS.md", "reports")
"""Tracked paths that runs themselves write; changes there say nothing about the code."""


class GitShaError(RuntimeError):
    """Neither a git checkout nor `T2SQL_GIT_SHA` says which commit produced a run."""


def current_git_sha(repo: Path = REPO_ROOT, *, environ: Mapping[str, str] = os.environ) -> str:
    """HEAD, suffixed `-dirty` when tracked files outside `RUN_OUTPUTS` have uncommitted changes.

    Untracked files and the files runs write (the spend ledger, reports, RESULTS.md) are ignored,
    so recording a run does not itself dirty the tree. Without a git binary or a repository (the
    Docker image), the commit comes from `T2SQL_GIT_SHA`, which must be a full 40-hex SHA with an
    optional `-dirty` suffix; a checkout always wins over it.
    """

    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    try:
        sha = git("rev-parse", "HEAD")
        excluded = [f":(exclude){path}" for path in RUN_OUTPUTS]
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", *excluded)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        fallback = environ.get(GIT_SHA_ENV, "").strip()
        if _GIT_SHA.fullmatch(fallback):
            return fallback
        why = e.stderr.strip() if isinstance(e, subprocess.CalledProcessError) else str(e)
        problem = f"is {fallback!r}, not a 40-hex SHA" if fallback else "is not set"
        raise GitShaError(
            f"cannot tag the report: git failed in {repo} ({why}) and {GIT_SHA_ENV} {problem}"
        ) from e
    return f"{sha}-dirty" if dirty else sha


def write_report(
    run: RunRecord, questions: Sequence[QuestionRecord], *, reports_dir: Path = REPORTS_DIR
) -> Path:
    """Write one run's report directory and return its path.

    results.json goes last: a directory without it (an interrupted write) is invisible to the
    registry instead of being read half-finished.
    """
    _check_run(run, questions)
    summary = summarize_run(questions)
    directory = _claim_directory(reports_dir, run)
    (directory / QUESTIONS_FILE).write_text(
        "".join(q.model_dump_json() + "\n" for q in questions), encoding="utf-8"
    )
    (directory / "summary.md").write_text(render_summary(run, summary), encoding="utf-8")
    (directory / "failures.md").write_text(render_failures(run, questions), encoding="utf-8")
    report = ReportFile(run=run, summary=summary)
    (directory / RESULTS_FILE).write_text(report.model_dump_json(indent=2) + "\n", "utf-8")
    return directory


def _check_run(run: RunRecord, questions: Sequence[QuestionRecord]) -> None:
    if not questions:
        raise ValueError("a report needs at least one question")
    expected = (run.dataset, run.split, run.with_evidence)
    for q in questions:
        if (q.dataset, q.split, q.with_evidence) != expected:
            raise ValueError(
                f"question {q.question_id} is {q.dataset}/{q.split}/evidence={q.with_evidence}, "
                f"but the run is {run.dataset}/{run.split}/evidence={run.with_evidence}"
            )
    if len({(q.db_id, q.question_id) for q in questions}) != len(questions):
        raise ValueError("a question appears twice in the run")
    if len(questions) > run.questions_planned:
        raise ValueError(f"{len(questions)} questions but only {run.questions_planned} planned")
    if len(questions) < run.questions_planned and not run.partial:
        raise ValueError(
            f"{len(questions)} of {run.questions_planned} planned questions: mark the run partial"
        )


def _claim_directory(reports_dir: Path, run: RunRecord) -> Path:
    """`<timestamp>-<sha>`, or `<timestamp>-<sha>-<run_id>` if another run took that second."""
    base = reports_dir / report_dir_name(run)
    for directory in (base, base.with_name(f"{base.name}-{run.run_id[:8]}")):
        existing = directory / RESULTS_FILE
        if not existing.exists() or read_report(existing).run.run_id == run.run_id:
            directory.mkdir(parents=True, exist_ok=True)
            return directory
    raise FileExistsError(f"{base} and its run-id variant belong to other runs")


def regenerate_results_md(
    *,
    reports_dir: Path = REPORTS_DIR,
    output: Path = RESULTS_MD,
    preset: str = HEADLINE_PRESET,
    secondary: Sequence[str] = SECONDARY_PRESETS,
) -> None:
    """Rebuild RESULTS.md and the N-sweep figures from every report of `preset` and `secondary`.

    The output depends only on the reports' contents: the same reports give the same bytes.
    """
    text = render_results_md(
        load_registry(reports_dir),
        preset=preset,
        output=output,
        figures_dir=reports_dir / "figures",
        secondary=secondary,
    )
    output.write_text(text, encoding="utf-8")
