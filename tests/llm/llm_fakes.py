"""Canned Responses API payloads and a scripted fake OpenAI transport for the LLM tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx2

API_KEY = "sk-test-not-a-real-key-7f3a9c"


def usage_json(
    input_tokens: int = 1200,
    cached: int = 0,
    written: int = 0,
    output: int = 40,
    reasoning: int = 16,
) -> dict[str, Any]:
    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": written},
        "output_tokens": output,
        "output_tokens_details": {"reasoning_tokens": reasoning},
        "total_tokens": input_tokens + output,
    }


def tool_call_item(sql: str, call_id: str = "call_abc") -> dict[str, Any]:
    return {
        "type": "custom_tool_call",
        "id": "ctc_1",
        "call_id": call_id,
        "name": "sql_query",
        "input": sql,
    }


def message_output(text: str | None = None, refusal: str | None = None) -> dict[str, Any]:
    part = (
        {"type": "refusal", "refusal": refusal}
        if refusal is not None
        else {"type": "output_text", "text": text, "annotations": []}
    )
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [part],
    }


def response_json(
    output: list[dict[str, Any]],
    *,
    usage: dict[str, Any] | None = None,
    status: str = "completed",
    service_tier: str = "flex",
    model: str = "gpt-6-luna",
    incomplete_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1760000000,
        "model": model,
        "status": status,
        "incomplete_details": None if incomplete_reason is None else {"reason": incomplete_reason},
        "output": [{"type": "reasoning", "id": "rs_1", "summary": []}, *output],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "service_tier": service_tier,
        "usage": usage or usage_json(),
    }


def embeddings_json(vectors: list[list[float]], tokens: int = 10) -> dict[str, Any]:
    return {
        "object": "list",
        "model": "text-embedding-3-small",
        "data": [
            {"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)
        ],
        "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
    }


@dataclass
class FakeAPI:
    """Pops one scripted reply per request (an httpx2.Response or an exception to raise) and
    records each request body and how many requests were in flight at once."""

    replies: list[httpx2.Response | Exception] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    delay_s: float = 0.0
    in_flight: int = 0
    max_in_flight: int = 0

    def reply(self, body: dict[str, Any], status: int = 200, **headers: str) -> None:
        self.replies.append(httpx2.Response(status, json=body, headers=headers))

    def error(
        self,
        status: int,
        message: str,
        *,
        code: str | None = None,
        type_: str = "error",
        param: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = {"error": {"message": message, "type": type_, "param": param, "code": code}}
        self.reply(body, status, **(headers or {}))

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        self.paths.append(request.url.path)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay_s)
            reply = self.replies.pop(0)
        finally:
            self.in_flight -= 1
        if isinstance(reply, Exception):
            raise reply
        return reply
