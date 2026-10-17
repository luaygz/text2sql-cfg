"""Value types passed from retrieval (stages 2-4) to schema linking, generation and the trace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from text2sql.catalog.schema import DatabaseSchema
from text2sql.llm import CallMeta

type ValueMatches = dict[tuple[str, str], list[str]]
"""(table, column) in catalog spelling -> database values that match a question literal."""

Complexity = Literal["easy", "non_nested", "nested"]


class QuestionAnalysis(BaseModel):
    """What the small model reads out of a question before any schema is shown to it.

    Field descriptions are short on purpose: the definitions the model follows are in
    prompts/question_analysis.yaml.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    literals: list[str] = Field(
        description="Database literals from the question and the evidence, verbatim."
    )
    keywords: list[str] = Field(
        description="Keywords and key phrases of the question and the evidence, as worded there."
    )
    skeleton: str = Field(
        description="The question with literals replaced by kind tags such as <NAME> or <YEAR> "
        "and table or column mentions replaced by <COLUMN>."
    )
    requested_outputs: list[str] = Field(
        description="What the answer must contain, in the order the question asks for it."
    )
    complexity: Complexity = Field(
        description="easy: one table, no nesting. non_nested: joins, no nesting. nested: "
        "subquery, set operation, or comparison with an aggregate."
    )
    may_be_empty: bool = Field(
        description="Only for existence checks and 'if any' requests: an empty result may be "
        "the correct answer."
    )


@dataclass(frozen=True)
class LinkResult:
    """The linked schema: `schema` keeps PK/FK join columns; `columns` is everything in it."""

    schema: DatabaseSchema
    columns: frozenset[tuple[str, str]]
    """(table, column) pairs in catalog spelling, including added key columns."""
    calls: tuple[CallMeta, ...]
    shortlist: tuple[tuple[str, str], ...] = ()
    """Embedding-pass columns, most similar first (shown to the model as hints)."""
    passes: tuple[frozenset[tuple[str, str]], ...] = ()
    """Each LLM pass's resolved selection, before values and keys were added."""


@dataclass(frozen=True)
class FewShotExample:
    question: str
    evidence: str | None
    sql: str
