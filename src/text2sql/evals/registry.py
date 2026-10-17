"""The report registry: every `reports/<run>/results.json`, read back for RESULTS.md.

The directory listing is the registry. Each report describes itself (run record, summary,
per-question records), so deleting a directory removes its rows and nothing else needs
updating. A run is classified by its `overrides` relative to its preset; see `RunRecord`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from text2sql.evals.metrics import RunSummary
from text2sql.evals.records import Dataset, JsonScalar, QuestionRecord, RunRecord

RunKind = Literal["reference", "n_sweep", "effort_sweep", "ablation"]
type Context = tuple[Dataset, str, bool]
"""(dataset, split, with_evidence): runs are only compared within one context."""

RESULTS_FILE = "results.json"
QUESTIONS_FILE = "per_question.jsonl"


class ReportFile(BaseModel):
    """Contents of results.json."""

    schema_version: Literal[1] = 1
    run: RunRecord
    summary: RunSummary


def read_report(path: Path) -> ReportFile:
    return ReportFile.model_validate_json(path.read_text(encoding="utf-8"))


def short_sha(git_sha: str) -> str:
    return git_sha[:7] + ("-dirty" if git_sha.endswith("-dirty") else "")


def report_dir_name(run: RunRecord) -> str:
    return f"{run.timestamp.astimezone(UTC):%Y%m%d-%H%M%S}-{short_sha(run.git_sha)}"


def override_label(overrides: dict[str, JsonScalar]) -> str:
    """`grammar off, selector=majority`; `none` for the preset itself."""
    if not overrides:
        return "none"
    return ", ".join(_override(k, v) for k, v in sorted(overrides.items()))


def _override(key: str, value: JsonScalar) -> str:
    if isinstance(value, bool):
        return f"{key} {'on' if value else 'off'}"
    return f"{key}={value}"


@dataclass(frozen=True)
class RegisteredReport:
    directory: Path
    run: RunRecord
    summary: RunSummary

    @cached_property
    def questions(self) -> list[QuestionRecord]:
        text = (self.directory / QUESTIONS_FILE).read_text(encoding="utf-8")
        return [QuestionRecord.model_validate_json(line) for line in text.splitlines() if line]

    @property
    def kind(self) -> RunKind:
        keys = set(self.run.overrides)
        if not keys:
            return "reference"
        if keys == {"n_candidates"}:
            return "n_sweep"
        if keys == {"effort"}:
            return "effort_sweep"
        return "ablation"

    @property
    def context(self) -> Context:
        return (self.run.dataset, self.run.split, self.run.with_evidence)


def load_registry(reports_dir: Path) -> list[RegisteredReport]:
    """Every report directory with a results.json under `reports_dir`, oldest first."""
    entries = []
    for path in reports_dir.glob(f"*/{RESULTS_FILE}"):
        report = read_report(path)
        entries.append(RegisteredReport(path.parent, report.run, report.summary))
    return sorted(entries, key=lambda e: (e.run.timestamp, e.run.run_id))


def preferred(entries: Sequence[RegisteredReport]) -> RegisteredReport:
    """Complete runs over partial ones, then the latest."""
    if not entries:
        raise ValueError("no reports to choose from")
    return max(entries, key=lambda e: (not e.run.partial, e.run.timestamp, e.run.run_id))
