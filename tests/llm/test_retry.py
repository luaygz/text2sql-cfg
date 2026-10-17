from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx2
import openai
import pytest
from llm_fakes import FakeAPI, response_json, tool_call_item

from text2sql.grammar import SqlGrammar
from text2sql.llm import LLMClient, Message, SqlToolCall
from text2sql.llm.retry import RetryPolicy, parse_duration

POLICY = RetryPolicy(max_retries=4, base_delay_s=1.0, max_delay_s=8.0, max_server_delay_s=120.0)
REQUEST = httpx2.Request("POST", "http://fake.openai.test/v1/responses")


def status_error(
    status: int, headers: dict[str, str] | None = None, code: str | None = None
) -> openai.APIStatusError:
    response = httpx2.Response(status, headers=headers or {}, request=REQUEST)
    body = {"message": "x", "type": "error", "code": code}
    classes: dict[int, type[openai.APIStatusError]] = {
        400: openai.BadRequestError,
        429: openai.RateLimitError,
        500: openai.InternalServerError,
        503: openai.InternalServerError,
    }
    return classes.get(status, openai.APIStatusError)("x", response=response, body=body)


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("1s", 1.0),
        ("6m0s", 360.0),
        ("250ms", 0.25),
        ("1h2m3.5s", 3723.5),
        ("soon", None),
        ("", None),
    ],
)
def test_parse_duration(text: str, seconds: float | None) -> None:
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    ("headers", "minimum"),
    [
        ({"retry-after-ms": "1500"}, 1.5),
        ({"retry-after": "7"}, 7.0),
        ({"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "20s"}, 20.0),
    ],
)
def test_server_hints_are_a_minimum_wait(headers: dict[str, str], minimum: float) -> None:
    delay = POLICY.delay_for(status_error(429, headers), attempt=0)
    assert delay is not None
    assert minimum <= delay <= minimum + POLICY.base_delay_s


def test_reset_header_of_a_bucket_that_is_not_exhausted_is_ignored() -> None:
    headers = {"x-ratelimit-remaining-tokens": "500", "x-ratelimit-reset-tokens": "6m0s"}
    delay = POLICY.delay_for(status_error(429, headers), attempt=0)
    assert delay is not None
    assert delay <= POLICY.base_delay_s


@pytest.mark.parametrize("attempt", [0, 1, 2, 3])
def test_backoff_grows_exponentially_with_jitter_and_a_ceiling(attempt: int) -> None:
    ceiling = min(POLICY.max_delay_s, POLICY.base_delay_s * 2**attempt)
    delays = [POLICY.delay_for(status_error(500), attempt) for _ in range(50)]
    assert all(d is not None and ceiling / 2 <= d <= ceiling for d in delays)
    assert len(set(delays)) > 1


@pytest.mark.parametrize(
    "exc",
    [
        status_error(400),
        status_error(429, code="insufficient_quota"),
        status_error(429, code="credit_balance_exhausted"),
        status_error(429, {"retry-after": "600"}),
        ValueError("not an API error"),
    ],
    ids=["bad-request", "quota", "credits", "hint-too-long", "other"],
)
def test_final_errors_are_not_retried(exc: BaseException) -> None:
    assert POLICY.delay_for(exc, attempt=0) is None


def test_transient_errors_are_retried_until_the_limit() -> None:
    timeout = openai.APITimeoutError(request=REQUEST)
    for exc in (timeout, status_error(503), status_error(429)):
        assert POLICY.delay_for(exc, attempt=3) is not None
        assert POLICY.delay_for(exc, attempt=4) is None


async def ask(client: LLMClient, grammar: SqlGrammar) -> SqlToolCall:
    return await client.sql_call(
        model="gpt-6-luna",
        messages=[Message("user", "names of singers")],
        grammar=grammar,
        effort="low",
        purpose="test.retry",
    )


def test_client_retries_429_500_and_timeouts_then_bills_once(
    make_client: Callable[..., LLMClient], fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    fake_api.error(429, "Resource unavailable", headers={"retry-after-ms": "1"})
    fake_api.error(500, "boom")
    fake_api.replies.append(httpx2.ReadTimeout("slow", request=REQUEST))
    fake_api.reply(response_json([tool_call_item("SELECT name FROM singer")]))

    result = asyncio.run(ask(client, grammar))

    assert result.output.text == "SELECT name FROM singer"
    assert len(fake_api.requests) == 4
    assert len(list(client.budget.ledger.entries())) == 1
    assert client.budget.reserved_usd == 0.0


def test_exhausted_retries_raise_and_release_the_reservation(
    make_client: Callable[..., LLMClient], fake_api: FakeAPI, grammar: SqlGrammar
) -> None:
    client = make_client()
    for _ in range(4):
        fake_api.error(503, "overloaded", headers={"retry-after-ms": "1"})

    with pytest.raises(openai.InternalServerError):
        asyncio.run(ask(client, grammar))

    assert len(fake_api.requests) == 4  # first attempt plus max_retries=3
    assert list(client.budget.ledger.entries()) == []
    assert client.budget.reserved_usd == 0.0
    assert client.budget.spent_usd == 0.0
