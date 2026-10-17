"""Value types and errors shared by the LLM client, cache, pricing and budget modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from text2sql.grammar import GrammarOutput


@dataclass(frozen=True)
class Message:
    """One input message. `cache_breakpoint` marks the end of a reusable prompt-cache prefix."""

    role: Literal["developer", "user"]
    text: str
    cache_breakpoint: bool = False


@dataclass(frozen=True)
class Usage:
    """Token counts as the API reports them. `input_tokens` includes cached and cache-write
    tokens; `output_tokens` includes reasoning tokens."""

    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int


@dataclass(frozen=True)
class CallMeta:
    """Accounting for one logical call.

    `cost_usd` is money billed by this call: 0 on a cache hit. `priced_usd` is the list-price
    cost of the response's usage at the tier that served it, the same live or replayed, so
    offline reports can reproduce cost per question. Likewise `latency_s` is this call's wall
    time and `api_latency_s` the latency of the API call that produced the response.
    """

    purpose: str
    model: str
    request_hash: str
    usage: Usage
    cost_usd: float
    latency_s: float
    cache_hit: bool
    priced_usd: float
    api_latency_s: float
    service_tier: str


@dataclass(frozen=True)
class SqlToolCall:
    output: GrammarOutput
    raw_input: str
    call_id: str
    history_items: tuple[dict[str, Any], ...]
    """Items to replay before a `tool_output_item` in a repair turn."""
    meta: CallMeta


@dataclass(frozen=True)
class Structured[T]:
    value: T
    meta: CallMeta


GrammarFailure = Literal[
    "no_tool_call", "refusal", "incomplete", "local_parse", "api_rejected", "flagged"
]
StructuredFailure = Literal["refusal", "incomplete", "invalid_json", "flagged"]


# The shared interface contract fixes these exception names (StructuredCallFailed follows suit),
# hence the N818 waivers.
class GrammarCallFailed(Exception):  # noqa: N818
    """The API returned no usable `sql_query` tool call, or its input failed the local re-parse.

    `raw_input` is the tool input (or refusal text) when there was one; `history_items` and
    `call_id` are set when a tool call exists, so a repair turn can answer it. Reason "flagged"
    means the API refused the prompt itself (see PromptFlaggedError); its meta is unbilled.
    """

    def __init__(
        self,
        reason: GrammarFailure,
        detail: str,
        *,
        meta: CallMeta,
        raw_input: str | None = None,
        call_id: str | None = None,
        history_items: tuple[dict[str, Any], ...] = (),
    ) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: GrammarFailure = reason
        self.detail = detail
        self.meta = meta
        self.raw_input = raw_input
        self.call_id = call_id
        self.history_items = history_items


class GrammarRejectedByAPI(GrammarCallFailed):
    """The API refused the grammar itself (HTTP 400 on `tools`), e.g. "regex construction fuel
    exhausted", although it passed offline validation. Not retried and not billed; every call
    with this grammar will fail the same way. `provider_message` is the API's error text."""

    def __init__(self, provider_message: str, *, fingerprint: str, meta: CallMeta) -> None:
        super().__init__("api_rejected", provider_message, meta=meta)
        self.provider_message = provider_message
        self.fingerprint = fingerprint


class StructuredCallFailed(Exception):  # noqa: N818
    """A structured-output call returned a refusal, was cut off, did not match the schema, or
    the API refused the prompt (reason "flagged", unbilled meta)."""

    def __init__(
        self, reason: StructuredFailure, detail: str, *, meta: CallMeta, raw_text: str | None
    ) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: StructuredFailure = reason
        self.detail = detail
        self.meta = meta
        self.raw_text = raw_text


class BudgetExceeded(Exception):  # noqa: N818
    """Making the next call could push spend past the per-run or lifetime cap."""


class CacheMiss(Exception):  # noqa: N818
    """Offline mode found no cached response for a request."""

    def __init__(self, request_hash: str, purpose: str) -> None:
        super().__init__(f"no cached response for {purpose} (request {request_hash[:12]})")
        self.request_hash = request_hash
        self.purpose = purpose


class PromptFlaggedError(Exception):
    """The API refused the request with HTTP 400 `invalid_prompt` ("flagged as potentially
    violating our usage policy"). The verdict is recorded per request key like a response, so
    reruns and offline replays see the same outcome; a new `sample` index asks again.
    `sql_call` and `structured` turn this into their "flagged" failure."""

    def __init__(self, message: str, *, request_hash: str, cache_hit: bool) -> None:
        super().__init__(message)
        self.message = message
        self.request_hash = request_hash
        self.cache_hit = cache_hit


class PricingError(Exception):
    """A model is missing from config/pricing.yaml, or usage does not fit its rates."""
