"""Replay committed reports from the response cache and check they come out identical.

`text2sql reproduce` (`make eval-offline`) re-runs every report under reports/ offline: the
stored pipeline configuration, on exactly the questions the report scored, with every model
response served from the committed cache. A report reproduces when each per-question record
and the run summary are identical to the stored ones. A cache miss means today's code sends a
request the recorded run never made (a prompt, grammar or configuration change), so the
report's numbers can no longer be regenerated from the cache and must be re-run or retired.
Last, RESULTS.md must be exactly what the reports render to.

Failure labels are replayed only where the recorded run produced them; labels a reviewer
assigned by hand (source `human`) are carried over, since no replay can regenerate them.
Replaying a test-split report is not a new test run: it recomputes recorded responses, so it
is not added to runs/held_out_runs.jsonl.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from text2sql.config import PipelineConfig, Settings
from text2sql.evals.datasets import EvalItem, load_items
from text2sql.evals.metrics import summarize_run
from text2sql.evals.records import Dataset, QuestionRecord, Split
from text2sql.evals.registry import RESULTS_FILE, RegisteredReport, load_registry, read_report
from text2sql.evals.report import HEADLINE_PRESET, REPORTS_DIR, RESULTS_MD, SECONDARY_PRESETS
from text2sql.evals.results_md import render_results_md
from text2sql.evals.runner import PipelineSystem, RunOutcome, RunPlan, SystemFactory, execute_plan
from text2sql.llm import CacheMiss, LLMClient, RunBudget
from text2sql.observability import start_run

Status = Literal["match", "mismatch", "cache_miss"]
type QuestionKey = tuple[str, str]


class _Keyed(Protocol):
    @property
    def db_id(self) -> str: ...
    @property
    def question_id(self) -> str: ...


@dataclass(frozen=True)
class Reproduction:
    directory: Path
    status: Status
    questions: int
    problems: tuple[str, ...] = ()


async def reproduce_report(
    entry: RegisteredReport,
    *,
    settings: Settings,
    open_system: SystemFactory = PipelineSystem.open,
    items_for: Callable[[Dataset, Split], Sequence[EvalItem]] = load_items,
    concurrency: int = 8,
) -> Reproduction:
    """Replay one report offline and compare it with what it recorded."""
    if not settings.offline:
        raise ValueError("reproduce replays from the response cache; pass offline settings")
    recorded = {_key(q): q for q in entry.questions}
    items = [i for i in items_for(entry.run.dataset, entry.run.split) if _key(i) in recorded]
    if gone := sorted(qid for _, qid in recorded.keys() - {_key(i) for i in items}):
        problem = f"questions no longer in the dataset: {', '.join(gone)}"
        return Reproduction(entry.directory, "mismatch", len(recorded), (problem,))
    plan = RunPlan(
        dataset=entry.run.dataset,
        split=entry.run.split,
        preset=entry.run.config_name,
        config=PipelineConfig.model_validate(entry.run.config["pipeline"]),
        overrides=entry.run.overrides,
        with_evidence=entry.run.with_evidence,
        items=items,
        concurrency=concurrency,
    )

    def machine_labelled(q: QuestionRecord) -> bool:
        label = recorded[_key(q)].failure_label
        return label is not None and label.source != "human"

    budget = RunBudget.from_settings(settings, run_id=start_run())
    try:
        async with LLMClient(settings, budget=budget) as llm:
            outcome = await execute_plan(
                plan, llm=llm, settings=settings, open_system=open_system, label=machine_labelled
            )
    except CacheMiss as exc:
        return Reproduction(entry.directory, "cache_miss", len(recorded), (str(exc),))
    replayed = _with_human_labels(outcome, recorded)
    problems = compare_questions(entry.questions, replayed)
    if not problems and summarize_run(replayed) != entry.summary:
        problems = [f"summary differs: {', '.join(_summary_fields(entry, replayed))}"]
    status: Status = "mismatch" if problems else "match"
    return Reproduction(entry.directory, status, len(recorded), tuple(problems))


def _key(record: _Keyed) -> QuestionKey:
    return (record.db_id, record.question_id)


def _with_human_labels(
    outcome: RunOutcome, recorded: dict[QuestionKey, QuestionRecord]
) -> list[QuestionRecord]:
    out = []
    for replayed in outcome.questions:
        label = recorded[_key(replayed)].failure_label
        if not replayed.correct and label is not None and label.source == "human":
            out.append(replayed.model_copy(update={"failure_label": label}))
        else:
            out.append(replayed)
    return out


def compare_questions(
    recorded: Sequence[QuestionRecord], replayed: Sequence[QuestionRecord]
) -> list[str]:
    """One line per question whose replayed record differs, naming the fields that changed."""
    old = {_key(q): q.model_dump(mode="json") for q in recorded}
    new = {_key(q): q.model_dump(mode="json") for q in replayed}
    problems = []
    for key in sorted(old.keys() | new.keys()):
        where = f"{key[0]}/{key[1]}"
        if key not in new or key not in old:
            problems.append(f"{where}: {'not replayed' if key not in new else 'not recorded'}")
            continue
        a, b = old[key], new[key]
        fields = sorted(f for f in a.keys() | b.keys() if a.get(f) != b.get(f))
        if fields:
            change = f" (correct {a['correct']} -> {b['correct']})" if "correct" in fields else ""
            problems.append(f"{where}: {', '.join(fields)} differ{change}")
    return problems


def _summary_fields(entry: RegisteredReport, replayed: Sequence[QuestionRecord]) -> list[str]:
    a = entry.summary.model_dump(mode="json")
    b = summarize_run(replayed).model_dump(mode="json")
    return sorted(f for f in a.keys() | b.keys() if a.get(f) != b.get(f))


def results_md_problem(
    *, reports_dir: Path = REPORTS_DIR, results_md: Path = RESULTS_MD
) -> str | None:
    """Why RESULTS.md does not match what the reports render to, or None if it does."""
    if not results_md.exists():
        return f"{results_md.name} is missing; run `text2sql report`"
    expected = render_results_md(
        load_registry(reports_dir),
        preset=HEADLINE_PRESET,
        secondary=SECONDARY_PRESETS,
        output=results_md,
        figures_dir=reports_dir / "figures",
    )
    if expected != results_md.read_text(encoding="utf-8"):
        return f"{results_md.name} is out of date with {reports_dir.name}/; run `text2sql report`"
    return None


async def reproduce_all(
    *,
    settings: Settings,
    reports_dir: Path = REPORTS_DIR,
    only: Sequence[Path] = (),
    concurrency: int = 8,
) -> list[Reproduction]:
    """Replay every report under `reports_dir`, oldest first, or only the directories given."""
    if only:
        entries = []
        for directory in only:
            report = read_report(directory / RESULTS_FILE)
            entries.append(RegisteredReport(directory, report.run, report.summary))
    else:
        entries = load_registry(reports_dir)
    return [await reproduce_report(e, settings=settings, concurrency=concurrency) for e in entries]
