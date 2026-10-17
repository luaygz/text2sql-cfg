"""Names and spellings shared by the grammar builder and the gold-SQL normalizer.

The grammar accepts one canonical spelling of every query: upper-case keywords, single spaces,
identifiers quoted only when SQLite needs it, table aliases `T1`..`T9`, CTE names
`cte1`..`cte5` and computed-column aliases `c1`..`c9`. `normalize_sql` rewrites human-written
SQL into the same spelling, so both modules read these constants from here.
"""

from __future__ import annotations

import re

TABLE_ALIASES = tuple(f"T{i}" for i in range(1, 10))
CTE_NAMES = tuple(f"cte{i}" for i in range(1, 6))
COLUMN_ALIASES = tuple(f"c{i}" for i in range(1, 10))

AGGREGATES = ("COUNT", "SUM", "AVG", "MIN", "MAX")
SCALAR_FUNCTIONS = (
    "ROUND",
    "ABS",
    "COALESCE",
    "IIF",
    "NULLIF",
    "LENGTH",
    "UPPER",
    "LOWER",
    "TRIM",
    "SUBSTR",
    "INSTR",
    "REPLACE",
    "STRFTIME",
    "DATE",
    "JULIANDAY",
)
"""The function allowlist minus the aggregates and CAST, which have their own productions."""

CAST_TYPES = ("INTEGER", "REAL", "TEXT", "NUMERIC")
"""The four SQLite column affinities; CAST semantics depend only on the target's affinity."""

CONSTANTS = ("NULL", "TRUE", "FALSE", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP")

TRAP_PUNCTUATION = '"#()*+-./:=?['
"""Characters a string literal may start with only alone or before a digit (ADR-005).

With the API's tokenizer `'+'`, `'-'`, `':'` and the like are a single token together with the
preceding space, and the hosted decoder does not let the model close such a literal once it has
opened it. Other values starting with these characters are written as a concatenation:
`'(' || 'none)'`.
"""

# https://www.sqlite.org/lang_keywords.html (147 keywords, read 2026-10-16).
_SQLITE_KEYWORD_TEXT = """
    ABORT ACTION ADD AFTER ALL ALTER ALWAYS ANALYZE AND AS ASC ATTACH AUTOINCREMENT BEFORE
    BEGIN BETWEEN BY CASCADE CASE CAST CHECK COLLATE COLUMN COMMIT CONFLICT CONSTRAINT CREATE
    CROSS CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP DATABASE DEFAULT DEFERRABLE
    DEFERRED DELETE DESC DETACH DISTINCT DO DROP EACH ELSE END ESCAPE EXCEPT EXCLUDE EXCLUSIVE
    EXISTS EXPLAIN FAIL FILTER FIRST FOLLOWING FOR FOREIGN FROM FULL GENERATED GLOB GROUP
    GROUPS HAVING IF IGNORE IMMEDIATE IN INDEX INDEXED INITIALLY INNER INSERT INSTEAD INTERSECT
    INTO IS ISNULL JOIN KEY LAST LEFT LIKE LIMIT MATCH MATERIALIZED NATURAL NO NOT NOTHING
    NOTNULL NULL NULLS OF OFFSET ON OR ORDER OTHERS OUTER OVER PARTITION PLAN PRAGMA PRECEDING
    PRIMARY QUERY RAISE RANGE RECURSIVE REFERENCES REGEXP REINDEX RELEASE RENAME REPLACE
    RESTRICT RETURNING RIGHT ROLLBACK ROW ROWS SAVEPOINT SELECT SET TABLE TEMP TEMPORARY THEN
    TIES TO TRANSACTION TRIGGER UNBOUNDED UNION UNIQUE UPDATE USING VACUUM VALUES VIEW VIRTUAL
    WHEN WHERE WINDOW WITH WITHOUT
"""
SQLITE_KEYWORDS = frozenset(_SQLITE_KEYWORD_TEXT.split())

_BARE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_GRAMMAR_WORDS = frozenset((*AGGREGATES, *SCALAR_FUNCTIONS, *CAST_TYPES, *CONSTANTS))


def sql_identifier(name: str) -> str:
    """Spell an identifier the way the grammar emits it.

    Names that are plain ASCII words stay bare; anything else, SQLite keywords included, is
    wrapped in backticks as BIRD gold SQL does. An all-caps name equal to a function or type
    word the grammar uses (say a column called `DATE`) is quoted too, so that a column can
    never be lexed as the start of a function call.
    """
    if _BARE.fullmatch(name) and name.upper() not in SQLITE_KEYWORDS and name not in _GRAMMAR_WORDS:
        return name
    return "`" + name.replace("`", "``") + "`"
