"""A recording stand-in for `LLMClient` and a small schema to build real grammars from."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from text2sql.catalog.schema import Column, DatabaseSchema, ForeignKey, Table
from text2sql.config import QueryMode, ReasoningEffort
from text2sql.generation import GenerationContext, SchemaView
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar
from text2sql.llm import CallMeta, Message, SqlToolCall, Structured, Usage
from text2sql.retrieval import FewShotExample

SCHEMA = DatabaseSchema(
    db_id="shop",
    tables=(
        Table("customers", (Column("id", "INTEGER", primary_key=True), Column("city", "TEXT"))),
        Table(
            "orders",
            (
                Column("id", "INTEGER", primary_key=True),
                Column("customer_id", "INTEGER"),
                Column("total", "REAL"),
            ),
        ),
    ),
    foreign_keys=(ForeignKey("orders", "customer_id", "customers", "id"),),
)
LINKED = SCHEMA.subset({"orders": frozenset({"id", "total"})})

FULL_TEXT = "【DB_ID】 shop\n【Schema】\n# Table: customers\n# Table: orders"
LINKED_TEXT = "【DB_ID】 shop\n【Schema】\n# Table: orders (linked)"


def grammars(
    mode: QueryMode, *, allow_abstain: bool = False, max_rows: int = 1000
) -> dict[SchemaView, SqlGrammar]:
    options = GrammarOptions(mode=mode, max_rows=max_rows, allow_abstain=allow_abstain)
    return {"full": build_grammar(SCHEMA, options), "linked": build_grammar(LINKED, options)}


def context(
    mode: QueryMode = QueryMode.BENCHMARK,
    *,
    allow_abstain: bool = False,
    max_rows: int = 1000,
    question: str = "What is the largest order total?",
    evidence: str | None = "largest refers to MAX(total)",
    matched: str = "【Matched values】\ncustomers.city: 'Paris'",
    fewshots: Sequence[FewShotExample] = (
        FewShotExample("How many singers?", None, "SELECT COUNT(*) FROM singer AS T1"),
    ),
    requested_outputs: Sequence[str] = ("order total",),
) -> GenerationContext:
    return GenerationContext(
        db_id="shop",
        question=question,
        evidence=evidence,
        mode=mode,
        schema_text={"full": FULL_TEXT, "linked": LINKED_TEXT},
        grammars=grammars(mode, allow_abstain=allow_abstain, max_rows=max_rows),
        matched_values_text=matched,
        fewshots=fewshots,
        requested_outputs=requested_outputs,
    )


def meta(purpose: str, model: str) -> CallMeta:
    return CallMeta(
        purpose=purpose,
        model=model,
        request_hash="hash",
        usage=Usage(100, 0, 0, 10, 5),
        cost_usd=0.001,
        latency_s=0.1,
        cache_hit=False,
        priced_usd=0.001,
        api_latency_s=0.1,
        service_tier="flex",
    )


@dataclass
class FakeLLM:
    """Answers each `sql_call` with the next scripted tool input (re-parsed by the real grammar)
    and each `structured` call with the next scripted object; records every request."""

    tool_inputs: list[str] = field(default_factory=list)
    structured_replies: list[BaseModel] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)

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
    ) -> SqlToolCall:
        self.requests.append(
            {
                "kind": "sql",
                "model": model,
                "messages": list(messages),
                "grammar": grammar,
                "effort": effort,
                "purpose": purpose,
                "sample": sample,
                "history": list(history),
                "tool_description": tool_description,
            }
        )
        text = self.tool_inputs.pop(0)
        call_id = f"call_{len(self.requests)}"
        item = {"type": "custom_tool_call", "call_id": call_id, "name": "sql_query", "input": text}
        return SqlToolCall(
            output=grammar.parse(text),
            raw_input=text,
            call_id=call_id,
            history_items=(item,),
            meta=meta(purpose, model),
        )

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
    ) -> Structured[T]:
        self.requests.append(
            {
                "kind": "structured",
                "model": model,
                "messages": list(messages),
                "output": output,
                "effort": effort,
                "purpose": purpose,
                "sample": sample,
            }
        )
        reply = self.structured_replies.pop(0)
        assert isinstance(reply, output)
        return Structured(value=reply, meta=meta(purpose, model))
