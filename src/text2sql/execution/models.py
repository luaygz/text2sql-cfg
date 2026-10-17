"""Value types shared by the executor, its worker process and callers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

type Cell = int | float | str | bytes | None
type Row = tuple[Cell, ...]
type Params = Mapping[str, int | float | str]
"""Named parameters (`:tenant_id`), always bound by sqlite3, never spliced into the SQL text."""

DEFAULT_FUNCTIONS: Final = frozenset(
    {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "round",
        "abs",
        "coalesce",
        "iif",
        "nullif",
        "length",
        "upper",
        "lower",
        "trim",
        "substr",
        "instr",
        "replace",
        "strftime",
        "date",
        "julianday",
        # SQLite authorizes the LIKE / NOT LIKE operator as a call to the function "like", and the
        # CURRENT_DATE / CURRENT_TIME / CURRENT_TIMESTAMP keywords as calls to same-named functions.
        # CAST, CASE, BETWEEN, IN, IS NULL, || and TRUE/FALSE compile to opcodes and need no
        # permission.
        "like",
        "current_date",
        "current_time",
        "current_timestamp",
    }
)
"""SQL functions the authorizer allows by default: the function allowlist, as SQLite names them."""


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    timeout_s: float = 2.0
    """Time limit for preparing, running and fetching one query. Always enforced as a budget of
    `text2sql.sqlite_budget.steps_for(timeout_s)` SQLite VM steps, and also as `timeout_s` of wall
    time while `wall_clock` is set; either raises `QueryTimeout`. A worker still busy after
    `executor.kill_after(limits)` seconds of wall time is killed, which raises it too."""
    wall_clock: bool = True
    """Stop at `timeout_s` of wall time as well as at the step budget. Keep it on wherever a user
    is waiting and a slow query is a denial of service (production and tenant requests). Turn it
    off only where reproducibility matters more, i.e. benchmark candidates and evaluation runs:
    then the outcome depends on the step count alone, and the kill moves out to
    `max(5 x timeout_s, timeout_s + 10 s)`."""
    clock: str | None = None
    """A fixed "now" (UTC, `YYYY-MM-DD HH:MM:SS`) that `'now'`, omitted time values and
    `CURRENT_*` read instead of the system clock (`text2sql.sqlite_clock.pin_clock`), so results
    do not change with the calendar; None is the real clock. Set for benchmark candidates only. It
    is fixed when an executor starts: per-call limits with a different clock raise ValueError."""
    max_rows: int = 1000
    """Rows returned at most; `QueryResult.truncated` says whether more existed."""
    max_value_bytes: int = 10_000_000
    """Largest string, blob or row a query may read or build (SQLITE_LIMIT_LENGTH). Without it,
    eight nested REPLACE calls build a 1 GB string, each call a single opcode the progress
    handler cannot interrupt."""
    max_result_bytes: int = 10_000_000
    """Approximate size of the returned result: 8 bytes per column name and per cell, plus the
    length of every name, string (in characters) and blob. Each value can be under
    `max_value_bytes` while the rows together are not: a constant 9.75 MB expression repeated on
    40 rows is 390 MB. The largest full BIRD Mini-Dev gold result measures 0.86 MB."""
    max_memory_bytes: int = 256 * 2**20
    """How far the worker's data segment may grow beyond its size at start-up (RLIMIT_DATA,
    Linux only; not applied to an in-process `Sandbox`). The backstop for what the byte counts
    cannot see before Python has built it, such as one row of many large columns."""

    def __post_init__(self) -> None:
        if not self.timeout_s > 0:
            raise ValueError("timeout_s must be positive")
        if self.max_rows < 0:
            raise ValueError("max_rows must be non-negative")
        for name in ("max_value_bytes", "max_result_bytes", "max_memory_bytes"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.clock is not None:
            try:
                datetime.strptime(self.clock, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValueError(
                    f"clock must look like 'YYYY-MM-DD HH:MM:SS', got {self.clock!r}"
                ) from None


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    readable: Mapping[str, frozenset[str]] | None = None
    """Table or view -> columns that may be read. None means every user table and view.

    Names are matched case-insensitively. The authorizer checks every column a statement touches,
    including columns used only in WHERE/JOIN and the base-table columns behind a view, so a scoped
    query that filters on `tenant_id` needs `tenant_id` listed here even though the model never
    sees it. SQLite's internal tables (`sqlite_master` and friends) and eponymous virtual tables
    (`pragma_*`, `json_each`, `dbstat`) are never readable.
    """
    functions: frozenset[str] = DEFAULT_FUNCTIONS
    """Lowercase SQLite function names the statement may call."""
    allow_recursive: bool = False
    """Permit recursive CTEs. Off by default: the grammar cannot produce them and they are the
    easiest way to write an unbounded query."""


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    truncated: bool
    """True when the query had more than `ExecutionLimits.max_rows` rows."""
    elapsed_s: float
    """Time SQLite spent preparing, running and fetching, measured inside the worker."""
