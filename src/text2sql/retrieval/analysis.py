"""Stage 2a: one small-model structured call reads literals, keywords and structure from a question.

The prompt (prompts/question_analysis.yaml) sees no schema, so it costs the same for every
database and its long instruction block is a cacheable prefix. The few-shot pool is masked by
this same function with the same model and effort, so test-side and pool skeletons come from
one masking procedure (docs/adr/011-retrieval.md).
"""

from __future__ import annotations

from text2sql.config import ReasoningEffort
from text2sql.llm import Message, Structured
from text2sql.prompts import load_prompt
from text2sql.retrieval.calls import StructuredLLM, structured_call
from text2sql.retrieval.types import QuestionAnalysis

PROMPT = "question_analysis"
DEFAULT_ANALYSIS_EFFORT: ReasoningEffort = "none"
"""The effort the few-shot pools were masked with; use it online too so skeletons compare."""
MAX_OUTPUT_TOKENS = 2_000
"""An analysis is about 150 tokens; the rest leaves room for reasoning at higher efforts."""


def analysis_messages(question: str, evidence: str | None) -> list[Message]:
    template = load_prompt(PROMPT)
    return [
        Message("developer", template.render("instructions"), cache_breakpoint=True),
        Message(
            "user",
            template.render("user", question=question.strip(), evidence=_evidence(evidence)),
        ),
    ]


async def analyze_question(
    llm: StructuredLLM,
    *,
    question: str,
    evidence: str | None,
    model: str,
    effort: ReasoningEffort,
) -> Structured[QuestionAnalysis]:
    """Literals, keywords, skeleton, requested outputs, complexity and may-be-empty flag."""
    return await structured_call(
        llm,
        model=model,
        messages=analysis_messages(question, evidence),
        output=QuestionAnalysis,
        effort=effort,
        purpose=f"retrieval.analysis {load_prompt(PROMPT).tag}",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def _evidence(evidence: str | None) -> str:
    text = (evidence or "").strip()
    return text or "(none)"
