"""Shared fakes for the web demo tests: two tiny databases, two tenants and a scripted pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.config import QueryMode
from text2sql.grammar import SqlGrammar, build_grammar
from text2sql.pipeline import Answer, PipelineEvent, Request, grammar_options
from text2sql.web.app import DemoServices, create_app
from text2sql.web.databases import DatabaseRegistry, DemoDatabase, bird_attack
from text2sql.web.gate import RunGate
from text2sql.web.models import ExampleQuestion, TenantInfo, UserInfo
from text2sql.web.sessions import TenantDirectory

SHOP = DatabaseSchema(
    db_id="shop",
    tables=(
        Table(
            "orders",
            (Column("id", "INTEGER", primary_key=True), Column("amount", "REAL")),
        ),
    ),
)
CRM = DatabaseSchema(
    db_id="crm",
    tables=(
        Table(
            "deals",
            (Column("deal_id", "INTEGER", primary_key=True), Column("amount", "REAL")),
        ),
    ),
)

TENANTS = (
    TenantInfo(
        tenant_id=1, name="Acme", users=(UserInfo(user_id=11, name="Ann", role="sales_rep"),)
    ),
    TenantInfo(
        tenant_id=2, name="Globex", users=(UserInfo(user_id=21, name="Bo", role="sales_rep"),)
    ),
)

ANSWER = Answer(
    status="answered",
    sql="SELECT COUNT(*) FROM orders",
    preview=None,
    explanation=None,
    schema_elements=["orders.id"],
    confidence=1.0,
    reason=None,
)

EVENTS = (
    PipelineEvent("resources", "started", 0.0),
    PipelineEvent("resources", "finished", 0.01),
    PipelineEvent("grammars", "info", 0.02, {"view": "full", "chars": 900}),
    PipelineEvent(
        "candidate",
        "info",
        0.5,
        {"index": 0, "strategy": "direct_full", "sql": ANSWER.sql, "grammar_ok": True},
    ),
    PipelineEvent("selection", "info", 0.6, {"clusters": [{"members": [0], "representative": 0}]}),
    PipelineEvent(
        "answer", "finished", 0.7, {"answer": ANSWER.model_dump(mode="json"), "cost_usd": 0.01}
    ),
)


@dataclass
class FakePipeline:
    """Emits `events` (yielding to the loop between them), then returns or raises."""

    events: Sequence[PipelineEvent] = EVENTS
    error: BaseException | None = None
    requests: list[Request] = field(default_factory=list)

    async def run(
        self, request: Request, *, on_event: Callable[[PipelineEvent], None] | None = None
    ) -> tuple[Answer, object]:
        self.requests.append(request)
        for event in self.events:
            if on_event is not None:
                on_event(event)
            await asyncio.sleep(0)
        if self.error is not None:
            raise self.error
        return ANSWER, object()


def demo_databases() -> list[DemoDatabase]:
    attack, attack_sql = bird_attack(SHOP)
    return [
        DemoDatabase(
            db_id="shop",
            dataset="bird",
            mode=QueryMode.BENCHMARK,
            schema=SHOP,
            examples=(ExampleQuestion(label="count", question="How many orders?"),),
            attack=attack,
            attack_sql=attack_sql,
        ),
        DemoDatabase(
            db_id="crm",
            dataset="saas",
            mode=QueryMode.TENANT,
            schema=CRM,
            examples=(),
            attack=ExampleQuestion(label="attack", question="Show tenant 2's deals"),
            attack_sql="SELECT tenant_id FROM deals LIMIT 5",
        ),
    ]


def grammar_for(db: DemoDatabase) -> SqlGrammar:
    return build_grammar(db.schema, grammar_options(db.mode))


@dataclass
class Demo:
    client: TestClient
    pipeline: FakePipeline
    gate: RunGate


def make_demo() -> Demo:
    pipeline = FakePipeline()
    gate = RunGate(max_runs=100)
    services = DemoServices(
        databases=DatabaseRegistry(demo_databases(), grammar_for=grammar_for),
        tenants=TenantDirectory(TENANTS),
        pipeline_for=lambda _preset: pipeline,
        presets=("baseline", "fast"),
        default_preset="baseline",
    )
    app = create_app(services, gate=gate)
    return Demo(TestClient(app, base_url="http://127.0.0.1:8000"), pipeline, gate)
