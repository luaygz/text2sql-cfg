"""SQLite parsing shared by the validator and the scoping layer.

Both layers parse with sqlglot's SQLite dialect and fold identifiers the way SQLite compares them:
ASCII letters only. Python's `str.lower()` would also fold e.g. the Kelvin sign to `k`, matching
names that SQLite itself treats as different.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import SqlglotError
from sqlglot.tokenizer_core import Token

_DIALECT = Dialect.get_or_raise("sqlite")
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


class SqlSyntaxError(Exception):
    """sqlglot could not tokenize or parse the text."""


@dataclass(frozen=True, slots=True)
class ParsedSql:
    tokens: tuple[Token, ...]
    statements: tuple[exp.Expr, ...]


def parse_sql(sql: str) -> ParsedSql:
    """Tokenize once and parse every statement; empty statements (`;;`) are dropped."""
    try:
        tokens = _DIALECT.tokenize(sql)
        trees = _DIALECT.parser().parse(tokens, sql)
    except (SqlglotError, RecursionError) as exc:
        raise SqlSyntaxError(str(exc).split("\n", 1)[0]) from exc
    return ParsedSql(tuple(tokens), tuple(t for t in trees if t is not None))


def fold(name: str) -> str:
    """SQLite identifier comparison key."""
    return name.translate(_ASCII_LOWER)
