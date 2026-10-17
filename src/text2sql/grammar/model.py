"""Public value types of the grammar package: options, the built grammar and its outputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

from lark.exceptions import LarkError

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.grammar.errors import GrammarRejection
from text2sql.grammar.size import GrammarSize, measure_grammar
from text2sql.grammar.validate import lark_parser


@dataclass(frozen=True)
class GrammarOptions:
    mode: QueryMode = QueryMode.BENCHMARK
    max_rows: int = 1000
    """Upper bound for LIMIT in every mode; LIMIT is mandatory outside BENCHMARK."""
    allow_abstain: bool = False
    """Add the `ABSTAIN: <reason>` alternative, which never parses as SQL."""

    def __post_init__(self) -> None:
        if self.max_rows < 1:
            raise ValueError(f"max_rows must be positive, got {self.max_rows}")


@dataclass(frozen=True)
class GrammarOutput:
    kind: Literal["sql", "abstain"]
    text: str
    """The SQL text, or the abstention reason without the `ABSTAIN: ` prefix."""


ABSTAIN_PREFIX = "ABSTAIN: "


@dataclass(frozen=True)
class SqlGrammar:
    definition: str
    schema: DatabaseSchema
    options: GrammarOptions
    description: str
    """Tool description telling the model the spelling conventions the grammar enforces."""

    @cached_property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.definition.encode()).hexdigest()

    @cached_property
    def size(self) -> GrammarSize:
        return measure_grammar(self.definition)

    def parse(self, text: str) -> GrammarOutput:
        """Re-parse a tool input locally with lark; raises GrammarRejection if it is not valid.

        The returned text drops the one trailing newline the grammar allows.
        """
        try:
            lark_parser(self.definition).parse(text)
        except LarkError as exc:
            raise GrammarRejection(str(exc)) from exc
        text = text.removesuffix("\n")
        if text.startswith(ABSTAIN_PREFIX):
            return GrammarOutput(kind="abstain", text=text.removeprefix(ABSTAIN_PREFIX))
        return GrammarOutput(kind="sql", text=text)

    def accepts(self, text: str) -> bool:
        try:
            self.parse(text)
        except GrammarRejection:
            return False
        return True
