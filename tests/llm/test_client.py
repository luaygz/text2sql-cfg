from __future__ import annotations

import asyncio
import json
import sqlite3
import zlib
from collections.abc import Callable
from pathlib import Path

import openai
import pytest
from hypothesis import given
from hypothesis import strategies as st
from llm_fakes import (
    API_KEY,
    FakeAPI,
    embeddings_json,
    message_output,
    response_json,
    tool_call_item,
    usage_json,
)
from pydantic import BaseModel

from text2sql.config import Settings
from text2sql.grammar import SqlGrammar
from text2sql.llm import (
    BudgetExceeded,
    CacheMiss,
    CallMeta,
    GrammarCallFailed,
    GrammarRejectedByAPI,
    LLMClient,
    Message,
    RunBudget,
    SqlToolCall,
    StructuredCallFailed,
    tool_output_item,
)
from text2sql.llm.client import split_by_weight

MESSAGES = (
    Message("developer", "You write SQLite for the concert database.", cache_breakpoint=True),
    Message("user", "List singer names."),
)
SQL = "SELECT name FROM singer LIMIT 5"
MakeClient = Callable[..., LLMClient]


async def ask(client: LLMClient, grammar: SqlGrammar, **kwargs: object) -> SqlToolCall:
    args: dict[str, object] = {
        "model": "gpt-6-luna",
        "messages": MESSAGES,
        "grammar": grammar,
        "effort": "low",
        "purpose": "test.sql",
    }
    return await client.sql_call(**(args | kwargs))  # type: ignore[arg-type]


def test_sql_call_sends_a_forced_grammar_tool_and_parses_the_call(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    fake_api.reply(response_json([tool_call_item(SQL)]))
    result = asyncio.run(ask(make_client(), grammar))

    assert result.output.kind == "sql"
    assert result.output.text == SQL
    assert result.call_id == "call_abc"
    assert result.history_items == (
        {"type": "custom_tool_call", "call_id": "call_abc", "name": "sql_query", "input": SQL},
    )
    sent = fake_api.requests[0]
    assert sent["tools"] == [
        {
            "type": "custom",
            "name": "sql_query",
            "description": grammar.description,
            "format": {"type": "grammar", "syntax": "lark", "definition": grammar.definition},
        }
    ]
    assert sent["tool_choice"] == {"type": "custom", "name": "sql_query"}
    assert sent["parallel_tool_calls"] is False
    assert sent["prompt_cache_options"] == {"mode": "explicit"}
    assert sent["service_tier"] == "flex"
    assert sent["store"] is False
    assert sent["reasoning"] == {"effort": "low"}
    assert "temperature" not in sent
    developer, user = sent["input"]
    assert developer["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert "prompt_cache_breakpoint" not in user["content"][0]


def test_meta_prices_usage_at_the_tier_the_response_reports(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    usage = usage_json(input_tokens=10_000, cached=4_000, written=2_000, output=500)
    fake_api.reply(response_json([tool_call_item(SQL)], usage=usage, service_tier="default"))
    meta = asyncio.run(ask(make_client(), grammar)).meta

    expected = (4_000 * 0.10 + 4_000 * 0.01 + 2_000 * 0.125 + 500 * 0.50) / 1e6
    assert meta.service_tier == "default"
    assert meta.cost_usd == pytest.approx(expected)
    assert meta.priced_usd == pytest.approx(expected)
    assert meta.cache_hit is False
    assert meta.usage.cached_tokens == 4_000
    assert meta.usage.cache_write_tokens == 2_000


def test_repeat_call_is_a_free_cache_hit_and_samples_are_separate(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    fake_api.reply(response_json([tool_call_item(SQL)]))
    fake_api.reply(response_json([tool_call_item("SELECT age FROM singer")]))

    async def run() -> tuple[SqlToolCall, SqlToolCall, SqlToolCall]:
        return (
            await ask(client, grammar),
            await ask(client, grammar),
            await ask(client, grammar, sample=1),
        )

    first, again, other = asyncio.run(run())
    assert len(fake_api.requests) == 2
    assert again.output == first.output
    assert again.meta.cache_hit is True
    assert again.meta.cost_usd == 0.0
    assert again.meta.priced_usd == pytest.approx(first.meta.cost_usd)
    assert again.meta.api_latency_s == pytest.approx(first.meta.api_latency_s)
    assert other.output.text == "SELECT age FROM singer"
    assert len(list(client.budget.ledger.entries())) == 2
    assert client.budget.summary().by_model["gpt-6-luna"].cache_hits == 1


def test_concurrent_identical_calls_share_one_request(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    fake_api.delay_s = 0.02
    fake_api.reply(response_json([tool_call_item(SQL)]))

    async def run() -> list[SqlToolCall]:
        return await asyncio.gather(*(ask(client, grammar) for _ in range(3)))

    results = asyncio.run(run())
    assert len(fake_api.requests) == 1
    assert sorted(r.meta.cache_hit for r in results) == [False, True, True]
    assert len(list(client.budget.ledger.entries())) == 1


def test_semaphore_bounds_requests_in_flight(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client(max_concurrency=2)
    fake_api.delay_s = 0.02
    for _ in range(6):
        fake_api.reply(response_json([tool_call_item(SQL)]))

    async def run() -> list[SqlToolCall]:
        return await asyncio.gather(*(ask(client, grammar, sample=i) for i in range(6)))

    asyncio.run(run())
    assert len(fake_api.requests) == 6
    assert fake_api.max_in_flight == 2


def test_offline_replays_the_cache_without_an_api_key(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, settings: Settings
) -> None:
    fake_api.reply(response_json([tool_call_item(SQL)]))
    live = asyncio.run(ask(make_client(), grammar))

    offline_settings = settings.model_copy(update={"offline": True, "openai_api_key": None})
    offline = LLMClient(offline_settings, budget=RunBudget.from_settings(offline_settings))

    async def run() -> SqlToolCall:
        async with offline:
            replayed = await ask(offline, grammar)
            with pytest.raises(CacheMiss):
                await ask(offline, grammar, messages=[Message("user", "Something new")])
        return replayed

    replayed = asyncio.run(run())
    assert replayed.output == live.output
    assert replayed.meta.cache_hit is True
    assert offline._openai is None
    assert len(fake_api.requests) == 1


@pytest.mark.parametrize(
    ("output", "status", "incomplete", "reason"),
    [
        ([message_output(text="SELECT name FROM singer")], "completed", None, "no_tool_call"),
        ([message_output(refusal="I can't help with that.")], "completed", None, "refusal"),
        (
            [tool_call_item("SELECT name FROM singer")],
            "incomplete",
            "max_output_tokens",
            "incomplete",
        ),
        ([tool_call_item("DROP TABLE singer")], "completed", None, "local_parse"),
    ],
    ids=["free-text", "refusal", "truncated", "unparseable"],
)
def test_unusable_responses_raise_grammar_call_failed(
    make_client: MakeClient,
    fake_api: FakeAPI,
    grammar: SqlGrammar,
    output: list[dict[str, object]],
    status: str,
    incomplete: str | None,
    reason: str,
) -> None:
    client = make_client()
    fake_api.reply(response_json(output, status=status, incomplete_reason=incomplete))
    with pytest.raises(GrammarCallFailed) as caught:
        asyncio.run(ask(client, grammar))
    failure = caught.value
    assert failure.reason == reason
    assert failure.meta.cost_usd > 0
    assert len(list(client.budget.ledger.entries())) == 1
    if reason in {"incomplete", "local_parse"}:
        assert failure.raw_input == output[0]["input"]
        assert failure.call_id == "call_abc"
        assert failure.history_items[0]["type"] == "custom_tool_call"
    if reason == "refusal":
        assert failure.raw_input == "I can't help with that."


def test_api_grammar_rejection_is_typed_unbilled_and_remembered(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, settings: Settings
) -> None:
    client = make_client()
    message = "Invalid lark grammar. regex construction fuel exhausted"
    fake_api.error(400, message, type_="invalid_request_error", param="tools")

    async def run() -> None:
        with pytest.raises(GrammarRejectedByAPI) as first:
            await ask(client, grammar)
        assert first.value.provider_message == message
        assert first.value.reason == "api_rejected"
        assert first.value.fingerprint == grammar.fingerprint
        with pytest.raises(GrammarRejectedByAPI):
            await ask(client, grammar, sample=3)
        assert await client.grammar_accepted(grammar) is False

    asyncio.run(run())
    assert len(fake_api.requests) == 1
    assert list(client.budget.ledger.entries()) == []
    assert client.budget.reserved_usd == 0.0
    with sqlite3.connect(settings.cache_dir / "responses.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone() == (0,)


def test_other_bad_requests_propagate_unchanged(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    fake_api.error(400, "Unsupported parameter: 'temperature'", param="temperature")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(ask(make_client(), grammar))


FLAGGED = (
    "Invalid prompt: your prompt was flagged as potentially violating our usage policy. "
    "Please try again with a different prompt."
)


def flag(fake_api: FakeAPI) -> None:
    fake_api.error(400, FLAGGED, code="invalid_prompt", type_="invalid_request_error")


def test_flagged_sql_prompt_is_a_typed_unbilled_failure_that_replays(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    flag(fake_api)
    fake_api.reply(response_json([tool_call_item(SQL)]))

    async def run() -> tuple[GrammarCallFailed, GrammarCallFailed, SqlToolCall]:
        with pytest.raises(GrammarCallFailed) as first:
            await ask(client, grammar)
        with pytest.raises(GrammarCallFailed) as rerun:
            await ask(client, grammar)
        fresh_draw = await ask(client, grammar, sample=1)
        return first.value, rerun.value, fresh_draw

    first, rerun, fresh_draw = asyncio.run(run())
    assert (first.reason, first.detail) == ("flagged", FLAGGED)
    assert not isinstance(first, GrammarRejectedByAPI)
    assert (first.meta.cost_usd, first.meta.priced_usd, first.meta.cache_hit) == (0.0, 0.0, False)
    assert (rerun.reason, rerun.meta.cache_hit) == ("flagged", True)
    assert rerun.meta.request_hash == first.meta.request_hash
    assert fresh_draw.output.text == SQL
    assert len(fake_api.requests) == 2  # the flag is retried neither by the policy nor the rerun
    assert len(list(client.budget.ledger.entries())) == 1
    assert client.budget.reserved_usd == 0.0

    offline = make_client(offline=True, openai_api_key=None)
    with pytest.raises(GrammarCallFailed) as replayed:
        asyncio.run(ask(offline, grammar))
    assert (replayed.value.reason, replayed.value.meta.cache_hit) == ("flagged", True)


def test_flagged_structured_prompt_raises_structured_call_failed(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    flag(fake_api)
    with pytest.raises(StructuredCallFailed) as caught:
        asyncio.run(
            make_client().structured(
                model="gpt-6-luna", messages=MESSAGES, output=Linked, effort="none", purpose="t"
            )
        )
    assert (caught.value.reason, caught.value.raw_text) == ("flagged", None)
    assert caught.value.meta.cost_usd == 0.0


def test_default_output_cap_is_4096_and_env_overrides_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAX_OUTPUT_TOKENS", raising=False)
    assert Settings(_env_file=None).max_output_tokens == 4096  # type: ignore[call-arg]
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "777")
    assert Settings(_env_file=None).max_output_tokens == 777  # type: ignore[call-arg]


def test_sql_call_output_cap_override_is_sent_keyed_and_billed_when_hit(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, settings: Settings
) -> None:
    client = make_client()
    fake_api.reply(response_json([tool_call_item(SQL)]))
    fake_api.reply(response_json([tool_call_item(SQL)]))
    # A runaway: grammar-valid tool input, cut off at the cap.
    fake_api.reply(
        response_json(
            [tool_call_item("SELECT name FROM singer LIMIT 1")],
            status="incomplete",
            incomplete_reason="max_output_tokens",
            usage=usage_json(output=300, reasoning=250),
        )
    )

    async def run() -> GrammarCallFailed:
        await ask(client, grammar)
        await ask(client, grammar, max_output_tokens=300)
        with pytest.raises(GrammarCallFailed) as cut_off:
            await ask(client, grammar, max_output_tokens=300, sample=1)
        with pytest.raises(ValueError, match="positive"):
            await ask(client, grammar, max_output_tokens=0)
        return cut_off.value

    failure = asyncio.run(run())
    assert [r["max_output_tokens"] for r in fake_api.requests] == [
        settings.max_output_tokens,
        300,
        300,
    ]
    assert failure.reason == "incomplete"
    assert failure.raw_input == "SELECT name FROM singer LIMIT 1"
    assert failure.meta.usage.output_tokens == 300
    assert failure.meta.cost_usd == pytest.approx(failure.meta.priced_usd)
    assert failure.meta.cost_usd > 0
    ledger = list(client.budget.ledger.entries())
    assert len(ledger) == 3
    assert ledger[-1].output_tokens == 300


def test_grammar_probe_is_cheap_and_cached(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, settings: Settings
) -> None:
    fake_api.reply(
        response_json(
            [tool_call_item("SELECT")], status="incomplete", incomplete_reason="max_output_tokens"
        )
    )

    async def run(client: LLMClient) -> tuple[bool, bool]:
        return await client.grammar_accepted(grammar), await client.grammar_accepted(grammar)

    assert asyncio.run(run(make_client())) == (True, True)
    probe = fake_api.requests[0]
    assert probe["model"] == settings.small_model
    assert probe["reasoning"] == {"effort": "none"}
    assert probe["max_output_tokens"] == 16
    assert probe["tools"][0]["format"]["definition"] == grammar.definition
    assert len(fake_api.requests) == 1
    assert asyncio.run(make_client(offline=True).grammar_accepted(grammar)) is True


def test_repair_turn_replays_the_call_and_its_output(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    fake_api.reply(response_json([tool_call_item("SELECT age FROM singer")]))
    fake_api.reply(response_json([tool_call_item(SQL, call_id="call_def")]))

    async def run() -> SqlToolCall:
        first = await ask(client, grammar)
        feedback = tool_output_item(first.call_id, "error: no such column: age")
        return await ask(client, grammar, history=[*first.history_items, feedback])

    repaired = asyncio.run(run())
    assert repaired.output.text == SQL
    replayed = fake_api.requests[1]["input"][2:]
    assert replayed == [
        {
            "type": "custom_tool_call",
            "call_id": "call_abc",
            "name": "sql_query",
            "input": "SELECT age FROM singer",
        },
        {
            "type": "custom_tool_call_output",
            "call_id": "call_abc",
            "output": "error: no such column: age",
        },
    ]


class Linked(BaseModel):
    """Columns the question needs."""

    tables: list[str]
    confident: bool


def test_structured_uses_a_strict_schema_and_validates(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    client = make_client()
    fake_api.reply(
        response_json([message_output(text='{"tables": ["singer"], "confident": true}')])
    )
    fake_api.reply(response_json([message_output(text='{"tables": "singer"}')]))

    async def run() -> Linked:
        ok = await client.structured(
            model="gpt-6-luna", messages=MESSAGES, output=Linked, effort="none", purpose="t"
        )
        with pytest.raises(StructuredCallFailed) as bad:
            await client.structured(
                model="gpt-6-luna",
                messages=MESSAGES,
                output=Linked,
                effort="none",
                purpose="t",
                sample=1,
            )
        assert bad.value.reason == "invalid_json"
        assert bad.value.raw_text == '{"tables": "singer"}'
        return ok.value

    assert asyncio.run(run()) == Linked(tables=["singer"], confident=True)
    fmt = fake_api.requests[0]["text"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["name"] == "Linked"
    assert fmt["strict"] is True
    assert fmt["schema"]["additionalProperties"] is False
    assert sorted(fmt["schema"]["required"]) == ["confident", "tables"]


def test_structured_output_cap_is_sent_keyed_and_budgeted(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    # The fixture's default cap (2,000 output tokens on luna flex) reserves at least $0.0005,
    # over this run cap; a 100-token cap fits.
    client = make_client(max_spend_usd=0.0002)
    answer = '{"tables": ["singer"], "confident": true}'
    fake_api.reply(response_json([message_output(text=answer)]))
    runaway = response_json(
        [message_output(text=answer + "\n}" * 40)],
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    fake_api.reply(runaway)

    async def call(cap: int | None) -> Linked:
        result = await client.structured(
            model="gpt-6-luna",
            messages=MESSAGES,
            output=Linked,
            effort="none",
            purpose="t",
            max_output_tokens=cap,
        )
        return result.value

    async def run() -> None:
        with pytest.raises(BudgetExceeded):
            await call(None)
        assert await call(100) == Linked(tables=["singer"], confident=True)
        with pytest.raises(StructuredCallFailed) as truncated:
            await call(150)
        assert truncated.value.reason == "incomplete"
        assert await call(100) == Linked(tables=["singer"], confident=True)
        with pytest.raises(ValueError, match="positive"):
            await call(0)

    asyncio.run(run())
    assert [r["max_output_tokens"] for r in fake_api.requests] == [100, 150]
    assert client.budget.reserved_usd == 0.0


def test_embed_caches_each_text_and_batches_the_rest(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    client = make_client(embedding_batch_size=2)
    fake_api.reply(embeddings_json([[1.0, 0.0], [0.0, 1.0]]))
    fake_api.reply(embeddings_json([[0.5, 0.5]]))
    fake_api.reply(embeddings_json([[0.25, 0.75]]))

    async def run() -> tuple[list[list[float]], list[list[float]]]:
        first = await client.embed(["alpha", "beta", "gamma"], purpose="t")
        second = await client.embed(["gamma", "delta", "alpha"], purpose="t")
        return first, second

    first, second = asyncio.run(run())
    assert first == [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    assert second == [[0.5, 0.5], [0.25, 0.75], [1.0, 0.0]]
    assert [r["input"] for r in fake_api.requests] == [["alpha", "beta"], ["gamma"], ["delta"]]
    assert all(p.endswith("/embeddings") for p in fake_api.paths)
    assert len(list(client.budget.ledger.entries())) == 3

    offline = make_client(offline=True)
    assert asyncio.run(offline.embed(["beta"], purpose="t")) == [[0.0, 1.0]]
    with pytest.raises(CacheMiss):
        asyncio.run(offline.embed(["epsilon"], purpose="t"))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(client.embed(["ok", ""], purpose="t"))


def test_embedding_meta_is_billed_live_and_reproduced_offline(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    client = make_client(embedding_batch_size=2)
    # "alpha" and "beta" share a 9-token batch by UTF-8 length (5:4); "gamma" and "delta" are
    # billed alone.
    fake_api.reply(embeddings_json([[1.0], [2.0]], tokens=9))
    fake_api.reply(embeddings_json([[3.0]], tokens=3))
    fake_api.reply(embeddings_json([[4.0]], tokens=2))
    rate = 0.02 / 1e6

    async def run() -> tuple[CallMeta, CallMeta, CallMeta]:
        _, live_first = await client.embed_with_meta(["alpha", "beta", "gamma"], purpose="t")
        _, live_mixed = await client.embed_with_meta(["gamma", "delta", "alpha"], purpose="t")
        _, duplicate = await client.embed_with_meta(["alpha", "alpha"], purpose="t")
        return live_first, live_mixed, duplicate

    live_first, live_mixed, duplicate = asyncio.run(run())
    assert live_first.usage.input_tokens == 12
    assert live_first.cost_usd == pytest.approx(12 * rate)
    assert live_first.cache_hit is False
    assert live_mixed.usage.input_tokens == 3 + 2 + 5
    assert live_mixed.cost_usd == pytest.approx(2 * rate)
    assert live_mixed.priced_usd == pytest.approx(10 * rate)
    assert live_mixed.cache_hit is False
    assert duplicate.usage.input_tokens == 5
    assert (duplicate.cost_usd, duplicate.cache_hit) == (0.0, True)
    assert client.budget.summary().by_model["text-embedding-3-small"].cache_hits == 3

    offline = make_client(offline=True)
    _, replayed = asyncio.run(offline.embed_with_meta(["gamma", "delta", "alpha"], purpose="t"))
    assert replayed.cache_hit is True
    assert replayed.cost_usd == 0.0
    assert replayed.usage == live_mixed.usage
    assert replayed.priced_usd == pytest.approx(live_mixed.priced_usd)
    assert replayed.api_latency_s == pytest.approx(live_mixed.api_latency_s)
    assert replayed.request_hash == live_mixed.request_hash


def test_dimensions_are_sent_and_cached_separately(
    make_client: MakeClient, fake_api: FakeAPI
) -> None:
    client = make_client()
    fake_api.reply(embeddings_json([[0.6, 0.8]]))
    fake_api.reply(embeddings_json([[0.1, 0.2, 0.3]]))

    async def run() -> list[list[list[float]]]:
        return [
            await client.embed(["alpha"], purpose="t", dimensions=2),
            await client.embed(["alpha"], purpose="t"),
            await client.embed(["alpha"], purpose="t", dimensions=2),
        ]

    short, full, short_again = asyncio.run(run())
    assert [r.get("dimensions") for r in fake_api.requests] == [2, None]
    assert short == short_again == [pytest.approx([0.6, 0.8])]
    assert full == [pytest.approx([0.1, 0.2, 0.3])]
    with pytest.raises(CacheMiss):
        asyncio.run(make_client(offline=True).embed(["alpha"], purpose="t", dimensions=3))


@given(
    total=st.integers(0, 10_000),
    weights=st.lists(st.integers(1, 1_000), min_size=1, max_size=50),
)
def test_split_by_weight_sums_to_total_and_stays_proportional(
    total: int, weights: list[int]
) -> None:
    parts = split_by_weight(total, weights)
    assert sum(parts) == total
    assert all(abs(p - total * w / sum(weights)) < 1 for p, w in zip(parts, weights, strict=True))


def test_budget_abort_happens_before_any_request(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client(max_spend_usd=0.0001)
    with pytest.raises(BudgetExceeded):
        asyncio.run(ask(client, grammar))
    assert fake_api.requests == []
    assert client.budget.reserved_usd == 0.0


def test_cache_ledger_and_traces_hold_no_secret(
    make_client: MakeClient,
    fake_api: FakeAPI,
    grammar: SqlGrammar,
    settings: Settings,
    trace_run: Path,
) -> None:
    fake_api.reply(response_json([tool_call_item(SQL)]))
    asyncio.run(ask(make_client(), grammar))

    with sqlite3.connect(settings.cache_dir / "responses.sqlite") as db:
        payloads = [
            zlib.decompress(row[0]).decode() for row in db.execute("SELECT payload FROM responses")
        ]
    assert len(payloads) == 1
    stored = json.loads(payloads[0])
    assert stored["output"][1]["input"] == SQL
    for text in (*payloads, settings.ledger_path.read_text(), trace_run.read_text()):
        assert API_KEY not in text
        assert "authorization" not in text.lower()
    assert API_KEY.encode() not in (settings.cache_dir / "responses.sqlite").read_bytes()


def test_each_call_writes_a_span_with_usage_and_cost(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, trace_run: Path
) -> None:
    client = make_client()
    fake_api.reply(response_json([tool_call_item(SQL)]))

    async def run() -> None:
        await ask(client, grammar)
        await ask(client, grammar)

    asyncio.run(run())
    spans = [json.loads(line) for line in trace_run.read_text().splitlines()]
    calls = [s for s in spans if s["name"] == "llm.responses"]
    assert [s["attributes"]["cache_hit"] for s in calls] == [False, True]
    first = calls[0]
    assert first["attributes"]["model"] == "gpt-6-luna"
    assert first["attributes"]["input_tokens"] == 1200
    assert first["attributes"]["cost_usd"] > 0
    assert calls[1]["attributes"]["cost_usd"] == 0
    assert first["status"] == {"code": "OK"}
    assert first["resource"]["run.id"] == "test-run"
    assert first["end_time_unix_nano"] >= first["start_time_unix_nano"]
