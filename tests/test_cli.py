"""The `text2sql` CLI: argument checks that must fail before any model call, `spend`, replay
mode, and the local grammar check."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest
from typer.testing import CliRunner

import text2sql.evals.runner
import text2sql.llm
import text2sql.pipeline
from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.cli import app
from text2sql.config import QueryMode, Settings, get_settings
from text2sql.grammar import SqlGrammar, build_grammar
from text2sql.llm import RunBudget
from text2sql.llm.budget import LedgerEntry, SpendLedger
from text2sql.pipeline import Dataset, grammar_options

runner = CliRunner()


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("LEDGER_PATH", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def entry(phase: str, model: str, cost: float) -> LedgerEntry:
    return LedgerEntry(
        run_id="r", phase=phase, purpose="p", model=model, service_tier="flex",
        input_tokens=1000, cached_tokens=0, cache_write_tokens=0, output_tokens=100,
        reasoning_tokens=50, cost_usd=cost, latency_s=1.0, request_hash="h",
    )  # fmt: skip


@pytest.mark.parametrize("split", ["test", "all"])
def test_eval_refuses_held_out_questions_without_allow_test(split: str) -> None:
    result = runner.invoke(app, ["eval", "--split", split, "--preset", "baseline"])
    assert result.exit_code == 2
    assert "allow-test" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--set", "no_such_setting=1"], "unknown pipeline setting"),
        (["--set", "n_candidates=zero"], "n_candidates"),
        (["--set", "use_evidence=false"], "with_evidence"),
        (["--set", "missing-equals"], "key=value"),
        (["--preset", "nope"], "unknown preset"),
    ],
)
def test_eval_rejects_bad_configuration(args: list[str], message: str) -> None:
    result = runner.invoke(app, ["eval", *args])
    assert result.exit_code == 2
    assert message in " ".join(result.output.split())


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--db", "saas_crm"], "tenant"),
        (["--db", "california_schools", "--tenant", "1"], "no tenants"),
        (["--db", "california_schools", "--mode", "tenant"], "no tenants"),
        (["--db", "saas_crm", "--tenant", "1", "--mode", "benchmark"], "tenant mode"),
    ],
)
def test_ask_checks_scope_and_mode_before_running(args: list[str], message: str) -> None:
    result = runner.invoke(app, ["ask", "How many deals?", *args])
    assert result.exit_code == 2
    assert message in " ".join(result.output.split())


def test_reproduce_rejects_a_directory_without_a_report(tmp_path: Path) -> None:
    result = runner.invoke(app, ["reproduce", str(tmp_path)])
    assert result.exit_code == 2
    assert "results.json" in result.output


def test_spend_totals_the_ledger_by_phase_and_model(ledger: Path) -> None:
    book = SpendLedger(ledger)
    book.append(entry("runner", "gpt-6.1-sol", 0.25))
    book.append(entry("runner", "gpt-6.1-sol", 0.5))
    book.append(entry("catalog", "gpt-6-luna", 0.125))
    result = runner.invoke(app, ["spend"])
    assert result.exit_code == 0
    rows = {line.split()[0]: line.split() for line in result.output.splitlines() if line}
    assert rows["runner"][1:3] == ["gpt-6.1-sol", "2"]
    assert rows["runner"][-1] == "0.7500"
    assert rows["total"][-1] == "0.8750"


class ClientOpenedError(Exception):
    """Raised by the stand-in LLM client with the settings the command handed it."""

    def __init__(self, settings: Settings) -> None:
        super().__init__("stand-in LLM client")
        self.settings = settings


def stand_in_client(settings: Settings, *, budget: RunBudget) -> NoReturn:
    raise ClientOpenedError(settings)


@pytest.mark.parametrize(
    "args",
    [
        ["ask", "How many schools?", "--db", "california_schools"],
        ["eval", "--preset", "baseline", "--limit", "1"],
    ],
)
def test_offline_in_the_environment_holds_without_the_flag(
    args: list[str], ledger: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OFFLINE", "true")
    get_settings.cache_clear()
    # Stop each command at the point it opens the LLM client, before any data is needed.
    monkeypatch.setattr(
        text2sql.pipeline.DatabaseResources, "load", lambda *_, **__: contextlib.nullcontext()
    )
    monkeypatch.setattr(text2sql.llm, "LLMClient", stand_in_client)
    monkeypatch.setattr(text2sql.evals.runner, "LLMClient", stand_in_client)
    monkeypatch.setattr(text2sql.evals.runner, "plan_run", lambda **_: SimpleNamespace(split="dev"))
    monkeypatch.setattr(text2sql.evals.runner, "start_run", lambda: "run")
    result = runner.invoke(app, args)
    assert isinstance(result.exception, ClientOpenedError), result.output
    assert result.exception.settings.offline


def users_grammar(
    db_id: str, *, dataset: Dataset, mode: QueryMode, db_path: Path | None = None
) -> SqlGrammar:
    """Stands in for the pipeline's full grammar: a `users` table without its hidden columns."""
    users = Table(name="users", columns=(Column(name="id"), Column(name="email")))
    return build_grammar(DatabaseSchema(db_id=db_id, tables=(users,)), grammar_options(mode))


@pytest.mark.parametrize(
    ("db", "text", "verdict"),
    [
        ("saas_crm", "SELECT T1.email FROM users AS T1 LIMIT 5", "accepted as sql"),
        ("saas_crm", "ABSTAIN: that is another tenant's data", "accepted as abstain"),
        ("california_schools", "SELECT T1.email FROM users AS T1", "accepted as sql"),
    ],
)
def test_grammar_check_accepts_what_the_pipeline_grammar_accepts(
    db: str, text: str, verdict: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(text2sql.pipeline, "full_grammar", users_grammar)
    result = runner.invoke(app, ["grammar", "--db", db, "--check", text])
    assert result.exit_code == 0, result.output
    assert verdict in result.output


@pytest.mark.parametrize(
    ("db", "text", "column"),
    [
        ("saas_crm", "SELECT T1.password_hash FROM users AS T1 LIMIT 5", 11),
        ("saas_crm", "DELETE FROM users", 1),
        # A BIRD database is served in benchmark mode, which offers no abstention.
        ("california_schools", "ABSTAIN: not answerable", 1),
    ],
)
def test_grammar_check_rejects_and_points_at_the_first_bad_character(
    db: str, text: str, column: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(text2sql.pipeline, "full_grammar", users_grammar)
    result = runner.invoke(app, ["grammar", "--db", db, "--check", text])
    assert result.exit_code == 1
    assert "rejected by the grammar" in result.output
    caret = next(line for line in result.output.splitlines() if line.strip() == "^")
    assert len(caret) == column, result.output
    assert "Expected one of" not in result.output


def test_grammar_check_reports_a_query_cut_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text2sql.pipeline, "full_grammar", users_grammar)
    # Tenant mode requires a LIMIT, so the query ends where the grammar still expects one.
    result = runner.invoke(
        app, ["grammar", "--db", "saas_crm", "--check", "SELECT T1.email FROM users AS T1"]
    )
    assert result.exit_code == 1
    assert "rejected by the grammar: Unexpected end-of-input." in result.output
    assert "Expected one of" not in result.output
