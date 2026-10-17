"""The API accepts the grammar for the fixture schema in every mode. Costs well under a cent on
gpt-6-luna; runs only with T2SQL_LIVE_TESTS=1 and an API key in the environment or `.env`."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from text2sql.config import Settings
from text2sql.grammar import SqlGrammar
from text2sql.llm import LLMClient, RunBudget

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("T2SQL_LIVE_TESTS") != "1", reason="set T2SQL_LIVE_TESTS=1 to call OpenAI"
    ),
]


def test_api_accepts_the_generated_grammars(
    benchmark_grammar: SqlGrammar,
    production_grammar: SqlGrammar,
    tenant_grammar: SqlGrammar,
    tmp_path: Path,
) -> None:
    real = Settings()
    if real.openai_api_key is None:
        pytest.skip("no OPENAI_API_KEY")
    settings = real.model_copy(
        update={"cache_dir": tmp_path / "cache", "max_spend_usd": 0.01, "offline": False}
    )

    async def probe() -> list[bool]:
        async with LLMClient(settings, budget=RunBudget.from_settings(settings)) as client:
            return [
                await client.grammar_accepted(g)
                for g in (benchmark_grammar, production_grammar, tenant_grammar)
            ]

    assert asyncio.run(probe()) == [True, True, True]
