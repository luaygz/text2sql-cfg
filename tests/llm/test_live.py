"""One real grammar-constrained call. Costs a fraction of a cent on gpt-6-luna flex; runs only
with T2SQL_LIVE_TESTS=1 and an API key in the environment or `.env`."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from text2sql.config import Settings
from text2sql.grammar import SqlGrammar
from text2sql.llm import LLMClient, Message, RunBudget, SqlToolCall

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("T2SQL_LIVE_TESTS") != "1", reason="set T2SQL_LIVE_TESTS=1 to call OpenAI"
    ),
]


def test_grammar_call_round_trip(grammar: SqlGrammar, tmp_path: Path) -> None:
    real = Settings()
    if real.openai_api_key is None:
        pytest.skip("no OPENAI_API_KEY")
    settings = real.model_copy(
        update={
            "cache_dir": tmp_path / "cache",
            "runs_dir": tmp_path / "runs",
            "max_spend_usd": 0.02,
            "service_tier": "flex",
            "max_output_tokens": 2000,
            "offline": False,
        }
    )
    # Real spend goes to the real ledger; responses go to a scratch cache.
    client = LLMClient(settings, budget=RunBudget.from_settings(settings))

    async def run() -> SqlToolCall:
        async with client:
            return await client.sql_call(
                model="gpt-6-luna",
                messages=[
                    Message("developer", "Answer with one SQLite query over table singer."),
                    Message("user", "Show the names of at most 5 singers."),
                ],
                grammar=grammar,
                effort="low",
                purpose="test.live",
            )

    result = asyncio.run(run())
    assert grammar.accepts(result.raw_input)
    assert result.output.kind == "sql"
    assert result.meta.cache_hit is False
    assert 0 < result.meta.cost_usd < 0.01
    assert result.meta.usage.input_tokens > 0
