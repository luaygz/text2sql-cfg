"""The SQLite authorizer callback: an allowlist every prepared statement must satisfy.

SQLite calls the authorizer while compiling a statement, once per action: SQLITE_SELECT for each
SELECT core, SQLITE_READ for each (table, column) touched (column "" when a table is scanned
without reading a column, e.g. `count(*)`), SQLITE_FUNCTION per function call, SQLITE_RECURSIVE
for a recursive CTE, and a distinct action for every write, DDL, PRAGMA, ATTACH or transaction
statement. Anything not explicitly allowed here is denied, so new statement kinds fail closed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

_ACTION_NAMES: Final = {
    getattr(sqlite3, name): name.removeprefix("SQLITE_")
    for name in (
        "SQLITE_CREATE_INDEX",
        "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE",
        "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW",
        "SQLITE_CREATE_TRIGGER",
        "SQLITE_CREATE_VIEW",
        "SQLITE_DELETE",
        "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX",
        "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW",
        "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW",
        "SQLITE_INSERT",
        "SQLITE_PRAGMA",
        "SQLITE_READ",
        "SQLITE_SELECT",
        "SQLITE_TRANSACTION",
        "SQLITE_UPDATE",
        "SQLITE_ATTACH",
        "SQLITE_DETACH",
        "SQLITE_ALTER_TABLE",
        "SQLITE_REINDEX",
        "SQLITE_ANALYZE",
        "SQLITE_CREATE_VTABLE",
        "SQLITE_DROP_VTABLE",
        "SQLITE_FUNCTION",
        "SQLITE_SAVEPOINT",
        "SQLITE_RECURSIVE",
    )
}

_INTERNAL_PREFIX: Final = "sqlite_"


@dataclass(frozen=True, slots=True)
class Denial:
    action: str
    target: str


class Authorizer:
    """Callable for `sqlite3.Connection.set_authorizer`.

    `readable` maps lowercase table/view names to the lowercase columns that may be read, or to
    None when every column may be read. `schema_objects` is every table and view in the database.
    `denial` holds the first refusal since `reset()`, so the caller can report what was refused
    instead of SQLite's generic "not authorized".
    """

    def __init__(
        self,
        readable: Mapping[str, frozenset[str] | None],
        schema_objects: frozenset[str],
        functions: frozenset[str],
        *,
        allow_recursive: bool,
    ) -> None:
        self._readable = readable
        self._schema_objects = schema_objects
        self._functions = functions
        self._allow_recursive = allow_recursive
        self.denial: Denial | None = None

    def reset(self) -> None:
        self.denial = None

    def __call__(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        db_name: str | None,
        source: str | None,
    ) -> int:
        if self._allows(action, arg1, arg2, db_name):
            return sqlite3.SQLITE_OK
        if self.denial is None:
            name = _ACTION_NAMES.get(action, str(action))
            self.denial = Denial(name, _describe(action, arg1, arg2, db_name))
        return sqlite3.SQLITE_DENY

    def _allows(self, action: int, arg1: str | None, arg2: str | None, db: str | None) -> bool:
        if action == sqlite3.SQLITE_SELECT:
            return True
        if action == sqlite3.SQLITE_READ:
            return self._may_read(arg1, arg2, db)
        if action == sqlite3.SQLITE_FUNCTION:
            return arg2 is not None and arg2.lower() in self._functions
        return action == sqlite3.SQLITE_RECURSIVE and self._allow_recursive

    def _may_read(self, table: str | None, column: str | None, db_name: str | None) -> bool:
        if table is None or db_name not in (None, "main"):
            return False
        key = table.lower()
        if key.startswith(_INTERNAL_PREFIX):
            return False
        if key in self._readable:
            columns = self._readable[key]
            return columns is None or not column or column.lower() in columns
        # SQLite also reports a column-less scan of a CTE (e.g. `SELECT count(*) FROM cte`) by the
        # CTE's name. Such a name is not a schema object; the CTE's own reads are checked when its
        # body is compiled. Eponymous virtual tables pass this test too, but every column read of
        # one, and the PRAGMA behind each pragma_* function, is still denied.
        return not column and key not in self._schema_objects


def _describe(action: int, arg1: str | None, arg2: str | None, db_name: str | None) -> str:
    if action == sqlite3.SQLITE_READ:
        target = f"{arg1}.{arg2}" if arg2 else str(arg1)
        return target if db_name in (None, "main") else f"{db_name}.{target}"
    if action == sqlite3.SQLITE_FUNCTION:
        return str(arg2)
    return " ".join(arg for arg in (arg1, arg2) if arg)
