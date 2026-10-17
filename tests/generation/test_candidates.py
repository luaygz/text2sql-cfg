"""Candidate calls, repair turns and the grammar-off ablation against a recording fake client."""

from __future__ import annotations

import asyncio

import pytest
from generation_fakes import FakeLLM, context

from text2sql.config import QueryMode
from text2sql.generation import (
    STRATEGIES,
    SqlAnswer,
    build_messages,
    generate_candidate,
    generate_json_candidate,
    repair_candidate,
    repair_feedback,
)
from text2sql.generation.prompting import json_messages
from text2sql.llm import tool_output_item

FIRST = "SELECT MAX(T1.total) FROM orders AS T1 WHERE T1.total > 0"
SECOND = "SELECT T1.total FROM orders AS T1 ORDER BY T1.total DESC LIMIT 1"
THIRD = "SELECT MAX(T1.total) FROM orders AS T1"


def test_candidate_uses_its_view_grammar_effort_and_sample() -> None:
    llm = FakeLLM(tool_inputs=[FIRST])
    ctx = context()
    spec = STRATEGIES["direct_linked_fewshot"]
    call = asyncio.run(generate_candidate(llm, spec, ctx, model="gen", sample=2))
    (request,) = llm.requests
    assert request["grammar"] is ctx.grammars["linked"]
    assert request["messages"] == build_messages(spec, ctx)
    assert (request["model"], request["effort"], request["sample"]) == ("gen", spec.effort, 2)
    assert request["history"] == []
    assert request["tool_description"] is None  # the client sends grammar.description
    assert request["purpose"] == (
        "generate.direct_linked_fewshot[generate_direct@1.0,generate_common@1.2]"
    )
    assert call.output.kind == "sql"
    assert call.output.text == FIRST


def test_repair_continues_the_candidate_conversation() -> None:
    llm = FakeLLM(tool_inputs=[FIRST, SECOND, THIRD])
    ctx = context()
    spec = STRATEGIES["divide_conquer"]
    first = asyncio.run(generate_candidate(llm, spec, ctx, model="gen", sample=1))
    note1 = repair_feedback(kind="empty", detail="")
    second = asyncio.run(repair_candidate(llm, spec, ctx, first, note1, model="gen", attempt=1))
    note2 = repair_feedback(kind="error", detail="no such column: T1.totl")
    third = asyncio.run(repair_candidate(llm, spec, ctx, second, note2, model="gen", attempt=2))

    _, repair1, repair2 = llm.requests
    for request in (repair1, repair2):
        assert request["messages"] == build_messages(spec, ctx)
        assert request["grammar"] is ctx.grammars["full"]
        assert request["effort"] == spec.effort
    ask = {"role": "user", "content": [{"type": "input_text", "text": "Call `sql_query` again."}]}
    assert repair1["history"] == [*first.history_items, tool_output_item(first.call_id, note1), ask]
    assert repair2["history"] == [
        *first.history_items,
        tool_output_item(first.call_id, note1),
        ask,
        *second.history_items[-1:],
        tool_output_item(second.call_id, note2),
        ask,
    ]
    assert repair2["history"][3]["input"] == SECOND
    assert repair1["purpose"].startswith("repair.divide_conquer#1[repair@1.2,")
    assert repair2["purpose"].startswith("repair.divide_conquer#2[repair@1.2,")
    assert third.output.text == THIRD
    assert third.history_items == (*repair2["history"], third.history_items[-1])
    assert third.history_items[-1]["call_id"] == third.call_id


def test_repair_attempts_count_from_one() -> None:
    llm = FakeLLM(tool_inputs=[FIRST])
    spec = STRATEGIES["query_plan"]
    first = asyncio.run(generate_candidate(llm, spec, context(), model="gen", sample=0))
    with pytest.raises(ValueError, match="count from 1"):
        asyncio.run(repair_candidate(llm, spec, context(), first, "x", model="gen", attempt=0))
    assert len(llm.requests) == 1


def test_abstention_comes_back_as_an_abstain_output() -> None:
    llm = FakeLLM(tool_inputs=["ABSTAIN: the database holds no salaries"])
    ctx = context(QueryMode.TENANT, allow_abstain=True, max_rows=200)
    call = asyncio.run(generate_candidate(llm, STRATEGIES["direct_full"], ctx, model="g", sample=0))
    assert (call.output.kind, call.output.text) == ("abstain", "the database holds no salaries")


def test_json_candidate_is_structured_output_on_the_same_prompt() -> None:
    llm = FakeLLM(structured_replies=[SqlAnswer(sql=f"  {FIRST};\n")])
    ctx = context()
    spec = STRATEGIES["query_plan"]
    sql, meta = asyncio.run(generate_json_candidate(llm, spec, ctx, model="gen", sample=3))
    (request,) = llm.requests
    assert request["kind"] == "structured"
    assert request["output"] is SqlAnswer
    assert request["messages"] == json_messages(spec, ctx)
    assert (request["effort"], request["sample"]) == (spec.effort, 3)
    assert request["purpose"].startswith("generate_json.query_plan[")
    assert sql == f"{FIRST};"  # not rewritten: the guard sees what the model wrote
    assert meta.purpose == request["purpose"]
