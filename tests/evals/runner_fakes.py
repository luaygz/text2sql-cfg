"""A scripted stand-in for the pipeline, and tiny databases, for the runner tests."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.config import ReasoningEffort, Settings
from text2sql.evals.datasets import BirdItem
from text2sql.evals.runner import RunOutcome, RunPlan, configure, execute_plan, finish_run
from text2sql.execution import QueryResult, Row
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar
from text2sql.llm import LLMClient, RunBudget, SpendLedger
from text2sql.pipeline import Answer, Request
from text2sql.safety import SafetyEvent, ScopeContext
from text2sql.safety.leaks import AttackVerdict, Execution


def make_db(path: Path, script: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(script)
    conn.close()
    return path


@dataclass(frozen=True)
class FakeRejection:
    layer: str
    rule: str
    detail: str


@dataclass
class FakeCandidate:
    """A candidate in its final state; `status` and `executed_sql` say whether it ran."""

    sql: str | None
    status: str = "ok"
    strategy: str = "direct_full"
    model: str = "gpt-6.1-sol"
    effort: ReasoningEffort = "low"
    abstain_reason: str | None = None
    grammar_ok: bool = True
    validator_error: str | None = None
    scoping_error: str | None = None
    rejection: FakeRejection | None = None
    exec_error: str | None = None
    executed_sql: str | None = None
    rows: tuple[Row, ...] = ()
    fingerprint: str | None = None
    repairs: int = 0
    cost_usd: float = 0.01
    model_latency_s: float = 1.5

    def __post_init__(self) -> None:
        if self.status in {"ok", "empty"} and self.executed_sql is None:
            self.executed_sql = self.sql

    @property
    def result(self) -> QueryResult | None:
        if self.executed_sql is None:
            return None
        return QueryResult(columns=("c",), rows=self.rows, truncated=False, elapsed_s=0.0)

    @property
    def row_count(self) -> int | None:
        return None if self.executed_sql is None else len(self.rows)


@dataclass
class FakeSelection:
    index: int | None


@dataclass
class FakeTrace:
    candidates: list[FakeCandidate]
    selection: FakeSelection | None = None
    linked_columns: frozenset[tuple[str, str]] | None = None
    safety_events: list[SafetyEvent] = field(default_factory=list)
    grammar_calls: int = 1
    grammar_failures: int = 0
    cost_usd: float = 0.02
    model_latency_s: float = 3.0


def answered(
    sql: str, *candidates: FakeCandidate, index: int = 0, **trace: Any
) -> tuple[Answer, FakeTrace]:
    """The pipeline answered with `sql`, chosen from `candidates` (default: just that SQL)."""
    cands = list(candidates) or [FakeCandidate(sql)]
    answer = Answer(
        status="answered", sql=sql, preview=None, explanation=None, schema_elements=[],
        confidence=1.0, reason=None,
    )  # fmt: skip
    return answer, FakeTrace(cands, selection=FakeSelection(index), **trace)


def abstained(reason: str = "not in the schema", **trace: Any) -> tuple[Answer, FakeTrace]:
    answer = Answer(
        status="abstained", sql=None, preview=None, explanation=None, schema_elements=[],
        confidence=1.0, reason=reason,
    )  # fmt: skip
    cand = FakeCandidate(None, status="abstained", abstain_reason=reason)
    return answer, FakeTrace([cand], selection=None, **trace)


type Script = Callable[[Request], tuple[Answer, FakeTrace]]


@dataclass
class FakeResources:
    visible_schema: DatabaseSchema
    full_grammar: SqlGrammar

    @classmethod
    def of(cls, db_path: Path, db_id: str) -> FakeResources:
        schema = introspect_sqlite(db_path, db_id)
        return cls(schema, build_grammar(schema, GrammarOptions()))


def leak_judge(marker: str) -> Callable[..., AttackVerdict]:
    """A judge that calls any executed row containing `marker` a violation."""

    def judge(
        *, scope: ScopeContext, executions: Sequence[Execution], events: Sequence[SafetyEvent]
    ) -> AttackVerdict:
        leaked = any(marker in str(cell) for e in executions for row in e.rows for cell in row)
        return AttackVerdict(
            violation=leaked,
            reasons=(f"{marker} for tenant {scope.tenant_id}",) if leaked else (),
            stopped_at=events[0].layer if events and not executions else None,
            events_by_layer={},
        )

    return judge


class FakeSystem:
    """Answers each request with `script(request)`; `asked` records every request."""

    def __init__(
        self,
        script: Script,
        resources: Mapping[str, FakeResources],
        judge: Callable[..., AttackVerdict] | None = None,
    ) -> None:
        self.script = script
        self._resources = resources
        self._judge = judge
        self.asked: list[Request] = []
        self.closed = False

    async def ask(self, request: Request) -> tuple[Answer, FakeTrace]:
        self.asked.append(request)
        return self.script(request)

    def resources(self, db_id: str) -> FakeResources:
        return self._resources[db_id]

    @property
    def judge(self) -> Callable[..., AttackVerdict] | None:
        return self._judge

    def close(self) -> None:
        self.closed = True


# A BIRD-like database and items over it, and helpers to run and report a plan offline.
SCHOOLS = """
CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT, city TEXT, enrollment INTEGER);
INSERT INTO schools VALUES (1, 'Alder', 'Fresno', 300), (2, 'Birch', 'Fresno', 120),
                           (3, 'Cedar', 'Oakland', 450);
"""
FRESNO = "SELECT name FROM schools WHERE city = 'Fresno'"
T0 = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def item(gold_db: Path, gold: str = FRESNO, qid: str = "1", **kw: Any) -> BirdItem:
    fields: dict[str, Any] = {
        "question_id": qid,
        "db_id": "schools",
        "question": f"Which schools are in Fresno? ({qid})",
        "evidence": "Fresno is a city",
        "gold_sql": gold,
        "difficulty": "simple",
        "gold_db": gold_db,
        "alternate_gold": None,
    }
    fields.update(kw)
    return BirdItem(**fields)


def resources_for(db: Path) -> dict[str, FakeResources]:
    return {"schools": FakeResources.of(db, "schools")}


def offline_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        offline=True,
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.jsonl",
        runs_dir=tmp_path / "runs",
    )


def plan(
    items: list[BirdItem],
    *,
    preset: str = "best",
    concurrency: int = 2,
    overrides: dict[str, str] | None = None,
) -> RunPlan:
    config, recorded = configure(preset, overrides or {}, with_evidence=True)
    return RunPlan(
        dataset="bird_minidev", split="dev", preset=preset, config=config, overrides=recorded,
        with_evidence=True, items=items, concurrency=concurrency,
    )  # fmt: skip


def run_with(system: FakeSystem, run_plan: RunPlan, settings: Settings) -> RunOutcome:
    async def go() -> RunOutcome:
        budget = RunBudget.from_settings(settings, run_id="test-run")
        async with LLMClient(settings, budget=budget) as llm:
            return await execute_plan(
                run_plan, llm=llm, settings=settings, open_system=lambda *_: system,
                label=lambda _: False,
            )  # fmt: skip

    return asyncio.run(go())


def finish(
    run_plan: RunPlan, outcome: RunOutcome, tmp_path: Path, git_sha: str | None = None
) -> Path:
    budget = RunBudget(
        run_cap_usd=0.3, lifetime_cap_usd=30.0, ledger=SpendLedger(tmp_path / "ledger.jsonl"),
        run_id="r", phase="test",
    )  # fmt: skip
    return finish_run(
        run_plan, outcome, run_id="r", started=T0, spend=budget.summary(),
        settings=offline_settings(tmp_path), reports_dir=tmp_path / "reports",
        results_md=tmp_path / "RESULTS.md", git_sha=git_sha,
    )  # fmt: skip
