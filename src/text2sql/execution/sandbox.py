"""A read-only, authorizer-guarded SQLite connection with a step budget per query.

This is the code that runs inside the worker process. It is kept free of process management so it
can be tested in-process; `executor.SandboxedExecutor` adds the process boundary and the hard kill.

With a fixed clock (`ExecutionLimits.clock`, benchmark mode), the connection's date functions are
replaced at open by `text2sql.sqlite_clock.pin_clock`. The overrides cannot be removed cleanly, so
a sandbox keeps the clock it was opened with for its whole life.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Final
from urllib.parse import quote

from text2sql.execution.authorizer import Authorizer
from text2sql.execution.errors import (
    OUT_OF_MEMORY,
    AccessDenied,
    ExecutionError,
    QueryFailed,
    QueryTimeout,
    ResultTooLarge,
)
from text2sql.execution.models import AccessPolicy, ExecutionLimits, Params, QueryResult, Row
from text2sql.sqlite_budget import step_budget, steps_for
from text2sql.sqlite_clock import pin_clock

CELL_OVERHEAD: Final = 8
"""Bytes counted per cell and per column name on top of its length (see `max_result_bytes`)."""


class Sandbox:
    def __init__(self, db_path: Path, access: AccessPolicy, *, clock: str | None = None) -> None:
        self._con, schema_objects = _open(f"file:{quote(str(db_path.resolve()))}?mode=ro")
        if clock is not None:
            # The overrides keep the built-in names, so the authorizer allows exactly the same
            # calls (`strftime`, `date`, ...) and still refuses `datetime`, `time`, `unixepoch`.
            pin_clock(self._con, clock)
        self._clock = clock
        self._authorizer = Authorizer(
            _readable(schema_objects, access.readable),
            schema_objects,
            frozenset(name.lower() for name in access.functions),
            allow_recursive=access.allow_recursive,
        )
        self._con.set_authorizer(self._authorizer)

    def run(self, sql: str, params: Params | None, limits: ExecutionLimits) -> QueryResult:
        """Execute one statement; raises QueryTimeout, AccessDenied or QueryFailed.

        The time limit is `steps_for(limits.timeout_s)` SQLite VM steps and, when
        `limits.wall_clock` is set, also `timeout_s` of wall time, checked at the same points.
        Size limits raise `ResultTooLarge`, a QueryFailed. `max_memory_bytes` is enforced only by
        the worker process, but a MemoryError raised here is reported the same way.
        `limits.clock` must be the clock the sandbox was opened with (ValueError otherwise).
        """
        if limits.clock != self._clock:
            raise ValueError(f"this sandbox's clock is {self._clock!r}, not {limits.clock!r}")
        self._authorizer.reset()
        self._con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, limits.max_value_bytes)
        started = time.perf_counter()
        steps = steps_for(limits.timeout_s)
        wall_s = limits.timeout_s if limits.wall_clock else None
        with step_budget(self._con, steps, wall_s=wall_s) as budget:
            try:
                cursor = self._con.execute(sql, dict(params) if params else ())
                try:
                    columns = tuple(col[0] for col in cursor.description or ())
                    rows, truncated = _fetch(cursor, columns, limits)
                finally:
                    cursor.close()
            # OverflowError: an int parameter beyond 64 bits; UnicodeEncodeError: lone surrogates.
            except (sqlite3.Error, OverflowError, UnicodeEncodeError) as exc:
                raise self._classify(exc, timed_out=budget.stopped, limits=limits) from None
            except MemoryError:
                raise ResultTooLarge(OUT_OF_MEMORY) from None
        return QueryResult(
            columns=columns,
            rows=tuple(rows),
            truncated=truncated,
            elapsed_s=time.perf_counter() - started,
        )

    def close(self) -> None:
        self._con.close()

    def _classify(
        self, exc: Exception, *, timed_out: bool, limits: ExecutionLimits
    ) -> ExecutionError:
        if timed_out:
            return QueryTimeout(limits.timeout_s)
        if self._authorizer.denial is not None:
            return AccessDenied(self._authorizer.denial.action, self._authorizer.denial.target)
        # mode=ro and query_only still block a write if the authorizer ever lets one through. Only
        # the plain code counts: extended codes such as READONLY_ROLLBACK (a hot journal left by
        # a crashed writer) are infrastructure faults, not refused statements.
        code = getattr(exc, "sqlite_errorcode", None)
        if code == sqlite3.SQLITE_READONLY:
            return AccessDenied("WRITE", str(exc))
        if code == sqlite3.SQLITE_TOOBIG:
            return ResultTooLarge(str(exc))
        return QueryFailed(str(exc))


def _open(uri: str) -> tuple[sqlite3.Connection, frozenset[str]]:
    """A read-only connection with its schema loaded, and the names of its tables and views."""
    # isolation_level=None: the sqlite3 module must never issue an implicit BEGIN.
    # cached_statements=0: SQLite starts a statement's progress-handler phase from the steps it
    # ran in earlier executions, so a reused prepared statement would be checked at different
    # points than a fresh one and a query at the edge of its budget could flip.
    con = sqlite3.connect(uri, uri=True, isolation_level=None, cached_statements=0)
    try:
        con.execute("PRAGMA query_only = ON")
        con.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        schema_objects = frozenset(
            str(name).lower()
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        )
    except BaseException:
        con.close()
        raise
    return con, schema_objects


def cell_bytes(value: object) -> int:
    """What one cell or column name counts against `max_result_bytes`."""
    if isinstance(value, str | bytes):
        return CELL_OVERHEAD + len(value)
    return CELL_OVERHEAD


def _fetch(
    cursor: sqlite3.Cursor, columns: tuple[str, ...], limits: ExecutionLimits
) -> tuple[list[Row], bool]:
    """Rows up to `max_rows`, and whether more existed.

    Rows are converted one at a time so the result size is checked between them: a constant
    9.75 MB expression is computed once, after which each row costs SQLite a few VM steps while
    the sqlite3 module copies 9.75 MB into it, so neither the step budget nor the per-value limit
    bounds the result. The Python work done here is bounded by `max_rows + 1` rows and
    `max_result_bytes`, both counted, not timed, so it cannot make the outcome depend on load.
    """
    size = sum(cell_bytes(name) for name in columns)
    rows: list[Row] = []
    for row in cursor:
        if len(rows) == limits.max_rows:
            return rows, True
        size += sum(cell_bytes(cell) for cell in row)
        if size > limits.max_result_bytes:
            raise ResultTooLarge(f"result exceeds {limits.max_result_bytes} bytes")
        rows.append(row)
    return rows, False


def _readable(
    schema_objects: frozenset[str], readable: Mapping[str, frozenset[str]] | None
) -> dict[str, frozenset[str] | None]:
    """Lowercase table/view -> readable columns (None = all), restricted to what exists."""
    if readable is None:
        return dict.fromkeys(schema_objects)
    allowed: dict[str, frozenset[str] | None] = {}
    for table, columns in readable.items():
        key = table.lower()
        if key in schema_objects:
            previous = allowed.get(key) or frozenset()
            allowed[key] = previous | {col.lower() for col in columns}
    return allowed
