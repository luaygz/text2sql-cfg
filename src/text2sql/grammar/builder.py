"""Turn a database schema and a query mode into the Lark grammar sent with every SQL tool call.

Design notes (ADR-005 has the measurements behind them):

- The API compiles a grammar under a fixed work budget. Measured cost is about 18 regex
  characters per symbol written in a rule body, and one per character of regex terminals. So
  the rules are kept short: the expression grammar is flat (`term (OPERATOR term)*`, with all
  binary operators in one terminal) instead of a precedence tower, and one `items` list serves
  select lists, GROUP BY, ORDER BY, IN lists and call arguments. The grammar accepts a few
  strings SQLite rejects (`ORDER BY x AS c1`); those fail at execution and go to repair. It
  accepts nothing that adds a statement, a comment, a non-allowlisted function or an
  identifier outside the schema.
- One canonical spelling. Keywords are upper case, tokens are separated by exactly one space,
  `, ` separates list items, there is no space inside parentheses. Spaces belong to the
  keyword lexemes (`" FROM "`), so keywords never overlap identifiers.
- Identifiers are enumerated, as prefix-factored regex terminals: `SOURCE` holds the tables
  and CTE names, `COLUMN` the column names plus the computed-column aliases `c1`..`c9`.
  Qualified references use table aliases `T1`..`T9` or CTE names (`T1.col`), never table names.
- No lexeme is a proper prefix of another lexeme that may follow in the same position with the
  longer one's next byte: llguidance lexes greedily and does not backtrack.
- The input may end with one newline. The model ends its tool inputs with one when it can, and
  forbidding it garbled queries that end in a punctuation literal (`'#'`, `'1:54%'`) and made
  some queries run on past their end (ADR-005). `SqlGrammar.parse` drops it.
"""

from __future__ import annotations

from collections.abc import Iterable

import structlog

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.grammar.conventions import (
    AGGREGATES,
    CAST_TYPES,
    COLUMN_ALIASES,
    CONSTANTS,
    CTE_NAMES,
    SCALAR_FUNCTIONS,
    TABLE_ALIASES,
    TRAP_PUNCTUATION,
    sql_identifier,
)
from text2sql.grammar.model import GrammarOptions, SqlGrammar

log = structlog.get_logger(__name__)

STRING_MAX_CHARS = 255
OFFSET_MAX_DIGITS = 6
ABSTAIN_MAX_CHARS = 300

# A string literal: single quotes, `''` as the only escape, at most STRING_MAX_CHARS characters,
# no backslash, `;` or control characters. `--` and `/*` may appear inside the literal, where
# they are data: a regex that excludes them costs as much of the API budget as about 33
# columns (ADR-005).
#
# A literal that starts with one of TRAP_PUNCTUATION is that character alone or the character
# followed by a digit ('-1 day'), so that after `'+` the closing quote is the decoder's only
# non-digit choice (see conventions.TRAP_PUNCTUATION and ADR-005).
_UNIT = r"[^'\\;\x00-\x1f\x7f]|''"
_TRAP_CLASS = "".join("\\" + ch if ch in "-/[" else ch for ch in TRAP_PUNCTUATION)
STRING_REGEX = (
    rf"'(?:[{_TRAP_CLASS}](?:[0-9](?:{_UNIT}){{0,{STRING_MAX_CHARS - 2}}})?"
    rf"|(?:[^'\\;\x00-\x1f\x7f{_TRAP_CLASS}]|'')(?:{_UNIT}){{0,{STRING_MAX_CHARS - 1}}})?'"
)
NUMBER_REGEX = r"[0-9]{1,18}(?:\.[0-9]{0,18})?(?:[eE][+-]?[0-9]{1,3})?"
OPERATOR_REGEX = r" (?:AND|OR|\|\||[-+*\/%]|[<>!]?=|<>|[<>]|(?:NOT )?(?:LIKE|BETWEEN)) "

_TEMPLATE = """\
// SQLite SELECT grammar for database {db_id} (mode={mode}, max_rows={max_rows}).
start: ({start}) "\\n"?
query: body {top_limit}
body: ("WITH " cte (", " cte)* " ")? select (SET_OP select)* (" ORDER BY " items)?
cte: CTE_NAME " AS " paren
select: "SELECT " DISTINCT? items (" FROM " source (JOIN source (" ON " expr)?)*)? \
(" WHERE " expr)? (" GROUP BY " items)? (" HAVING " expr)?
source: (SOURCE | paren) (" AS " TABLE_ALIAS)?
items: item (", " item)*
item: expr (" AS " COLUMN | DIRECTION)?{star_item}
paren: "(" (body limit? | items) ")"
limit: " LIMIT " LIMIT_N (" OFFSET " OFFSET_N)?
expr: term (OPERATOR term)*
term: PREFIX* primary (IS_NULL | IN paren)?
?primary: QUALIFIER? COLUMN | NUMBER | STRING | CONSTANT | EXISTS? paren
    | FUNCTION {call_args} ")"
    | "CAST(" expr " AS " CAST_TYPE ")"
    | "CASE " expr? (WHEN expr " THEN " expr)+ (" ELSE " expr)? " END"
{abstain}
DISTINCT: "DISTINCT "
EXISTS: "EXISTS"
SET_OP: / (?:UNION(?: ALL)?|INTERSECT|EXCEPT) /
JOIN: / (?:(?:INNER|CROSS|LEFT(?: OUTER)?) )?JOIN /
DIRECTION: / (?:ASC|DESC)/
OPERATOR: /{operator}/
PREFIX: /NOT |-/
IS_NULL: / IS (?:NOT )?NULL/
IN: / (?:NOT )?IN /
WHEN: / ?WHEN /
CAST_TYPE: /{cast_types}/
CONSTANT: /{constants}/
FUNCTION: /{functions}\\(/
TABLE_ALIAS: /T[1-{n_aliases}]/
CTE_NAME: /cte[1-{n_ctes}]/
QUALIFIER: /(?:T[1-{n_aliases}]|cte[1-{n_ctes}])\\./
SOURCE: /{sources}/
COLUMN: /{columns}/
NUMBER: /{number}/
STRING: /{string}/
LIMIT_N: /{limit_n}/
OFFSET_N: /[0-9]{{1,{offset_digits}}}/
"""

_ABSTAIN = f"""\
abstain: "ABSTAIN: " REASON
REASON: /[^\\x00-\\x1f\\x7f]{{1,{ABSTAIN_MAX_CHARS}}}/
"""

_REGEX_META = frozenset("\\.+*?()|[]{}^$/")
_DEFAULT_OPTIONS = GrammarOptions()

type _Trie = dict[str, _Trie]


def build_grammar(schema: DatabaseSchema, options: GrammarOptions = _DEFAULT_OPTIONS) -> SqlGrammar:
    """Build the grammar for one database (full or linked schema) and query mode."""
    _check_reserved_names(schema)
    tables = {sql_identifier(t.name) for t in schema.tables}
    columns = {sql_identifier(c.name) for t in schema.tables for c in t.columns}
    tenant = options.mode is QueryMode.TENANT
    definition = _TEMPLATE.format(
        db_id=schema.db_id,
        mode=options.mode.value,
        max_rows=options.max_rows,
        start="query | abstain" if options.allow_abstain else "query",
        top_limit="limit?" if options.mode is QueryMode.BENCHMARK else "limit",
        # Star projections can expand into columns the tenant schema hides, so TENANT has no
        # `*` item; COUNT(*) then needs its own `*` argument.
        star_item="" if tenant else ' | QUALIFIER? "*"',
        call_args='("*" | DISTINCT? items)' if tenant else "DISTINCT? items",
        abstain=_ABSTAIN if options.allow_abstain else "",
        operator=OPERATOR_REGEX,
        cast_types=trie_regex(CAST_TYPES),
        constants=trie_regex(CONSTANTS),
        functions=trie_regex((*AGGREGATES, *SCALAR_FUNCTIONS)),
        n_aliases=len(TABLE_ALIASES),
        n_ctes=len(CTE_NAMES),
        sources=trie_regex((*tables, *CTE_NAMES)),
        columns=trie_regex((*columns, *COLUMN_ALIASES)),
        number=NUMBER_REGEX,
        string=STRING_REGEX,
        limit_n=int_range_regex(options.max_rows),
        offset_digits=OFFSET_MAX_DIGITS,
    )
    grammar = SqlGrammar(
        definition=definition, schema=schema, options=options, description=describe(options)
    )
    size = grammar.size
    if not size.fits_api_budget:
        log.warning(
            "grammar_exceeds_api_budget",
            db_id=schema.db_id,
            tables=len(tables),
            columns=len(columns),
            api_load=size.api_load,
            hint="use a linked-schema grammar",
        )
    return grammar


def describe(options: GrammarOptions) -> str:
    """Conventions the model must follow; sent as the custom tool's description."""
    limit = (
        f"LIMIT is optional (n <= {options.max_rows})."
        if options.mode is QueryMode.BENCHMARK
        else f"End the query with LIMIT n (n <= {options.max_rows})."
    )
    parts = [
        "Exactly one SQLite SELECT statement, no semicolon, no comments.",
        "Upper-case keywords; single spaces between tokens; ', ' between list items;"
        " no space after '(' or before ')'.",
        "Use only the listed tables and columns, spelled exactly as listed"
        " (names with spaces or keywords in backticks).",
        "Alias tables as T1..T9 and qualify columns as T1.column."
        " CTEs are named cte1..cte5; computed columns are aliased c1..c9.",
        "Functions: "
        + ", ".join((*AGGREGATES, *SCALAR_FUNCTIONS))
        + ", CAST(x AS "
        + "|".join(CAST_TYPES)
        + "), CASE.",
        "Write x NOT IN (...), x IS NOT NULL, EXISTS(SELECT ...); strings in single quotes"
        " with '' for a quote. A string starting with one of " + TRAP_PUNCTUATION + " is that"
        " one character alone ('+', '-') or the character followed by a digit ('-1 day');"
        " write other such values as a concatenation: '(' || 'none)'.",
        limit,
    ]
    if options.mode is QueryMode.TENANT:
        parts.append("No SELECT *; list the columns.")
    if options.allow_abstain:
        parts.append(
            "If the question cannot be answered from this database, output"
            " 'ABSTAIN: ' followed by a one-sentence reason instead of SQL."
        )
    return " ".join(parts)


def trie_regex(words: Iterable[str]) -> str:
    """Prefix-factored regex matching exactly `words`.

    The API's grammar budget charges per regex character, so shared prefixes are written once:
    {`abc`, `abd`, `x`} becomes `(?:ab(?:c|d)|x)`. Optional tails are greedy, so Python's `re`
    (used by lark) still prefers the longest word, as llguidance's greedy lexer does.
    """
    trie: _Trie = {}
    for word in words:
        node = trie
        for ch in word:
            node = node.setdefault(ch, {})
        node[""] = {}
    return _trie_body(trie)


def _trie_body(node: _Trie) -> str:
    branches = []
    for first in sorted(k for k in node if k):
        label, child = first, node[first]
        while len(child) == 1 and "" not in child:
            ((ch, child),) = child.items()
            label += ch
        branches.append(_regex_escape(label) + _trie_body(child))
    if not branches:
        return ""
    body = branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"
    if "" not in node:
        return body
    return body + "?" if len(branches) > 1 else f"(?:{body})?"


def int_range_regex(upper: int) -> str:
    """Regex matching the decimal integers 1..upper without leading zeros.

    Branches run from the widest to the narrowest because Python's `re`, which lark uses,
    stops at the first alternative that matches.
    """
    digits = str(upper)
    width = len(digits)
    branches = [digits]
    for i, ch in enumerate(digits):
        low, high = (1 if i == 0 else 0), int(ch) - 1
        if high >= low:
            branches.append(digits[:i] + _digit_class(low, high) + _any_digits(width - i - 1))
    branches += [_digit_class(1, 9) + _any_digits(k) for k in range(width - 2, -1, -1)]
    return "(?:" + "|".join(branches) + ")"


def _any_digits(count: int) -> str:
    return f"[0-9]{{{count}}}" if count else ""


def _digit_class(low: int, high: int) -> str:
    return str(low) if low == high else f"[{low}-{high}]"


def _regex_escape(text: str) -> str:
    """Escape for both Python `re` and Rust `regex`, inside a Lark `/.../` literal."""
    return "".join("\\" + ch if ch in _REGEX_META else ch for ch in text)


def _check_reserved_names(schema: DatabaseSchema) -> None:
    """Tables may not be named like an alias; columns may not equal `T1` or `cte1` exactly,
    or the column would be lexed as the start of a qualified reference."""
    reserved = {n.lower() for n in (*TABLE_ALIASES, *CTE_NAMES)}
    clashes = sorted(t.name for t in schema.tables if t.name.lower() in reserved)
    clashes += sorted(
        c.name for t in schema.tables for c in t.columns if c.name in TABLE_ALIASES + CTE_NAMES
    )
    if clashes:
        raise ValueError(f"schema uses names reserved for aliases: {', '.join(clashes)}")
