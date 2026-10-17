"""Grammar-tool candidates, repair turns, and the grammar-off ablation (ADR-012)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from text2sql.config import ReasoningEffort
from text2sql.generation.prompting import (
    GenerationContext,
    build_messages,
    json_messages,
    purpose,
    repair_turn,
)
from text2sql.generation.strategies import StrategySpec
from text2sql.grammar import SqlGrammar
from text2sql.llm import CallMeta, Message, SqlToolCall, Structured


class GenerationLLM(Protocol):
    """The part of `text2sql.llm.LLMClient` this module uses."""

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
    ) -> SqlToolCall: ...

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
    ) -> Structured[T]: ...


async def generate_candidate(
    llm: GenerationLLM,
    spec: StrategySpec,
    ctx: GenerationContext,
    *,
    model: str,
    sample: int,
) -> SqlToolCall:
    """One forced `sql_query` call. Raises the client's GrammarCallFailed when the response
    holds no usable tool call."""
    return await llm.sql_call(
        model=model,
        messages=build_messages(spec, ctx),
        grammar=ctx.grammar(spec.schema_view),
        effort=spec.effort,
        purpose=purpose("generate", spec),
        sample=sample,
    )


async def repair_candidate(
    llm: GenerationLLM,
    spec: StrategySpec,
    ctx: GenerationContext,
    previous: SqlToolCall,
    feedback: str,
    *,
    model: str,
    attempt: int,
) -> SqlToolCall:
    """Continue the candidate's own conversation: the same messages, its earlier tool calls,
    outputs and repair turns, then `feedback` (see `repair_feedback`) as the output of
    `previous`, a short user message asking for the call, and a new forced `sql_query` call.
    The caller enforces the repair limit.

    The returned call's `history_items` hold the whole exchange so far, so a second repair
    passes the first repair's result as `previous`.
    """
    if attempt < 1:
        raise ValueError(f"repair attempts count from 1, got {attempt}")
    history = (*previous.history_items, *repair_turn(previous.call_id, feedback))
    repaired = await llm.sql_call(
        model=model,
        messages=build_messages(spec, ctx),
        grammar=ctx.grammar(spec.schema_view),
        effort=spec.effort,
        purpose=purpose("repair", spec, attempt=attempt),
        history=history,
    )
    return replace(repaired, history_items=(*history, *repaired.history_items))


class SqlAnswer(BaseModel):
    """Structured output of the grammar-off ablation."""

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(description="The complete final SQLite query.")


async def generate_json_candidate(
    llm: GenerationLLM,
    spec: StrategySpec,
    ctx: GenerationContext,
    *,
    model: str,
    sample: int,
) -> tuple[str, CallMeta]:
    """ABLATION ONLY ("grammar off"): the same prompt answered as JSON with an `sql` field,
    with no grammar constraint. Production paths must use `generate_candidate`; the caller has
    to send this SQL through the same guard minus layer 1 (the grammar re-parse), and record
    that it did. The text is returned as the model wrote it apart from outer whitespace."""
    answer = await llm.structured(
        model=model,
        messages=json_messages(spec, ctx),
        output=SqlAnswer,
        effort=spec.effort,
        purpose=purpose("generate_json", spec),
        sample=sample,
    )
    return answer.value.sql.strip(), answer.meta
