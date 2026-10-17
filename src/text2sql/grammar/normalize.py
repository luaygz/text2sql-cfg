"""Rewrite human-written SQLite into the canonical spelling the grammar accepts.

Grammar coverage asks whether the grammar can express each gold query, not whether a human
happened to use our whitespace. So gold SQL is parsed with sqlglot and printed back in the
grammar's conventions. Every rewrite here preserves the query's result:

- keyword case, whitespace, `!=` -> `<>`, `x NOT IN` -> `NOT x IN`, `LIMIT a, b` ->
  `LIMIT b OFFSET a`, comma joins -> `CROSS JOIN`, `IFNULL` -> `COALESCE` (sqlglot's printer);
- CTEs renamed to `cte1`..`cte5`, table aliases to `T1`..`T9` (aliases already named `Tn`
  keep their number; unaliased base tables get one); qualifiers follow their source by scope;
- a string literal starting with a TRAP_PUNCTUATION character and not a digit after it is
  split into a concatenation, `'(none)'` -> `('(' || 'none)')` (ADR-005);
- `CAST(x AS <type>)` printed with the type's SQLite affinity (`INTEGER`, `TEXT`, `REAL`,
  `NUMERIC`), which is all CAST looks at, so `CAST(x AS DATE)` stays a numeric cast;
- with a schema: identifier case and quoting follow the schema, computed-column aliases that
  are not schema column names become `c1`..`c9`, and an unresolvable double-quoted name
  becomes the string literal SQLite would have read it as.

Without a schema, column aliases and identifier case are left alone, because telling an alias
from a column needs the schema.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import ClassVar

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import rename_func
from sqlglot.dialects.sqlite import SQLite
from sqlglot.errors import ErrorLevel, SqlglotError
from sqlglot.generators.sqlite import SQLiteGenerator

from text2sql.catalog.schema import DatabaseSchema
from text2sql.grammar.conventions import (
    COLUMN_ALIASES,
    CTE_NAMES,
    TABLE_ALIASES,
    TRAP_PUNCTUATION,
    sql_identifier,
)
from text2sql.grammar.errors import NormalizationError


def _affinity(datatype: exp.DataType) -> str:
    """SQLite's type-affinity rules (https://www.sqlite.org/datatype3.html, section 3.1)."""
    raw = datatype.args.get("kind") if datatype.this == exp.DType.USERDEFINED else None
    name = str(raw or datatype.this.value).upper()
    if "INT" in name:
        return "INTEGER"
    if any(token in name for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if "BLOB" in name:
        return "BLOB"
    if any(token in name for token in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return "NUMERIC"


class _GrammarSQLite(SQLite):
    """SQLite as the grammar spells it: backtick quotes, SUBSTR, affinity-named CAST types."""

    class Tokenizer(SQLite.Tokenizer):
        IDENTIFIERS: ClassVar[list[str | tuple[str, str]]] = ["`", '"', ("[", "]")]

    class Generator(SQLiteGenerator):
        TRANSFORMS: ClassVar[dict[type[exp.Expr], Callable[..., str]]] = {
            **SQLiteGenerator.TRANSFORMS,
            exp.Substring: rename_func("SUBSTR"),
        }

        def cast_sql(self, expression: exp.Cast, safe_prefix: str | None = None) -> str:
            return f"CAST({self.sql(expression, 'this')} AS {_affinity(expression.to)})"


def normalize_sql(sql: str, schema: DatabaseSchema | None = None) -> str:
    """Canonical, grammar-shaped spelling of one SQLite query; raises NormalizationError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except SqlglotError as exc:
        raise NormalizationError(f"sqlglot cannot parse: {exc}") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise NormalizationError("expected exactly one SELECT statement")
    tree = statements[0]
    try:
        _rename_ctes(tree)
        _alias_tables(tree)
        if schema is not None:
            _apply_schema(tree, schema)
        _requote(tree)
        _split_trap_literals(tree)
        return tree.sql(dialect=_GrammarSQLite, unsupported_level=ErrorLevel.RAISE)
    except SqlglotError as exc:
        raise NormalizationError(str(exc)) from exc


def _rename_ctes(tree: exp.Expr) -> None:
    ctes = list(tree.find_all(exp.CTE))
    if len(ctes) > len(CTE_NAMES):
        raise NormalizationError(f"{len(ctes)} CTEs; the grammar allows {len(CTE_NAMES)}")
    renames = {cte.alias.lower(): new for cte, new in zip(ctes, CTE_NAMES, strict=False)}
    for cte in ctes:
        cte.args["alias"].set("this", exp.to_identifier(renames[cte.alias.lower()]))
    for table in tree.find_all(exp.Table):
        if not table.args.get("db") and table.name.lower() in renames:
            table.set("this", exp.to_identifier(renames[table.name.lower()]))
    _requalify(tree, renames)


_ALIAS_NUMBER = re.compile(r"t([1-9])", re.IGNORECASE)


def _alias_tables(tree: exp.Expr) -> None:
    """Give every base table and aliased source a `Tn` alias and requalify columns to match.

    Renaming is by the name a source is visible under (its alias, or the table name when it
    has none), one new name per old name. That keeps every qualifier bound to the same source
    in every scope, so no scope analysis is needed. Aliases already named `Tn` keep `n`.
    """
    sources = [
        node
        for node in tree.find_all(exp.Table, exp.Subquery)
        if isinstance(node, exp.Table | exp.Subquery)
        and isinstance(node.parent, exp.From | exp.Join)
    ]
    visible = {id(s): _visible_name(s) for s in sources}
    names = list(dict.fromkeys(v.lower() for v in visible.values() if v))
    taken = {int(m.group(1)) for n in names if (m := _ALIAS_NUMBER.fullmatch(n))}
    free = (n for n in range(1, len(TABLE_ALIASES) + 1) if n not in taken)
    renames: dict[str, str] = {}
    for name in names:
        if match := _ALIAS_NUMBER.fullmatch(name):
            renames[name] = f"T{match.group(1)}"
            continue
        number = next(free, None)
        if number is None:
            raise NormalizationError(f"more than {len(TABLE_ALIASES)} table aliases needed")
        renames[name] = f"T{number}"
    for source in sources:
        if new := renames.get(visible[id(source)].lower()):
            source.set("alias", exp.TableAlias(this=exp.to_identifier(new)))
    _requalify(tree, renames)


def _visible_name(source: exp.Table | exp.Subquery) -> str:
    """Name the source is referenced by; unaliased CTE references keep their `cteN` name."""
    if source.alias:
        return source.alias
    if isinstance(source, exp.Table) and source.name not in CTE_NAMES:
        return source.name
    return ""


def _requalify(tree: exp.Expr, renames: dict[str, str]) -> None:
    for column in tree.find_all(exp.Column):
        if column.table and (new := renames.get(column.table.lower())):
            column.set("table", exp.to_identifier(new))


def _apply_schema(tree: exp.Expr, schema: DatabaseSchema) -> None:
    columns: dict[str, str] = {}
    for schema_table in schema.tables:
        for schema_column in schema_table.columns:
            columns.setdefault(schema_column.name.lower(), schema_column.name)

    for table_node in tree.find_all(exp.Table):
        if (known := schema.table(table_node.name)) is not None:
            table_node.set("this", exp.to_identifier(known.name))

    alias_names = _rename_column_aliases(tree, columns)
    for column in list(tree.find_all(exp.Column)):
        if isinstance(column.this, exp.Star):
            continue
        key = column.name.lower()
        if key in columns:
            column.set("this", exp.to_identifier(columns[key]))
        elif key in alias_names:
            column.set("this", exp.to_identifier(alias_names[key]))
        elif column.this.quoted and not column.table:
            # SQLite reads an unresolvable "name" as the string 'name'.
            column.replace(exp.Literal.string(column.name))


def _rename_column_aliases(tree: exp.Expr, columns: dict[str, str]) -> dict[str, str]:
    """Map select-list alias names to `c1`..`c9`, keeping aliases that are schema columns."""
    aliases = [a for a in tree.find_all(exp.Alias) if isinstance(a.parent, exp.Select)]
    reserved = {name.lower() for name in COLUMN_ALIASES}
    taken = {a.alias.lower() for a in aliases if a.alias.lower() in reserved}
    free = (name for name in COLUMN_ALIASES if name.lower() not in taken)
    renames: dict[str, str] = {}
    for alias in aliases:
        key = alias.alias.lower()
        if key in columns:
            new = columns[key]
        elif key in reserved:
            new = key
        elif key in renames:
            new = renames[key]
        else:
            fresh = next(free, None)
            if fresh is None:
                raise NormalizationError(f"more than {len(COLUMN_ALIASES)} column aliases")
            new = renames[key] = fresh
        alias.set("alias", exp.to_identifier(new))
    return {**renames, **{name: name for name in taken}}


def _requote(tree: exp.Expr) -> None:
    for identifier in tree.find_all(exp.Identifier):
        identifier.set("quoted", sql_identifier(identifier.name) != identifier.name)


def _split_trap_literals(tree: exp.Expr) -> None:
    """`'(none)'` -> `('(' || 'none)')`: the grammar's spelling of such literals (ADR-005)."""
    for literal in list(tree.find_all(exp.Literal)):
        if not literal.is_string:
            continue
        parts, rest = [], literal.this
        while len(rest) > 1 and rest[0] in TRAP_PUNCTUATION and not rest[1].isdigit():
            parts.append(rest[0])
            rest = rest[1:]
        if not parts:
            continue
        chain: exp.Expr = exp.Literal.string(parts[0])
        for part in [*parts[1:], rest]:
            chain = exp.DPipe(this=chain, expression=exp.Literal.string(part))
        literal.replace(exp.Paren(this=chain))
