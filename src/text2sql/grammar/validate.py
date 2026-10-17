"""Offline checks of a Lark grammar against both engines that matter.

Two lark front ends are used for two jobs. Validation builds the LALR(1) table in strict mode,
which fails on any shift/reduce or reduce/reduce conflict; a conflict-free LALR(1) grammar is
unambiguous. (Lark's own `strict=True` also checks regex collisions through `interegular`,
which takes over a minute on the bounded string-literal regex, so the table is analysed
directly instead.) Parsing uses Earley with lark's dynamic lexer, which accepts exactly the
grammar's language. LALR's lexer would not: it tries terminals in a fixed order and stops at
the first match, so `NULLIF(` lexes as the constant `NULL` and fails.

`llguidance` is the engine behind the OpenAI grammar tool. Its lexer is greedy and never
backtracks, so it accepts a subset of the language: a string where one lexeme could stop
early and the next begin is lost if the longer lexeme can continue. The builder avoids those
shapes, and `GuidanceMatcher` replays strings byte by byte to check that the engines agree.
Neither engine reproduces the API's own size limit; see `text2sql.grammar.size`.
"""

from __future__ import annotations

from functools import lru_cache

from lark import Lark
from lark.common import ParserConf
from lark.exceptions import LarkError
from lark.parsers.lalr_analysis import LALR_Analyzer
from llguidance import LLMatcher, LLTokenizer, TokenizerWrapper

from text2sql.grammar.errors import GrammarInvalid

_EOS = 256


@lru_cache(maxsize=64)
def lark_parser(definition: str) -> Lark:
    """Earley parser for a grammar definition, cached per definition."""
    return Lark(definition, parser="earley", lexer="dynamic")


def validate_grammar_offline(definition: str) -> None:
    """Raise GrammarInvalid unless lark (conflict-free LALR(1)) and llguidance both accept it."""
    try:
        lalr = Lark(definition, parser="lalr")
        conf = ParserConf(lalr.rules, {}, lalr.options.start)
        LALR_Analyzer(conf, strict=True).compute_lalr()  # type: ignore[no-untyped-call]
        lark_parser(definition)
    except LarkError as exc:
        raise GrammarInvalid(f"lark: {exc}") from exc
    is_error, messages = LLMatcher.validate_grammar_with_warnings(
        LLMatcher.grammar_from_lark(definition), _byte_tokenizer()
    )
    if is_error or messages:
        raise GrammarInvalid("llguidance: " + "; ".join(messages))


class _ByteVocabulary:
    """A 257-token vocabulary: one token per byte plus EOS, so any UTF-8 string tokenizes."""

    def __init__(self) -> None:
        self.tokens = [bytes([b]) for b in range(256)] + [b"<eos>"]
        self.eos_token_id = _EOS
        self.bos_token_id = None
        self.special_token_ids = [_EOS]

    def __call__(self, text: bytes | str) -> list[int]:
        return list(text.encode() if isinstance(text, str) else text)


@lru_cache(maxsize=1)
def _byte_tokenizer() -> LLTokenizer:
    return LLTokenizer(TokenizerWrapper(_ByteVocabulary()))


class GuidanceMatcher:
    """Checks whole strings against a grammar the way llguidance constrains generation."""

    def __init__(self, definition: str) -> None:
        self._matcher = LLMatcher(
            _byte_tokenizer(), LLMatcher.grammar_from_lark(definition), log_level=0
        )
        if self._matcher.is_error():
            raise GrammarInvalid("llguidance: " + self._matcher.get_error())

    def accepts(self, text: str) -> bool:
        # A rejected token leaves an LLMatcher in a permanent error state, so probe with
        # validate_tokens (side-effect free) and only consume strings that are fully valid.
        tokens = list(text.encode())
        if self._matcher.validate_tokens(tokens) < len(tokens):
            return False
        self._matcher.consume_tokens(tokens)
        accepting = self._matcher.is_accepting()
        self._matcher.reset()
        return bool(accepting)
