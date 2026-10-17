"""Fixtures for the LLM client tests: isolated settings and paths, a client wired to the fake
transport in `llm_fakes`, and a tiny grammar. Nothing here touches the network."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from llm_fakes import API_KEY, FakeAPI
from openai import AsyncOpenAI

from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.config import Settings
from text2sql.grammar import GrammarOptions, SqlGrammar
from text2sql.llm import LLMClient, RunBudget
from text2sql.llm.retry import RetryPolicy
from text2sql.observability import start_run

REPO_ROOT = Path(__file__).resolve().parents[2]

TINY_GRAMMAR = r"""
start: query
query: "SELECT " column " FROM singer" limit?
column: "name" | "age"
limit: " LIMIT " NUMBER
NUMBER: /[1-9][0-9]{0,3}/
"""


@pytest.fixture
def grammar() -> SqlGrammar:
    schema = DatabaseSchema(
        db_id="concert", tables=(Table("singer", (Column("name"), Column("age"))),)
    )
    return SqlGrammar(
        definition=TINY_GRAMMAR,
        schema=schema,
        options=GrammarOptions(),
        description="One SELECT over the singer table.",
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        openai_api_key=API_KEY,
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "spend_ledger.jsonl",
        runs_dir=tmp_path / "runs",
        pricing_path=REPO_ROOT / "config" / "pricing.yaml",
        service_tier="flex",
        max_spend_usd=1.0,
        total_spend_cap_usd=5.0,
        max_concurrency=4,
        max_output_tokens=2000,
        offline=False,
        phase="test",
    )


@pytest.fixture(autouse=True)
def trace_run(tmp_path: Path) -> Path:
    traces = tmp_path / "runs" / "traces"
    start_run("test-run", traces_dir=traces)
    return traces / "test-run.jsonl"


@pytest.fixture
def fake_api() -> FakeAPI:
    return FakeAPI()


@pytest.fixture
def make_client(settings: Settings, fake_api: FakeAPI) -> Iterator[Callable[..., LLMClient]]:
    """Build clients that talk to `fake_api`; keyword overrides patch the settings."""
    clients: list[LLMClient] = []

    def factory(**overrides: Any) -> LLMClient:
        s = settings.model_copy(update=overrides)
        openai_client = AsyncOpenAI(
            api_key=API_KEY,
            base_url="http://fake.openai.test/v1",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api.handle)),
        )
        client = LLMClient(
            s,
            budget=RunBudget.from_settings(s, run_id="test-run"),
            openai_client=openai_client,
            retry=RetryPolicy(max_retries=3, base_delay_s=0.001, max_delay_s=0.005),
        )
        clients.append(client)
        return client

    yield factory
    for client in clients:
        asyncio.run(client.aclose())
