"""Grammar-constrained SQL: the Lark grammar builder, offline validation and gold-SQL coverage."""

from text2sql.grammar.builder import build_grammar
from text2sql.grammar.errors import GrammarInvalid, GrammarRejection, NormalizationError
from text2sql.grammar.model import GrammarOptions, GrammarOutput, SqlGrammar
from text2sql.grammar.normalize import normalize_sql
from text2sql.grammar.size import GrammarSize
from text2sql.grammar.validate import GuidanceMatcher, validate_grammar_offline

__all__ = [
    "GrammarInvalid",
    "GrammarOptions",
    "GrammarOutput",
    "GrammarRejection",
    "GrammarSize",
    "GuidanceMatcher",
    "NormalizationError",
    "SqlGrammar",
    "build_grammar",
    "normalize_sql",
    "validate_grammar_offline",
]
