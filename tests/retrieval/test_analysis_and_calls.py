from __future__ import annotations

import asyncio
from collections.abc import Sequence

import numpy as np
import pytest
from pydantic import BaseModel
from retrieval_fakes import FakeLLM, analysis, meta

from text2sql.llm import Message, StructuredCallFailed
from text2sql.prompts import load_prompt
from text2sql.retrieval.analysis import MAX_OUTPUT_TOKENS, PROMPT, analyze_question
from text2sql.retrieval.calls import embed, structured_call, unit_rows
from text2sql.retrieval.types import QuestionAnalysis


def _reply(value: QuestionAnalysis) -> FakeLLM:
    return FakeLLM(lambda output, messages: value)


def test_analysis_sends_cached_instructions_then_question_and_evidence() -> None:
    llm = _reply(analysis(literals=["Alameda"]))
    result = asyncio.run(
        analyze_question(
            llm,
            question="How many schools are in Alameda?",
            evidence="Alameda refers to County = 'Alameda'",
            model="small",
            effort="none",
        )
    )
    assert result.value.literals == ["Alameda"]
    ((developer, user),) = [messages for messages, _, _ in llm.structured_calls]
    assert developer.role == "developer" and developer.cache_breakpoint
    assert "skeleton" in developer.text and "Alameda" not in developer.text
    assert user.role == "user" and not user.cache_breakpoint
    assert "How many schools are in Alameda?" in user.text
    assert "County = 'Alameda'" in user.text
    _, effort, purpose = llm.structured_calls[0]
    assert effort == "none" and load_prompt(PROMPT).tag in purpose
    assert llm.output_caps == [MAX_OUTPUT_TOKENS]


@pytest.mark.parametrize("evidence", [None, "", "   "])
def test_missing_evidence_is_stated_not_left_blank(evidence: str | None) -> None:
    llm = _reply(analysis())
    asyncio.run(analyze_question(llm, question="Q?", evidence=evidence, model="m", effort="none"))
    user = llm.structured_calls[0][0][1]
    assert "Evidence: (none)" in user.text


def test_question_containing_template_syntax_is_passed_verbatim() -> None:
    llm = _reply(analysis())
    question = "Price above $100 and ${amount}?"
    asyncio.run(analyze_question(llm, question=question, evidence=None, model="m", effort="none"))
    assert question in llm.structured_calls[0][0][1].text


class _Pick(BaseModel):
    tables: list[str]


def _failing(reason: str, raw_text: str | None) -> FakeLLM:
    error = StructuredCallFailed(reason, "cut off", meta=meta("x", 0.5), raw_text=raw_text)  # type: ignore[arg-type]
    return FakeLLM(lambda output, messages: error)


def _call(llm: FakeLLM) -> _Pick:
    messages: Sequence[Message] = [Message("user", "q")]
    result = asyncio.run(
        structured_call(
            llm,
            model="m",
            messages=messages,
            output=_Pick,
            effort="none",
            purpose="p",
            max_output_tokens=10,
        )
    )
    assert result.meta.cost_usd == 0.5  # the cut-off call is still accounted for
    return result.value


def test_complete_object_before_a_runaway_tail_is_recovered() -> None:
    assert _call(_failing("incomplete", '{"tables": ["a"]}\n}\n}\n}')).tables == ["a"]


@pytest.mark.parametrize(
    ("reason", "raw"),
    [
        ("incomplete", '{"tables": ["a"'),  # cut off inside the object
        ("incomplete", '{"columns": []}'),  # wrong shape
        ("incomplete", None),
        ("refusal", '{"tables": ["a"]}'),  # only truncation is recoverable
    ],
)
def test_other_failures_still_raise(reason: str, raw: str | None) -> None:
    with pytest.raises(StructuredCallFailed):
        _call(_failing(reason, raw))


def test_embeddings_are_unit_length_and_requested_at_256_dimensions() -> None:
    llm = FakeLLM(vectors={"a": [3.0, 4.0] + [0.0] * 254})
    vectors, call = asyncio.run(embed(llm, ["a", "b"], purpose="p"))
    assert vectors.shape == (2, 256) and vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert vectors[0][:2] == pytest.approx([0.6, 0.8])
    assert call.purpose == "p"


def test_zero_vectors_do_not_divide_by_zero() -> None:
    assert np.array_equal(unit_rows([[0.0, 0.0]]), np.zeros((1, 2), dtype=np.float32))
