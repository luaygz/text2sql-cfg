"""Retrieval stages 2-4: question analysis, value retrieval, schema linking, few-shot retrieval.

Indexes live under data/indexes/ (gitignored); build them with
`uv run --frozen python -m text2sql.retrieval build --dataset bird|saas`.
"""

from text2sql.retrieval.analysis import DEFAULT_ANALYSIS_EFFORT, analyze_question
from text2sql.retrieval.columns import ColumnIndex
from text2sql.retrieval.fewshot import FewShotIndex
from text2sql.retrieval.linking import DEFAULT_LINKING_EFFORT, link_schema
from text2sql.retrieval.types import (
    Complexity,
    FewShotExample,
    LinkResult,
    QuestionAnalysis,
    ValueMatches,
)
from text2sql.retrieval.values import ValueIndex

__all__ = [
    "DEFAULT_ANALYSIS_EFFORT",
    "DEFAULT_LINKING_EFFORT",
    "ColumnIndex",
    "Complexity",
    "FewShotExample",
    "FewShotIndex",
    "LinkResult",
    "QuestionAnalysis",
    "ValueIndex",
    "ValueMatches",
    "analyze_question",
    "link_schema",
]
