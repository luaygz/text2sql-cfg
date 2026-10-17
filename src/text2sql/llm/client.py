"""Async OpenAI client: grammar-constrained SQL calls, structured outputs and embeddings.

Every Responses call takes the same path: response cache, then (offline: CacheMiss) the
concurrency semaphore, a budget reservation, the retry loop, the cache write, pricing, a
spend-ledger row, and a trace span with a matching log event. Callers never see an SDK object
that has not been cached first, so an offline replay returns exactly what a live run saw.

Requests are built to be reproducible. They carry no ids that change between runs, and repair
turns replay only the `custom_tool_call` item (without its `ctc_` id), not reasoning items:
replaying reasoning would need `store` or encrypted reasoning content, both of which add tokens
and put opaque blobs into the cache key.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import openai
import structlog
from openai import AsyncOpenAI
from openai.types.responses import (
    Response,
    ResponseCustomToolCall,
    ResponseOutputMessage,
    ResponseOutputRefusal,
)
from pydantic import BaseModel, ValidationError

from text2sql.config import ReasoningEffort, Settings, get_settings
from text2sql.grammar import GrammarRejection, SqlGrammar, validate_grammar_offline
from text2sql.llm.budget import LedgerEntry, Reservation, RunBudget
from text2sql.llm.cache import (
    CachedEmbedding,
    CachedResponse,
    GrammarVerdict,
    canonical_json,
    embedding_key,
    embedding_request,
    request_key,
)
from text2sql.llm.pricing import load_prices
from text2sql.llm.retry import RetryPolicy
from text2sql.llm.shards import open_cache
from text2sql.llm.types import (
    CacheMiss,
    CallMeta,
    GrammarCallFailed,
    GrammarRejectedByAPI,
    Message,
    PricingError,
    PromptFlaggedError,
    SqlToolCall,
    Structured,
    StructuredCallFailed,
    Usage,
)
from text2sql.observability import AttributeValue, span

SQL_TOOL_NAME = "sql_query"
PROBE_PURPOSE = "grammar.probe"
_PROBE_MAX_OUTPUT_TOKENS = 16
# The embeddings API caps a request at 300,000 tokens summed over its inputs.
_EMBED_REQUEST_TOKEN_LIMIT = 250_000
_EMBEDDING_TIER = "default"

log = structlog.get_logger(__name__)
_valid_fingerprints: set[str] = set()


def message_item(message: Message) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "input_text", "text": message.text}
    if message.cache_breakpoint:
        block["prompt_cache_breakpoint"] = {"mode": "explicit"}
    return {"role": message.role, "content": [block]}


def sql_tool(definition: str, description: str) -> dict[str, Any]:
    return {
        "type": "custom",
        "name": SQL_TOOL_NAME,
        "description": description,
        "format": {"type": "grammar", "syntax": "lark", "definition": definition},
    }


def tool_output_item(call_id: str, output: str) -> dict[str, Any]:
    """The `custom_tool_call_output` input item that answers `call_id` in a repair turn."""
    return {"type": "custom_tool_call_output", "call_id": call_id, "output": output}


def json_schema_format(output: type[BaseModel]) -> dict[str, Any]:
    """Strict `text.format` for `output`, via the SDK's strict JSON-schema conversion (the same
    one `responses.parse` uses)."""
    schema = openai.pydantic_function_tool(output)["function"]["parameters"]
    return {"type": "json_schema", "name": output.__name__, "schema": dict(schema), "strict": True}


def estimate_input_tokens(request: Mapping[str, Any]) -> int:
    """Deliberately high token estimate for the budget check: UTF-8 bytes of the request JSON
    over two. English prose and SQL run near four bytes per token."""
    return len(canonical_json(request).encode()) // 2 + 1


def _estimate_text_tokens(texts: Sequence[str]) -> int:
    return sum(len(t.encode()) // 2 + 1 for t in texts)


def split_by_weight(total: int, weights: Sequence[int]) -> list[int]:
    """`total` in integer parts proportional to the positive `weights`, summing to `total`
    (largest remainder, ties to the earlier position)."""
    whole = sum(weights)
    divided = [divmod(total * w, whole) for w in weights]
    parts = [quotient for quotient, _ in divided]
    by_remainder = sorted(range(len(weights)), key=lambda i: -divided[i][1])
    for i in by_remainder[: total - sum(parts)]:
        parts[i] += 1
    return parts


def usage_of(response: Response) -> Usage:
    u = response.usage
    if u is None:
        raise PricingError(f"response {response.id} reports no usage")
    return Usage(
        input_tokens=u.input_tokens,
        cached_tokens=u.input_tokens_details.cached_tokens,
        cache_write_tokens=u.input_tokens_details.cache_write_tokens,
        output_tokens=u.output_tokens,
        reasoning_tokens=u.output_tokens_details.reasoning_tokens,
    )


def _refusal(response: Response) -> str | None:
    for item in response.output:
        if isinstance(item, ResponseOutputMessage):
            for part in item.content:
                if isinstance(part, ResponseOutputRefusal):
                    return part.refusal
    return None


def _incomplete_reason(response: Response) -> str | None:
    if response.status != "incomplete":
        return None
    details = response.incomplete_details
    return details.reason if details is not None and details.reason else "unknown"


def _provider_message(exc: openai.APIStatusError) -> str:
    """The API's own error text (`error.message`), without the SDK's status-code prefix."""
    body = exc.body
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return str(body["message"])
    return exc.message


def _is_grammar_rejection(exc: openai.BadRequestError) -> bool:
    return "grammar" in _provider_message(exc).lower()


def parse_sql_response(response: Response, grammar: SqlGrammar, meta: CallMeta) -> SqlToolCall:
    """The `sql_query` call in `response`, re-parsed locally; GrammarCallFailed otherwise.

    A response cut off by the output cap fails even when its tool input parses, because a
    truncated query can still be a valid, shorter query.
    """
    call = next(
        (
            item
            for item in response.output
            if isinstance(item, ResponseCustomToolCall) and item.name == SQL_TOOL_NAME
        ),
        None,
    )
    if call is None:
        history: tuple[dict[str, Any], ...] = ()
    else:
        replay = {"type": "custom_tool_call", "call_id": call.call_id, "name": call.name}
        history = ({**replay, "input": call.input},)
    if (reason := _incomplete_reason(response)) is not None:
        raise GrammarCallFailed(
            "incomplete",
            f"response incomplete ({reason})",
            meta=meta,
            raw_input=None if call is None else call.input,
            call_id=None if call is None else call.call_id,
            history_items=history,
        )
    if call is None:
        if (refusal := _refusal(response)) is not None:
            raise GrammarCallFailed("refusal", refusal, meta=meta, raw_input=refusal)
        kinds = sorted({item.type for item in response.output})
        raise GrammarCallFailed("no_tool_call", f"output item types {kinds}", meta=meta)
    try:
        output = grammar.parse(call.input)
    except GrammarRejection as exc:
        raise GrammarCallFailed(
            "local_parse",
            str(exc),
            meta=meta,
            raw_input=call.input,
            call_id=call.call_id,
            history_items=history,
        ) from exc
    return SqlToolCall(
        output=output,
        raw_input=call.input,
        call_id=call.call_id,
        history_items=history,
        meta=meta,
    )


def parse_structured[T: BaseModel](response: Response, output: type[T], meta: CallMeta) -> T:
    if (reason := _incomplete_reason(response)) is not None:
        raise StructuredCallFailed(
            "incomplete", reason, meta=meta, raw_text=response.output_text or None
        )
    if (refusal := _refusal(response)) is not None:
        raise StructuredCallFailed("refusal", refusal, meta=meta, raw_text=refusal)
    text = response.output_text
    try:
        return output.model_validate_json(text)
    except ValidationError as exc:
        raise StructuredCallFailed("invalid_json", str(exc), meta=meta, raw_text=text) from exc


def _embedding_batches(
    items: Sequence[tuple[str, str]], size: int
) -> Iterator[list[tuple[str, str]]]:
    batch: list[tuple[str, str]] = []
    tokens = 0
    for item in items:
        estimate = _estimate_text_tokens([item[1]])
        if batch and (len(batch) >= size or tokens + estimate > _EMBED_REQUEST_TOKEN_LIMIT):
            yield batch
            batch, tokens = [], 0
        batch.append(item)
        tokens += estimate
    if batch:
        yield batch


@dataclass(frozen=True)
class _Lookup:
    record: CachedResponse
    billed_usd: float | None
    """Cost of the API call that produced `record` in this process; None for a cache hit."""


class LLMClient:
    """One per run. Not safe to share across event loops."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        budget: RunBudget | None = None,
        openai_client: AsyncOpenAI | None = None,
        retry: RetryPolicy | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.budget = budget or RunBudget.from_settings(self.settings)
        self._prices = load_prices(self.settings.pricing_path)
        self._cache = open_cache(self.settings.cache_dir)
        self._retry = retry or RetryPolicy(max_retries=self.settings.max_retries)
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        self._openai = openai_client
        self._inflight: dict[str, asyncio.Task[_Lookup]] = {}

    async def sql_call(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        grammar: SqlGrammar,
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        history: Sequence[dict[str, Any]] = (),
        tool_description: str | None = None,
        max_output_tokens: int | None = None,
    ) -> SqlToolCall:
        """One forced `sql_query` call under `grammar`; the SQL is re-parsed locally.

        `history` items go after `messages` (for a repair turn: the previous call's
        `history_items` plus a `tool_output_item`). The tool description defaults to
        `grammar.description`. `max_output_tokens` overrides `Settings.max_output_tokens` for
        this call (part of the cache key and of the budget pre-check). Raises
        GrammarRejectedByAPI if the API refuses the grammar (now or in a recorded earlier call)
        and GrammarCallFailed for any other call without usable SQL, including one cut off by
        the output cap (reason "incomplete", still billed) and a prompt the API flags as a
        policy violation (reason "flagged", unbilled).
        """
        _validate_offline(grammar)
        items = [*map(message_item, messages), *history]
        request = self._request(model, items, effort, max_output_tokens)
        request |= self._sql_tool_fields(grammar, tool_description)
        verdict = self._cache.get_grammar_verdict(grammar.fingerprint)
        if verdict is not None and not verdict.accepted:
            key = request_key("responses", request, sample)
            meta = self._unbilled_meta(purpose, model, key, cache_hit=True)
            raise GrammarRejectedByAPI(
                verdict.message or "", fingerprint=grammar.fingerprint, meta=meta
            )
        try:
            response, meta = await self._respond(request, sample=sample, purpose=purpose)
        except PromptFlaggedError as exc:
            meta = self._unbilled_meta(purpose, model, exc.request_hash, cache_hit=exc.cache_hit)
            raise GrammarCallFailed("flagged", exc.message, meta=meta) from exc
        except openai.BadRequestError as exc:
            if not _is_grammar_rejection(exc):
                raise
            self._record_rejection(grammar, model, exc)
            key = request_key("responses", request, sample)
            raise GrammarRejectedByAPI(
                _provider_message(exc),
                fingerprint=grammar.fingerprint,
                meta=self._unbilled_meta(purpose, model, key, cache_hit=False),
            ) from exc
        return parse_sql_response(response, grammar, meta)

    async def grammar_accepted(
        self, grammar: SqlGrammar, *, model: str | None = None, effort: ReasoningEffort = "none"
    ) -> bool:
        """Whether the API compiles `grammar`, probed once per grammar fingerprint with a tiny
        forced call (default: the small model) and remembered in the response cache. The
        model must support `effort`."""
        verdict = self._cache.get_grammar_verdict(grammar.fingerprint)
        if verdict is not None:
            return verdict.accepted
        _validate_offline(grammar)
        probe_model = model or self.settings.small_model
        request = self._request(
            probe_model,
            [message_item(Message("user", "Probe."))],
            effort,
            _PROBE_MAX_OUTPUT_TOKENS,
        )
        request |= self._sql_tool_fields(grammar, None)
        try:
            await self._respond(request, sample=0, purpose=PROBE_PURPOSE)
        except openai.BadRequestError as exc:
            if not _is_grammar_rejection(exc):
                raise
            self._record_rejection(grammar, probe_model, exc)
            return False
        self._cache.put_grammar_verdict(
            grammar.fingerprint, GrammarVerdict(accepted=True, message=None, model=probe_model)
        )
        return True

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        max_output_tokens: int | None = None,
    ) -> Structured[T]:
        """A strict JSON-schema response parsed into `output`; StructuredCallFailed otherwise.

        `max_output_tokens` overrides `Settings.max_output_tokens` for this call. It is part of
        the cache key and caps the budget pre-check, so a small cap bounds what a runaway
        response (e.g. trailing whitespace after the JSON object) can cost."""
        items = [message_item(m) for m in messages]
        request = self._request(model, items, effort, max_output_tokens)
        request["text"] = {"format": json_schema_format(output)}
        try:
            response, meta = await self._respond(request, sample=sample, purpose=purpose)
        except PromptFlaggedError as exc:
            meta = self._unbilled_meta(purpose, model, exc.request_hash, cache_hit=exc.cache_hit)
            raise StructuredCallFailed("flagged", exc.message, meta=meta, raw_text=None) from exc
        return Structured(value=parse_structured(response, output, meta), meta=meta)

    async def embed(
        self, texts: Sequence[str], *, purpose: str, dimensions: int | None = None
    ) -> list[list[float]]:
        """Embeddings for `texts` in order; `embed_with_meta` without the accounting."""
        vectors, _ = await self.embed_with_meta(texts, purpose=purpose, dimensions=dimensions)
        return vectors

    async def embed_with_meta(
        self, texts: Sequence[str], *, purpose: str, dimensions: int | None = None
    ) -> tuple[list[list[float]], CallMeta]:
        """Embeddings for `texts` in order, each text cached on its own, plus one CallMeta for
        the call. `dimensions` shortens the vectors (text-embedding-3 models; the default is
        the model's full size) and is part of the cache key.

        `usage`, `priced_usd` and `api_latency_s` sum the stored shares of the distinct texts,
        so they are the same live and replayed. `cost_usd` is what this call billed, and
        `cache_hit` means it made no API call."""
        if any(not t for t in texts):
            raise ValueError("the embeddings API rejects empty strings")
        model = self.settings.embedding_model
        keys = [embedding_key(model, t, dimensions) for t in texts]
        request_hash = request_key("embeddings", embedding_request(model, texts, dimensions))
        started = time.perf_counter()
        with span(
            "llm.embeddings", purpose=purpose, model=model, request_hash=request_hash
        ) as trace:
            rows = self._cache.get_embeddings(keys)
            hits, hit_tokens = len(rows), sum(r.tokens for r in rows.values())
            missing = {k: t for k, t in zip(keys, texts, strict=True) if k not in rows}
            if missing and self.settings.offline:
                raise CacheMiss(next(iter(missing)), purpose)
            billed, calls = 0.0, 0
            for batch in _embedding_batches(
                list(missing.items()), self.settings.embedding_batch_size
            ):
                fetched, cost = await self._embed_batch(model, batch, purpose, dimensions)
                rows |= fetched
                billed, calls = billed + cost, calls + 1
            hit_usage = Usage(hit_tokens, 0, 0, 0, 0)
            self.budget.record_cache_hits(
                model, hits, self._prices.cost_usd(model, hit_usage, _EMBEDDING_TIER)
            )
            usage = Usage(sum(r.tokens for r in rows.values()), 0, 0, 0, 0)
            meta = CallMeta(
                purpose=purpose,
                model=model,
                request_hash=request_hash,
                usage=usage,
                cost_usd=billed,
                latency_s=time.perf_counter() - started,
                cache_hit=not missing,
                priced_usd=self._prices.cost_usd(model, usage, _EMBEDDING_TIER),
                api_latency_s=sum(r.api_latency_s for r in rows.values()),
                service_tier=_EMBEDDING_TIER,
            )
            fields: dict[str, AttributeValue] = {
                "cache_hit": meta.cache_hit,
                "texts": len(texts),
                "dimensions": dimensions,
                "cache_hits": hits,
                "api_calls": calls,
                "input_tokens": usage.input_tokens,
                "cost_usd": billed,
                "priced_usd": meta.priced_usd,
            }
            trace.set(**fields)
            log.info("llm.embeddings", purpose=purpose, model=model, **fields)
        return [rows[k].vector for k in keys], meta

    async def aclose(self) -> None:
        if self._openai is not None:
            await self._openai.close()
        self._cache.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _api(self) -> AsyncOpenAI:
        """The SDK client, built on first use so offline runs never need an API key."""
        if self._openai is None:
            key = self.settings.openai_api_key
            self._openai = AsyncOpenAI(
                api_key=None if key is None else key.get_secret_value(),
                timeout=self.settings.request_timeout_s,
                max_retries=0,
            )
        return self._openai

    def _request(
        self,
        model: str,
        items: list[dict[str, Any]],
        effort: ReasoningEffort,
        max_output_tokens: int | None,
    ) -> dict[str, Any]:
        """The common request fields; `max_output_tokens` None means the Settings default."""
        if max_output_tokens is not None and max_output_tokens < 1:
            raise ValueError(f"max_output_tokens must be positive, got {max_output_tokens}")
        cap = self.settings.max_output_tokens if max_output_tokens is None else max_output_tokens
        return {
            "model": model,
            "input": items,
            "reasoning": {"effort": effort},
            "max_output_tokens": cap,
            "service_tier": self.settings.service_tier,
            "prompt_cache_options": {"mode": "explicit"},
            "store": False,
        }

    @staticmethod
    def _sql_tool_fields(grammar: SqlGrammar, description: str | None) -> dict[str, Any]:
        return {
            "tools": [sql_tool(grammar.definition, description or grammar.description)],
            "tool_choice": {"type": "custom", "name": SQL_TOOL_NAME},
            "parallel_tool_calls": False,
        }

    def _record_rejection(
        self, grammar: SqlGrammar, model: str, exc: openai.BadRequestError
    ) -> None:
        message = _provider_message(exc)
        log.warning("llm.grammar_rejected", fingerprint=grammar.fingerprint, error=message)
        self._cache.put_grammar_verdict(
            grammar.fingerprint, GrammarVerdict(accepted=False, message=message, model=model)
        )

    def _unbilled_meta(self, purpose: str, model: str, key: str, *, cache_hit: bool) -> CallMeta:
        return CallMeta(
            purpose=purpose,
            model=model,
            request_hash=key,
            usage=Usage(0, 0, 0, 0, 0),
            cost_usd=0.0,
            latency_s=0.0,
            cache_hit=cache_hit,
            priced_usd=0.0,
            api_latency_s=0.0,
            service_tier=self.settings.service_tier,
        )

    async def _respond(
        self, request: dict[str, Any], *, sample: int, purpose: str
    ) -> tuple[Response, CallMeta]:
        key = request_key("responses", request, sample)
        model = str(request["model"])
        with span(
            "llm.responses", purpose=purpose, model=model, request_hash=key, sample=sample
        ) as trace:
            started = time.perf_counter()
            found = await self._lookup(key, request, purpose)
            response = Response.model_validate(found.record.payload)
            usage = usage_of(response)
            tier = response.service_tier or str(request["service_tier"])
            priced = self._prices.cost_usd(model, usage, tier)
            meta = CallMeta(
                purpose=purpose,
                model=model,
                request_hash=key,
                usage=usage,
                cost_usd=found.billed_usd or 0.0,
                latency_s=time.perf_counter() - started,
                cache_hit=found.billed_usd is None,
                priced_usd=priced,
                api_latency_s=found.record.api_latency_s,
                service_tier=tier,
            )
            if meta.cache_hit:
                self.budget.record_cache_hits(model, 1, priced)
            fields: dict[str, AttributeValue] = {
                "cache_hit": meta.cache_hit,
                "service_tier": tier,
                "input_tokens": usage.input_tokens,
                "cached_tokens": usage.cached_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
                "output_tokens": usage.output_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "cost_usd": meta.cost_usd,
                "priced_usd": priced,
                "status": response.status,
            }
            trace.set(**fields)
            log.info("llm.call", purpose=purpose, model=model, request_hash=key, **fields)
        return response, meta

    async def _lookup(self, key: str, request: dict[str, Any], purpose: str) -> _Lookup:
        """The cached response for `key`, fetching it if needed. Concurrent callers with the
        same key share one API call; only the first is billed. Raises PromptFlaggedError if
        the API refused this request, now or in a recorded earlier call."""
        record = self._cache.get_response(key)
        if record is not None:
            return _Lookup(record, None)
        flagged = self._cache.get_flagged(key)
        if flagged is not None:
            raise PromptFlaggedError(flagged, request_hash=key, cache_hit=True)
        if self.settings.offline:
            raise CacheMiss(key, purpose)
        pending = self._inflight.get(key)
        if pending is not None:
            return _Lookup((await pending).record, None)
        task = asyncio.create_task(self._fetch(key, request, purpose))
        self._inflight[key] = task
        try:
            return await task
        finally:
            del self._inflight[key]

    async def _fetch(self, key: str, request: dict[str, Any], purpose: str) -> _Lookup:
        model = str(request["model"])
        requested_tier = str(request["service_tier"])
        estimate = self._prices.max_cost_usd(
            model,
            input_tokens=estimate_input_tokens(request),
            output_tokens=int(request["max_output_tokens"]),
            service_tier=requested_tier,
        )
        async with self._semaphore:
            # Reserve only once a slot is free, so queued calls do not hold budget.
            reservation = self.budget.reserve(estimate, purpose=purpose)
            started = time.perf_counter()
            try:
                response: Response = await self._retry.run(
                    lambda: self._api().responses.create(**request), purpose=purpose
                )
            except openai.BadRequestError as exc:
                self.budget.release(reservation)
                if exc.code != "invalid_prompt":
                    raise
                message = _provider_message(exc)
                log.warning("llm.prompt_flagged", purpose=purpose, request_hash=key, error=message)
                self._cache.put_flagged(key, model=model, message=message)
                raise PromptFlaggedError(message, request_hash=key, cache_hit=False) from exc
            except BaseException:
                self.budget.release(reservation)
                raise
            latency = time.perf_counter() - started
        record = self._cache.put_response(
            key,
            model=model,
            payload=response.model_dump(mode="json", by_alias=True),
            api_latency_s=latency,
        )
        usage = usage_of(response)
        tier = response.service_tier or requested_tier
        cost = self._prices.cost_usd(model, usage, tier)
        self._charge(
            reservation,
            purpose=purpose,
            model=model,
            tier=tier,
            usage=usage,
            cost=cost,
            latency=latency,
            key=key,
        )
        return _Lookup(record, cost)

    async def _embed_batch(
        self,
        model: str,
        batch: Sequence[tuple[str, str]],
        purpose: str,
        dimensions: int | None,
    ) -> tuple[dict[str, CachedEmbedding], float]:
        """Fetch, store and bill one batch; returns the stored rows and the billed cost."""
        inputs = [text for _, text in batch]
        estimate = self._prices.max_cost_usd(
            model,
            input_tokens=_estimate_text_tokens(inputs),
            output_tokens=0,
            service_tier=_EMBEDDING_TIER,
        )
        async with self._semaphore:
            reservation = self.budget.reserve(estimate, purpose=purpose)
            started = time.perf_counter()
            try:
                result = await self._retry.run(
                    lambda: self._api().embeddings.create(
                        model=model,
                        input=inputs,
                        dimensions=openai.omit if dimensions is None else dimensions,
                    ),
                    purpose=purpose,
                )
            except BaseException:
                self.budget.release(reservation)
                raise
            latency = time.perf_counter() - started
        tokens = result.usage.prompt_tokens
        weights = [len(text.encode()) for text in inputs]
        shares = split_by_weight(tokens, weights)
        rows = {
            batch[d.index][0]: CachedEmbedding(
                d.embedding, shares[d.index], latency * weights[d.index] / sum(weights)
            )
            for d in result.data
        }
        stored = self._cache.put_embeddings(model, rows)
        usage = Usage(tokens, 0, 0, 0, 0)
        cost = self._prices.cost_usd(model, usage, _EMBEDDING_TIER)
        self._charge(
            reservation,
            purpose=purpose,
            model=model,
            tier=_EMBEDDING_TIER,
            usage=usage,
            cost=cost,
            latency=latency,
            key=request_key("embeddings", embedding_request(model, inputs, dimensions)),
        )
        return stored, cost

    def _charge(
        self,
        reservation: Reservation,
        *,
        purpose: str,
        model: str,
        tier: str,
        usage: Usage,
        cost: float,
        latency: float,
        key: str,
    ) -> None:
        entry = LedgerEntry(
            run_id=self.budget.run_id,
            phase=self.budget.phase,
            purpose=purpose,
            model=model,
            service_tier=tier,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            cost_usd=cost,
            latency_s=latency,
            request_hash=key,
        )
        self.budget.charge(reservation, entry)


def _validate_offline(grammar: SqlGrammar) -> None:
    """Offline grammar validation, once per fingerprint per process."""
    if grammar.fingerprint not in _valid_fingerprints:
        validate_grammar_offline(grammar.definition)
        _valid_fingerprints.add(grammar.fingerprint)
