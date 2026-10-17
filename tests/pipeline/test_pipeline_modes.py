"""Tenant mode on the real SaaS database, the time-limit policy per mode, the grammar-off
ablation, and the fallback to the linked grammar when the full-schema grammar is too large for
the API."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from pipeline_fakes import (
    FRENCH,
    UNKNOWN_ALIAS,
    FakeLLM,
    analysis,
    config,
    linker,
    request,
    run_pipeline,
)

from text2sql.catalog import build_catalog
from text2sql.config import QueryMode, Settings
from text2sql.data.saas import DEFAULT_DB_PATH, SAAS_DB_ID
from text2sql.generation.candidates import SqlAnswer
from text2sql.pipeline import DatabaseResources
from text2sql.pipeline import pipeline as pipeline_module
from text2sql.pipeline.events import CollectingEventLog
from text2sql.pipeline.resources import execution_limits
from text2sql.retrieval import QuestionAnalysis
from text2sql.safety import ScopeContext

ResourcesFactory = Callable[..., DatabaseResources]

needs_saas = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="data/saas/crm.sqlite not generated (make saas)"
)
ACCOUNTS = "SELECT T1.name FROM accounts AS T1 ORDER BY T1.name LIMIT 200"


@needs_saas
def test_tenant_requests_run_scoped_with_the_session_identity(
    settings: Settings, events_path: Path
) -> None:
    res = DatabaseResources.load(
        SAAS_DB_ID, dataset="saas", mode=QueryMode.TENANT, events_path=events_path
    )
    try:
        llm = FakeLLM(settings, sql={("direct_full", 0): [ACCOUNTS]})
        req = request(QueryMode.TENANT, db_id=SAAS_DB_ID, scope=ScopeContext(tenant_id=2))

        answer, trace = run_pipeline(llm, config(), res, req)
    finally:
        res.close()

    candidate = trace.candidates[0]
    assert answer.status == "answered"
    assert answer.sql == ACCOUNTS
    assert candidate.params == {"tenant_id": 2}
    assert candidate.executed_sql is not None and ":tenant_id" in candidate.executed_sql
    with sqlite3.connect(f"file:{DEFAULT_DB_PATH}?mode=ro", uri=True) as conn:
        own = conn.execute(
            "SELECT name FROM accounts WHERE tenant_id = 2 ORDER BY name LIMIT 200"
        ).fetchall()
    assert candidate.result is not None
    assert list(candidate.result.rows) == own
    # The model never sees the tenant column, in the prompt or the grammar.
    assert "tenant_id" not in llm.messages[0][0].text
    assert not res.full_grammar.accepts("SELECT T1.tenant_id FROM accounts AS T1 LIMIT 5")


def test_saas_is_only_served_in_tenant_mode(events_path: Path) -> None:
    with pytest.raises(ValueError, match="only served in tenant mode"):
        DatabaseResources.load(
            SAAS_DB_ID, dataset="saas", mode=QueryMode.PRODUCTION, events_path=events_path
        )


@pytest.mark.parametrize(
    ("mode", "evaluation", "wall_clock"),
    [
        # A user is waiting: a slow query is a denial of service and must be cut off in time.
        (QueryMode.TENANT, False, True),
        (QueryMode.PRODUCTION, False, True),
        # Nobody is waiting: the outcome must not depend on machine load, so a replay matches.
        (QueryMode.TENANT, True, False),
        (QueryMode.BENCHMARK, False, False),
        (QueryMode.BENCHMARK, True, False),
    ],
)
def test_only_requests_a_user_waits_on_get_a_wall_clock_limit(
    mode: QueryMode, evaluation: bool, wall_clock: bool
) -> None:
    assert execution_limits(mode, evaluation=evaluation).wall_clock is wall_clock


def test_grammar_off_sends_json_sql_through_the_other_layers(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    res = resources_factory()
    llm = FakeLLM(settings, structured_values={SqlAnswer: SqlAnswer(sql=f"{UNKNOWN_ALIAS}")})
    cfg = config(grammar=False)

    answer, trace = run_pipeline(llm, cfg, res)

    candidate = trace.candidates[0]
    assert llm.calls_for("generate_json.direct_full") != []
    assert candidate.attempts[0].output == "json"
    assert candidate.grammar_calls == 0
    assert candidate.status == "guard_rejected"
    assert candidate.rejection is not None and candidate.rejection.layer == "validator"
    assert [e.context["grammar"] for e in trace.safety_events] == ["off"]
    assert answer.status == "failed"


def test_a_full_grammar_over_the_api_budget_falls_back_to_the_linked_one(
    settings: Settings, tmp_path: Path, events_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wide = tmp_path / "wide.sqlite"
    names = [f"measurement_{i:03d}_with_a_long_descriptive_name" for i in range(240)]
    with sqlite3.connect(wide) as conn:
        conn.execute(
            "CREATE TABLE singer (singer_id INTEGER PRIMARY KEY, name TEXT, country TEXT, "
            + ", ".join(f"{n} REAL" for n in names)
            + ")"
        )
        conn.execute("INSERT INTO singer (singer_id, name, country) VALUES (1, 'Ada', 'France')")
    conn.close()
    catalog = build_catalog(wide, "wide")
    res = DatabaseResources(
        db_id="wide",
        dataset="bird",
        mode=QueryMode.BENCHMARK,
        db_path=wide,
        catalog=catalog,
        full_schema=catalog.schema(),
        policy=None,
        event_log=CollectingEventLog(events_path),
        column_index=object(),  # type: ignore[arg-type]
    )
    assert not res.full_grammar.size.fits_api_budget
    monkeypatch.setattr(pipeline_module, "link_schema", linker({"singer": ["name", "country"]}))
    llm = FakeLLM(
        settings,
        sql={("direct_full", 0): [FRENCH]},
        structured_values={QuestionAnalysis: analysis()},
    )
    cfg = config(question_analysis=True, schema_linking=True)

    try:
        answer, trace = run_pipeline(llm, cfg, res, request(db_id="wide"))
    finally:
        res.close()

    assert answer.sql == FRENCH
    assert trace.grammars["full"].built_from == "linked"
    assert trace.grammars["full"].fingerprint == trace.grammars["linked"].fingerprint
    assert trace.grammars["full"].fits_api_budget
    assert any("full grammar too large" in w for w in trace.warnings)
    # The full-schema strategy still shows the whole schema in its prompt.
    assert names[-1] in llm.messages[-1][0].text
