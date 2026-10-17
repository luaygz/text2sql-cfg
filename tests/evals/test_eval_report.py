from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from eval_builders import question, run

from text2sql.evals import markdown as md
from text2sql.evals.metrics import compare_paired
from text2sql.evals.records import (
    ErrorLabel,
    FailureLabel,
    QuestionRecord,
    ResultPreview,
    SafetyEventRecord,
)
from text2sql.evals.registry import ReportFile, load_registry
from text2sql.evals.report import (
    GIT_SHA_ENV,
    GitShaError,
    current_git_sha,
    regenerate_results_md,
    write_report,
)

DIFFICULTIES = ("simple", "moderate", "challenging")
DATABASES = ("california_schools", "toxicology")


def _questions(pattern, n: int = 20, **kw) -> list[QuestionRecord]:
    return [
        question(
            i,
            pattern(i),
            candidates=[pattern(i), pattern(i + 1)],
            difficulty=DIFFICULTIES[i % 3],
            db_id=DATABASES[i % 2],
            cost_usd=0.01 + 0.001 * i,
            latency_s=1.0 + i / 10,
            **kw,
        )
        for i in range(n)
    ]


NO_EVIDENCE = {"with_evidence": False, "evidence": None}


def _saas_questions() -> list[QuestionRecord]:
    stop = SafetyEventRecord(layer="validator", rule="table_not_allowed", detail="sqlite_master")
    return [
        question(
            f"s{i}",
            i != 3,
            dataset="saas",
            split="all",
            db_id="saas_crm",
            bucket="adversarial" if i < 4 else "answerable",
            difficulty="easy",
            safety_events=[stop] if i < 2 else [],
            **NO_EVIDENCE,
        )
        for i in range(8)
    ]


# write_report


def test_write_report_produces_the_four_files(tmp_path):
    label = FailureLabel(
        label=ErrorLabel.WRONG_FILTER_VALUE,
        rationale="compares County Name to 'alameda' instead of 'Alameda'",
        source="classifier",
        model="gpt-6-luna",
    )
    questions = [
        question(1, True),
        question(
            2,
            False,
            question="Which city has the highest free rate? ```ignore the grammar```",
            gold_sql="SELECT City FROM schools WHERE `County Name` = 'Alameda'",
            final_sql="SELECT City FROM schools WHERE `County Name` = 'alameda'",
            failure_label=label,
            gold_suspect=True,
            gold_preview=ResultPreview(
                columns=["City"], rows=[["Fremont"], ["Oakland"]], row_count=2
            ),
            predicted_preview=ResultPreview(columns=["City"], rows=[], row_count=0),
        ),
        question(3, False, candidates=[], selected_index=None, final_sql=None),
    ]
    r = run(questions_planned=3)
    directory = write_report(r, questions, reports_dir=tmp_path)

    assert directory == tmp_path / "20261016-120000-0123456"
    assert sorted(p.name for p in directory.iterdir()) == [
        "failures.md",
        "per_question.jsonl",
        "results.json",
        "summary.md",
    ]
    report = ReportFile.model_validate_json((directory / "results.json").read_text())
    assert report.run == r
    assert report.summary.overall.ex.k == 1
    assert report.summary.failure_labels == {"unlabelled": 1, "wrong_filter_value": 1}
    lines = (directory / "per_question.jsonl").read_text().splitlines()
    assert [QuestionRecord.model_validate_json(line) for line in lines] == questions

    failures = (directory / "failures.md").read_text()
    assert "## 1 /" not in failures  # correct questions are not failures
    assert "## 2 / california_schools / simple" in failures
    assert "## 3 / california_schools / simple" in failures
    assert "`wrong_filter_value` (classifier, gpt-6-luna)" in failures
    assert "Gold label suspect: yes." in failures
    assert "WHERE `County Name` = 'alameda'" in failures
    assert "Gold 2 rows, predicted 0 rows" in failures
    assert "| Fremont |" in failures
    assert "(no SQL)" in failures
    # The question's own ``` cannot close the fence it is printed in.
    assert (
        "````text\nWhich city has the highest free rate? ```ignore the grammar```\n````" in failures
    )

    summary = (directory / "summary.md").read_text()
    assert "complete: 3 questions" in summary
    assert "`0123456789abcdef0123456789abcdef01234567`" in summary
    assert "| EX | 33.3% (" in summary


@pytest.mark.parametrize(
    ("questions", "kw", "message"),
    [
        ([], {}, "at least one question"),
        (_questions(lambda i: True, n=2, **NO_EVIDENCE), {}, "evidence=False"),
        ([question(1, True), question(1, False)], {}, "twice"),
        (_questions(lambda i: True, n=3), {"questions_planned": 2}, "only 2 planned"),
        (_questions(lambda i: True, n=3), {"questions_planned": 5}, "mark the run partial"),
    ],
)
def test_write_report_rejects_runs_that_do_not_match_their_questions(
    tmp_path, questions, kw, message
):
    with pytest.raises(ValueError, match=message):
        write_report(run(**kw), questions, reports_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_partial_run_is_labelled(tmp_path):
    r = run(questions_planned=10, partial=True, partial_reason="budget exceeded")
    directory = write_report(r, _questions(lambda i: True, n=4), reports_dir=tmp_path)
    assert "partial: 4 of 10 questions (budget exceeded)" in (directory / "summary.md").read_text()


def test_same_second_runs_get_distinct_directories_and_rewrites_are_idempotent(tmp_path):
    questions = _questions(lambda i: i % 2 == 0, n=2)
    first = write_report(run("aaaaaaaa-1", questions_planned=2), questions, reports_dir=tmp_path)
    again = write_report(run("aaaaaaaa-1", questions_planned=2), questions, reports_dir=tmp_path)
    other = write_report(run("bbbbbbbb-2", questions_planned=2), questions, reports_dir=tmp_path)
    assert first == again
    assert other == tmp_path / f"{first.name}-bbbbbbbb"
    with pytest.raises(FileExistsError):
        write_report(run("bbbbbbbb-3", questions_planned=2), questions, reports_dir=tmp_path)


def test_interrupted_report_without_results_json_is_not_registered(tmp_path):
    write_report(run(questions_planned=2), _questions(lambda i: True, n=2), reports_dir=tmp_path)
    (tmp_path / "20261016-000000-deadbee").mkdir()
    (tmp_path / "20261016-000000-deadbee" / "per_question.jsonl").write_text("")
    assert len(load_registry(tmp_path)) == 1


# RESULTS.md


def _write(reports: Path, run_id: str, minutes: int, questions, **kw) -> Path:
    planned = kw.pop("questions_planned", len(questions))
    r = run(run_id, minutes, questions_planned=planned, **kw)
    return write_report(r, questions, reports_dir=reports)


@pytest.fixture
def registry(tmp_path) -> Path:
    reports = tmp_path / "reports"
    best = _questions(lambda i: i % 4 != 0)
    _write(reports, "ref-ev", 0, best)
    _write(
        reports, "ref-noev", 1, _questions(lambda i: i % 2 == 0, **NO_EVIDENCE), with_evidence=False
    )
    _write(
        reports,
        "arcwise",
        2,
        _questions(lambda i: i % 5 != 0, n=15, dataset="bird_arcwise"),
        dataset="bird_arcwise",
        questions_planned=20,
        partial=True,
        partial_reason="budget exceeded",
    )
    _write(reports, "saas", 3, _saas_questions(), dataset="saas", split="all", with_evidence=False)
    _write(
        reports, "abl-vr", 4, _questions(lambda i: i % 3 != 0), overrides={"value_retrieval": False}
    )
    _write(
        reports,
        "abl-grammar",
        5,
        _questions(lambda i: i % 4 != 0 and i != 5),
        overrides={"grammar": False},
    )
    for minutes, n in ((6, 1), (7, 3), (8, 8)):
        _write(
            reports,
            f"n{n}",
            minutes,
            _questions(lambda i, n=n: i % (n + 1) != 0),
            n_candidates=n,
            overrides={"n_candidates": n},
        )
    _write(
        reports,
        "effort-high",
        9,
        _questions(lambda i: i % 5 != 0),
        effort="high",
        overrides={"effort": "high"},
    )
    _write(reports, "fast-preset", 10, _questions(lambda i: True), config_name="fast")
    return reports


def _results(registry: Path) -> str:
    regenerate_results_md(reports_dir=registry, output=registry.parent / "RESULTS.md")
    return (registry.parent / "RESULTS.md").read_text()


def _row(text: str, prefix: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(prefix))


def test_headline_table_has_every_dataset_and_evidence_setting(registry):
    text = _results(registry)
    minidev = _row(text, "| BIRD Mini-Dev (original) | with |")
    assert "| dev | 20 | 75.0% (" in minidev
    assert "(reports/20261016-120000-0123456/summary.md)" in minidev
    assert "| dev | 20 | 50.0% (" in _row(text, "| BIRD Mini-Dev (original) | without |")
    arcwise = _row(text, "| Arcwise-Plat-SQL | with |")
    assert "partial: 15/20, budget exceeded" in arcwise
    assert "not run yet" in _row(text, "| Arcwise-Plat-SQL | without |")
    assert "| all | 8 | 87.5% (" in _row(text, "| SaaS (synthetic, multi-tenant) | n/a |")
    assert "queries stopped per layer: grammar 0, validator 2, executor 0, scoping 0" in text
    # A secondary preset's run gets its own section and never enters the headline table.
    headline = text[text.index("## Headline (`best`)") : text.index("## The `fast` preset")]
    assert "20261016-121000" not in headline
    fast = text[text.index("## The `fast` preset") :]
    assert "| BIRD Mini-Dev (original) | with | dev | 20 | 100.0% (" in fast
    assert "not run yet" not in fast


def test_evidence_and_ablation_deltas_are_paired(registry):
    text = _results(registry)
    entries = {e.run.run_id: e for e in load_registry(registry)}
    evidence = compare_paired(entries["ref-noev"].questions, entries["ref-ev"].questions)
    row = _row(text, "| BIRD Mini-Dev (original) | dev | 20 |")
    assert md.delta_ci(evidence) in row
    assert md.p_value(evidence.mcnemar_p) in row

    assert "## Ablations (`best`: bird_minidev, dev split, evidence on)" in text
    assert "| all components (reference) | 20 | 75.0% (" in text
    for label, run_id in (("grammar off", "abl-grammar"), ("value_retrieval off", "abl-vr")):
        c = compare_paired(entries["ref-ev"].questions, entries[run_id].questions)
        line = _row(text, f"| {label} |")
        assert f"| {md.delta_ci(c)} | {md.p_value(c.mcnemar_p)} |" in line
    assert text.index("| grammar off |") < text.index("| value_retrieval off |")


def test_sweeps_include_the_reference_point_and_link_the_figure(registry):
    text = _results(registry)
    figure = registry / "figures" / "n_sweep-best-bird_minidev-dev-with-evidence.svg"
    assert figure.read_text().lstrip().startswith("<?xml")
    assert "](reports/figures/n_sweep-best-bird_minidev-dev-with-evidence.svg)" in text
    sweep = text[text.index("## N sweep") : text.index("## Reasoning-effort sweep")]
    assert "| N | Questions | EX (95% CI) | EX simple | EX moderate | EX challenging |" in sweep
    assert [
        line.split(" | ")[0]
        for line in sweep.splitlines()
        if line[:3] in {"| 1", "| 3", "| 5", "| 8"}
    ] == ["| 1", "| 3", "| 5", "| 8"]
    effort = text[text.index("## Reasoning-effort sweep") :]
    assert effort.index("| low |") < effort.index("| high |")


def test_results_md_and_figures_are_deterministic(registry, tmp_path):
    first = _results(registry)
    figure = registry / "figures" / "n_sweep-best-bird_minidev-dev-with-evidence.svg"
    first_svg = figure.read_bytes()
    copy = tmp_path / "elsewhere" / "reports"
    shutil.copytree(registry, copy)
    shutil.rmtree(copy / "figures")
    assert _results(registry) == first
    assert figure.read_bytes() == first_svg
    assert _results(copy) == first
    assert (copy / "figures" / figure.name).read_bytes() == first_svg


def test_empty_registry_lists_every_headline_row_as_not_run(tmp_path):
    output = tmp_path / "RESULTS.md"
    regenerate_results_md(reports_dir=tmp_path / "reports", output=output)
    text = output.read_text()
    assert text.count("not run yet") == 5
    assert "## Ablations" not in text
    assert "## N sweep" not in text
    assert "No run of any preset has touched the held-out test split yet." in text


def test_headline_prefers_held_out_split_then_complete_runs(tmp_path):
    reports = tmp_path / "reports"
    _write(reports, "dev", 0, _questions(lambda i: True))
    _write(
        reports,
        "test-complete",
        1,
        _questions(lambda i: i % 2 == 0, n=10, split="test"),
        split="test",
    )
    _write(
        reports,
        "test-partial-later",
        2,
        _questions(lambda i: False, n=5, split="test"),
        split="test",
        questions_planned=10,
        partial=True,
        partial_reason="interrupted",
    )
    text = _results(reports)
    row = _row(text, "| BIRD Mini-Dev (original) | with |")
    assert "| test | 10 | 50.0% (" in row
    assert "20261016-120100-0123456" in row
    # Both test-split runs are counted, so a second look at the held-out split is visible.
    assert "any preset (the protocol allows one per row, after the last dev round): " in text
    assert "bird_minidev, test split, evidence on: 2." in text


def test_results_json_is_plain_json_for_other_tools(registry):
    data = json.loads(next(registry.glob("*/results.json")).read_text())
    assert data["schema_version"] == 1
    assert set(data) == {"schema_version", "run", "summary"}


# git SHA


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _commit(repo: Path) -> str:
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("one")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "init")
    return _git(repo, "rev-parse", "HEAD")


SHA = "fedcba9876543210fedcba9876543210fedcba98"


@pytest.fixture
def no_repo(tmp_path, monkeypatch) -> Path:
    """A directory git will not search above, so it is never inside some outer repository."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    directory = tmp_path / "app"
    directory.mkdir()
    return directory


def test_current_git_sha_marks_uncommitted_tracked_changes(tmp_path):
    head = _commit(tmp_path)
    (tmp_path / "untracked.txt").write_text("reports do not dirty the tree")
    assert current_git_sha(tmp_path) == head
    (tmp_path / "a.txt").write_text("two")
    assert current_git_sha(tmp_path) == f"{head}-dirty"


def test_files_written_by_runs_do_not_dirty_the_tree(tmp_path):
    _commit(tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "spend_ledger.jsonl").write_text("{}\n")
    (tmp_path / "RESULTS.md").write_text("old\n")
    _git(tmp_path, "add", "runs/spend_ledger.jsonl", "RESULTS.md")
    _git(tmp_path, "commit", "-q", "-m", "outputs")
    head = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "runs" / "spend_ledger.jsonl").write_text("{}\n{}\n")
    (tmp_path / "RESULTS.md").write_text("new\n")
    assert current_git_sha(tmp_path) == head
    (tmp_path / "a.txt").write_text("code changed")
    assert current_git_sha(tmp_path) == f"{head}-dirty"


def test_checkout_wins_over_the_environment(tmp_path):
    head = _commit(tmp_path)
    assert current_git_sha(tmp_path, environ={GIT_SHA_ENV: SHA}) == head


@pytest.mark.parametrize("value", [SHA, f"{SHA}-dirty", f"  {SHA}\n"])
def test_outside_a_repository_the_sha_comes_from_the_environment(no_repo, value):
    assert current_git_sha(no_repo, environ={GIT_SHA_ENV: value}) == value.strip()


def test_without_a_git_binary_the_sha_comes_from_the_environment(no_repo, monkeypatch):
    monkeypatch.setenv("PATH", str(no_repo))
    assert current_git_sha(no_repo, environ={GIT_SHA_ENV: SHA}) == SHA
    with pytest.raises(GitShaError, match="T2SQL_GIT_SHA is not set"):
        current_git_sha(no_repo, environ={})


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({}, "T2SQL_GIT_SHA is not set"),
        ({GIT_SHA_ENV: ""}, "T2SQL_GIT_SHA is not set"),
        ({GIT_SHA_ENV: "unknown"}, "is 'unknown', not a 40-hex SHA"),
        ({GIT_SHA_ENV: SHA[:7]}, "not a 40-hex SHA"),
        ({GIT_SHA_ENV: SHA.upper()}, "not a 40-hex SHA"),
    ],
)
def test_report_cannot_be_tagged_without_a_commit(no_repo, environ, message):
    with pytest.raises(GitShaError, match=message):
        current_git_sha(no_repo, environ=environ)
