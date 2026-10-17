"""Layer 2: AST validation of SQL produced by the model.

The grammar (layer 1) should make every rejection here impossible; this module assumes it failed.
It parses with sqlglot's SQLite dialect and accepts only a single read-only SELECT (optionally with
CTEs and set operations) whose tables, columns and functions all resolve against the request's
visible schema and allowlist. Every rejection is a `ValidationError` with a stable `Rule` id;
nothing is repaired.

Validating with one parser and executing with another invites parser differentials, so anything
sqlglot and SQLite could read differently is rejected outright: comments, statement separators,
non-ASCII outside literals, bind parameters, and SQLite's `expr IN table` form (sqlglot parses the
table as a column; SQLite reads the whole table).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from sqlglot import exp
from sqlglot.errors import OptimizeError
from sqlglot.optimizer.scope import Scope, ScopeType, traverse_scope
from sqlglot.tokenizer_core import Token, TokenType

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.safety.errors import ValidationError
from text2sql.safety.parsing import SqlSyntaxError, fold, parse_sql
from text2sql.safety.policy import ScopePolicy

ALLOWED_FUNCTIONS: Final = frozenset(
    {
        "COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "ABS", "CAST", "COALESCE", "IIF", "NULLIF",
        "LENGTH", "UPPER", "LOWER", "TRIM", "SUBSTR", "INSTR", "REPLACE", "STRFTIME", "DATE",
        "JULIANDAY", "CASE",
    }
)  # fmt: skip
"""The function allowlist (the grammar's too); CASE is listed so it can be switched off."""


class Rule(StrEnum):
    """Stable rejection ids; the safety report aggregates on these."""

    TOO_LONG = "too_long"
    PARSE_ERROR = "parse_error"
    COMMENT = "comment"
    MULTIPLE_STATEMENTS = "multiple_statements"
    NON_ASCII = "non_ascii"
    """Non-ASCII outside string literals and quoted identifiers (homoglyphs, odd whitespace)."""
    NOT_SELECT = "not_select"
    FORBIDDEN_CONSTRUCT = "forbidden_construct"
    """A syntax node outside the allowlist: window functions, RIGHT/NATURAL joins, `IN table`..."""
    PLACEHOLDER = "placeholder"
    FUNCTION_NOT_ALLOWED = "function_not_allowed"
    SCHEMA_QUALIFIER = "schema_qualifier"
    SYSTEM_TABLE = "system_table"
    UNKNOWN_TABLE = "unknown_table"
    INVALID_CTE = "invalid_cte"
    SCOPE_ERROR = "scope_error"
    """sqlglot could not build the query's scopes (e.g. one alias used for two sources)."""
    UNKNOWN_COLUMN = "unknown_column"
    AMBIGUOUS_COLUMN = "ambiguous_column"
    HIDDEN_COLUMN = "hidden_column"
    STAR_IN_TENANT_MODE = "star_in_tenant_mode"
    INVALID_LIMIT = "invalid_limit"
    LIMIT_TOO_LARGE = "limit_too_large"
    MISSING_LIMIT = "missing_limit"


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    mode: QueryMode
    max_rows: int = 1000
    """Largest LIMIT accepted in production and tenant mode."""
    functions: frozenset[str] = ALLOWED_FUNCTIONS
    scope: ScopePolicy | None = None
    """When set, scope and hidden columns are rejected as `hidden_column` even if `schema` still
    lists them, and CTEs may not shadow scoped tables."""
    max_sql_chars: int = 10_000


_STRUCTURAL: Final[frozenset[type[exp.Expr]]] = frozenset(
    {
        exp.Select, exp.Union, exp.Intersect, exp.Except, exp.CTE, exp.Subquery, exp.From,
        exp.Where, exp.Group, exp.Having, exp.Order, exp.Ordered, exp.Alias, exp.TableAlias,
        exp.Identifier, exp.Column, exp.Literal, exp.Null, exp.Boolean, exp.Paren, exp.Distinct,
        exp.DataType, exp.Exists, exp.In, exp.Like, exp.Between, exp.Is, exp.Not, exp.And, exp.Or,
        exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Neg, exp.Add, exp.Sub, exp.Mul,
        exp.Div, exp.Mod, exp.DPipe, exp.CurrentDate, exp.CurrentTime, exp.CurrentTimestamp,
    }
)  # fmt: skip
"""Node types allowed as they are; everything else needs a dedicated check or is rejected.
CURRENT_DATE/TIME/TIMESTAMP are keyword constants the grammar emits, not calls."""

_SPANLESS_NAMES: Final[dict[type[exp.Expr], str]] = {
    exp.Case: "CASE",
    exp.Cast: "CAST",
    exp.Trim: "TRIM",
    exp.Substring: "SUBSTRING",
}
"""sqlglot records the source span of a function name in `node.meta`, except for calls handled by
dedicated parsers. Those are named by their keyword; SUBSTR has a span, SUBSTRING does not."""

_IMPLIED: Final = frozenset(
    {(exp.If, exp.Case, "ifs"), (exp.TsOrDsToTimestamp, exp.TimeToStr, "this")}
)
"""Nodes sqlglot synthesizes inside an allowed construct (CASE branches, STRFTIME's argument)."""

_LITERAL_TOKENS: Final = frozenset({TokenType.STRING, TokenType.IDENTIFIER})
_UNSIGNED_INT: Final = re.compile(r"[0-9]+")


def validate_sql(sql: str, schema: DatabaseSchema, config: ValidationConfig) -> exp.Expression:
    """Return the parsed statement if `sql` passes every rule; raise `ValidationError` otherwise.

    `schema` is what this request may reference: the visible schema, or the linked subset of it.
    """
    if len(sql) > config.max_sql_chars:
        raise ValidationError(
            Rule.TOO_LONG, f"{len(sql)} characters exceeds the limit of {config.max_sql_chars}"
        )
    try:
        parsed = parse_sql(sql)
    except SqlSyntaxError as exc:
        raise ValidationError(Rule.PARSE_ERROR, str(exc)) from exc
    _check_tokens(sql, parsed.tokens)
    if len(parsed.statements) != 1:
        raise ValidationError(Rule.PARSE_ERROR, "expected exactly one statement")
    tree = parsed.statements[0]
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        raise ValidationError(
            Rule.NOT_SELECT, f"{type(tree).__name__} statements are not allowed, only SELECT"
        )
    _Validator(sql, schema, config).check(tree)
    return tree


def _check_tokens(sql: str, tokens: Sequence[Token]) -> None:
    outside: list[str] = []
    pos = 0
    for token in tokens:
        if token.comments:
            raise ValidationError(Rule.COMMENT, "comments are not allowed")
        if token.token_type is TokenType.SEMICOLON:
            raise ValidationError(Rule.MULTIPLE_STATEMENTS, "statement separator ';' found")
        if token.token_type in _LITERAL_TOKENS:
            outside.append(sql[pos : token.start])
            pos = token.end + 1
    outside.append(sql[pos:])
    if not "".join(outside).isascii():
        raise ValidationError(
            Rule.NON_ASCII, "non-ASCII character outside a string literal or quoted identifier"
        )


@dataclass(frozen=True, slots=True)
class _Source:
    """A FROM/JOIN source as seen from its query: nameable columns and policy-hidden ones."""

    columns: frozenset[str]
    hidden: frozenset[str] = frozenset()


def _enclosing(scope: Scope) -> Scope | None:
    # Expression subqueries (and the branches of a compound query inside one) can see the
    # enclosing query; FROM subqueries and CTE bodies cannot, as SQLite has no LATERAL.
    if scope.scope_type in (ScopeType.SUBQUERY, ScopeType.SET_OPERATION):
        return scope.parent
    return None


class _Validator:
    def __init__(self, sql: str, schema: DatabaseSchema, config: ValidationConfig) -> None:
        self._sql = sql
        self._config = config
        self._policy = config.scope
        if config.scope is not None:
            schema = config.scope.visible_schema(schema)
        self._tables = {fold(t.name): t for t in schema.tables}
        self._functions = frozenset(fold(f) for f in config.functions)
        self._ctes: frozenset[str] = frozenset()
        self._scopes: dict[int, Scope] = {}
        self._sources: dict[int, dict[str, _Source]] = {}

    def check(self, tree: exp.Expression) -> None:
        self._ctes = frozenset(fold(cte.alias) for cte in tree.find_all(exp.CTE))
        for node in tree.walk():
            self._check_node(node)
        if self._config.mode is not QueryMode.BENCHMARK and tree.args.get("limit") is None:
            raise ValidationError(Rule.MISSING_LIMIT, f"{self._config.mode} mode requires LIMIT")
        try:
            scopes = traverse_scope(tree)
            # Children come before parents, so a derived table's outputs exist when its parent
            # resolves columns against it.
            for scope in scopes:
                self._sources[id(scope)] = self._source_map(scope)
                self._check_star_qualifiers(scope)
        except OptimizeError as exc:
            raise ValidationError(Rule.SCOPE_ERROR, str(exc)) from exc
        self._scopes = {id(scope.expression): scope for scope in scopes}
        for column in tree.find_all(exp.Column):
            if not isinstance(column.this, exp.Star):
                self._check_column(column)

    # -- syntax --------------------------------------------------------------------------------

    def _check_node(self, node: exp.Expr) -> None:  # noqa: PLR0912 - one flat case per node kind
        match node:
            case exp.Placeholder() | exp.Parameter():
                raise ValidationError(Rule.PLACEHOLDER, f"bind parameter {node.sql()} found")
            case exp.Identifier() if not node.quoted and node.name.startswith("$"):
                raise ValidationError(Rule.PLACEHOLDER, f"bind parameter {node.name} found")
            case exp.Table():
                self._check_table(node)
            case exp.Column() if node.args.get("db") or node.args.get("catalog"):
                raise ValidationError(Rule.SCHEMA_QUALIFIER, f"{node.sql()} names a schema")
            case exp.Join():
                self._check_join(node)
            case exp.Limit() | exp.Offset():
                self._check_limit(node)
            case exp.Star():
                self._check_star(node)
            case exp.In() if node.args.get("field") is not None:
                raise ValidationError(
                    Rule.FORBIDDEN_CONSTRUCT, "IN must be followed by a list or a subquery"
                )
            case exp.TableAlias() if node.columns and not isinstance(node.parent, exp.CTE):
                raise ValidationError(Rule.FORBIDDEN_CONSTRUCT, "column lists on table aliases")
            case exp.With():
                self._check_with(node)
            case _ if type(node) in _STRUCTURAL:
                return
            case exp.Func():
                self._check_function(node)
            case _:
                raise ValidationError(
                    Rule.FORBIDDEN_CONSTRUCT, f"{type(node).__name__} is not allowed"
                )

    def _check_table(self, table: exp.Table) -> None:
        if not isinstance(table.parent, (exp.From, exp.Join)):
            raise ValidationError(Rule.FORBIDDEN_CONSTRUCT, "table reference outside FROM/JOIN")
        if table.args.get("db") or table.args.get("catalog"):
            raise ValidationError(Rule.SCHEMA_QUALIFIER, f"{table.sql()} names a schema")
        name = fold(table.name)
        if name.startswith("sqlite_"):
            raise ValidationError(Rule.SYSTEM_TABLE, f"{table.name} is a SQLite system table")
        if table.args.get("indexed") is not None:
            raise ValidationError(Rule.FORBIDDEN_CONSTRUCT, "INDEXED BY / NOT INDEXED")
        if name not in self._tables and name not in self._ctes:
            raise ValidationError(Rule.UNKNOWN_TABLE, f"{table.name} is not in the schema")

    def _check_join(self, join: exp.Join) -> None:
        side, kind = join.side.upper(), join.kind.upper()
        inner = side == "" and kind in {"", "INNER", "CROSS"}
        left = side == "LEFT" and kind in {"", "OUTER"}
        if not (inner or left) or join.method or join.args.get("using"):
            raise ValidationError(
                Rule.FORBIDDEN_CONSTRUCT,
                f"{' '.join(filter(None, [join.method, side, kind]))} JOIN is not allowed; use "
                "[INNER] JOIN ... ON, LEFT [OUTER] JOIN ... ON or CROSS JOIN",
            )

    def _check_limit(self, node: exp.Limit | exp.Offset) -> None:
        value = node.expression
        clause = "LIMIT" if isinstance(node, exp.Limit) else "OFFSET"
        if not (
            isinstance(value, exp.Literal)
            and not value.is_string
            and _UNSIGNED_INT.fullmatch(value.this)
        ):
            raise ValidationError(
                Rule.INVALID_LIMIT, f"{clause} must be a non-negative integer, got {value.sql()}"
            )
        if (
            clause == "LIMIT"
            and self._config.mode is not QueryMode.BENCHMARK
            and int(value.this) > self._config.max_rows
        ):
            raise ValidationError(
                Rule.LIMIT_TOO_LARGE, f"LIMIT {value.this} exceeds {self._config.max_rows}"
            )

    def _check_star(self, star: exp.Star) -> None:
        if isinstance(star.parent, exp.Count):
            return
        item = star.parent if isinstance(star.parent, exp.Column) else star
        if not isinstance(item.parent, exp.Select) or item.arg_key != "expressions":
            raise ValidationError(
                Rule.FORBIDDEN_CONSTRUCT, "* is only allowed as a select item or in COUNT(*)"
            )
        if self._config.mode is QueryMode.TENANT:
            raise ValidationError(
                Rule.STAR_IN_TENANT_MODE, "list columns explicitly; * is rejected in tenant mode"
            )

    def _check_with(self, with_: exp.With) -> None:
        if with_.args.get("recursive"):
            raise ValidationError(Rule.INVALID_CTE, "recursive CTEs are not allowed")
        seen: set[str] = set()
        for cte in with_.expressions:
            name = fold(cte.alias)
            if name in seen:
                raise ValidationError(Rule.INVALID_CTE, f"CTE {cte.alias} is defined twice")
            if (
                name in self._tables
                or name.startswith("sqlite_")
                or (self._policy is not None and self._policy.is_tenant_scoped(name))
            ):
                raise ValidationError(Rule.INVALID_CTE, f"CTE {cte.alias} shadows a table")
            seen.add(name)

    def _check_function(self, node: exp.Func) -> None:
        name = self._function_name(node)
        if name is not None and fold(name) not in self._functions:
            raise ValidationError(Rule.FUNCTION_NOT_ALLOWED, f"{name.upper()} is not allowed")

    def _function_name(self, node: exp.Func) -> str | None:
        if isinstance(node, exp.Anonymous):
            return node.name
        start, end = node.meta.get("start"), node.meta.get("end")
        if start is not None and end is not None:
            return self._sql[start : end + 1]
        if (type(node), type(node.parent), node.arg_key) in _IMPLIED:
            return None
        return _SPANLESS_NAMES.get(type(node), node.sql_name())

    # -- name resolution -----------------------------------------------------------------------

    def _source_map(self, scope: Scope) -> dict[str, _Source]:
        sources: dict[str, _Source] = {}
        for alias, (_, source) in scope.selected_sources.items():
            if isinstance(source, Scope):
                sources[fold(alias)] = _Source(self._outputs(source))
                continue
            table = self._tables.get(fold(source.name))
            if table is None:  # a CTE used before (or inside) its own definition
                raise ValidationError(
                    Rule.UNKNOWN_TABLE, f"{source.name} is not in the schema or an earlier CTE"
                )
            hidden = self._policy.hidden_for(table.name) if self._policy else frozenset()
            sources[fold(alias)] = _Source(frozenset(fold(c.name) for c in table.columns), hidden)
        return sources

    def _check_star_qualifiers(self, scope: Scope) -> None:
        for item in scope.expression.expressions:
            if (
                isinstance(item, exp.Column)
                and isinstance(item.this, exp.Star)
                and fold(item.table) not in self._sources[id(scope)]
            ):
                raise ValidationError(Rule.UNKNOWN_COLUMN, f"{item.table}.* has no source")

    def _outputs(self, scope: Scope) -> frozenset[str]:
        """Column names a derived table or CTE exposes to the query that selects from it."""
        cte = scope.expression.parent
        if isinstance(cte, exp.CTE) and cte.alias_column_names:
            return frozenset(fold(c) for c in cte.alias_column_names)
        return self._select_outputs(scope)

    def _select_outputs(self, scope: Scope) -> frozenset[str]:
        query = scope.expression
        if isinstance(query, exp.SetOperation):  # a compound query is named by its first branch
            return self._select_outputs(scope.set_operation_scopes[0])
        sources = self._sources[id(scope)]
        names: set[str] = set()
        for item in query.expressions:
            if isinstance(item, exp.Star):
                names.update(*(s.columns for s in sources.values()))
            elif isinstance(item, exp.Column) and isinstance(item.this, exp.Star):
                names.update(sources[fold(item.table)].columns)
            else:
                names.add(fold(item.alias_or_name))
        return frozenset(names)

    def _branch_outputs(self, scope: Scope) -> frozenset[str]:
        if isinstance(scope.expression, exp.SetOperation):
            return frozenset().union(*map(self._branch_outputs, scope.set_operation_scopes))
        return self._select_outputs(scope)

    def _aliases(self, scope: Scope) -> frozenset[str]:
        """Names an unqualified column may refer to besides source columns (SQLite resolves
        select-list aliases in WHERE/GROUP BY/HAVING/ORDER BY; a compound ORDER BY sees the
        output names of every branch)."""
        query = scope.expression
        if isinstance(query, exp.SetOperation):
            return self._branch_outputs(scope)
        return frozenset(fold(e.alias) for e in query.expressions if isinstance(e, exp.Alias))

    def _owning_scope(self, column: exp.Column) -> Scope:
        ancestor = column.parent
        while ancestor is not None and id(ancestor) not in self._scopes:
            ancestor = ancestor.parent
        return self._scopes[id(ancestor)]

    def _check_column(self, column: exp.Column) -> None:
        scope = self._owning_scope(column)
        name, qualifier = fold(column.name), fold(column.table)
        current: Scope | None = scope
        while current is not None:
            sources = self._sources[id(current)]
            if qualifier in sources:
                self._check_member(column, sources[qualifier])
                return
            if not qualifier:
                matches = [s for s in sources.values() if name in s.columns]
                if len(matches) > 1:
                    raise ValidationError(Rule.AMBIGUOUS_COLUMN, f"{column.name} is ambiguous")
                if matches:
                    return
                if any(name in s.hidden for s in sources.values()):
                    raise ValidationError(Rule.HIDDEN_COLUMN, f"{column.name} is not visible")
                if current is scope and name in self._aliases(scope):
                    return
            current = _enclosing(current)
        raise ValidationError(Rule.UNKNOWN_COLUMN, f"{column.sql()} does not resolve")

    @staticmethod
    def _check_member(column: exp.Column, source: _Source) -> None:
        name = fold(column.name)
        if name in source.columns:
            return
        rule = Rule.HIDDEN_COLUMN if name in source.hidden else Rule.UNKNOWN_COLUMN
        raise ValidationError(rule, f"{column.sql()} is not a visible column of {column.table}")
