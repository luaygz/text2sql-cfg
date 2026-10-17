"""A fixed "now" for SQLite, so benchmark results do not change with the calendar.

Twelve BIRD Mini-Dev gold queries compute ages or durations from `'now'` or `CURRENT_DATE`, and
the model's answers to them do the same, so their results change from one day to the next and a
replay on another day disagrees with the recorded run. `pin_clock` replaces SQLite's date
functions on one connection with wrappers that read `BENCHMARK_NOW` wherever SQLite would read
the system clock: a `'now'` argument, an omitted time value (`date()`, `strftime('%Y')`), and
`CURRENT_DATE`, `CURRENT_TIME`, `CURRENT_TIMESTAMP`. Connections for benchmark candidates and for
scoring are pinned; production and tenant requests keep the real clock.

The wrappers forward to SQLite's own functions on a private in-memory connection, with the
arguments bound as parameters, so every other argument behaves exactly as before. Pinning is
unconditional rather than decided by looking at the SQL, because SQLite reads the clock in more
ways than a pattern can see (`date('n' || 'ow')`). The price is a Python call per date-function
call: a 92k-row `STRFTIME` scan of BIRD's `posts` table takes 0.16 s instead of 0.04 s.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Final

BENCHMARK_NOW: Final = "2026-10-16 12:00:00"
"""UTC, the day every reported benchmark run was recorded."""

_TIME_VALUE_POSITION: Final = {
    "date": 0,
    "time": 0,
    "datetime": 0,
    "julianday": 0,
    "unixepoch": 0,
    "strftime": 1,
}
"""Index of the time-value argument; SQLite reads the clock when the call stops before it."""

type SqlValue = str | int | float | bytes | None


def pin_clock(conn: sqlite3.Connection, now: str = BENCHMARK_NOW) -> None:
    """Make every way of reading the current date or time on `conn` return `now`."""
    builtin = sqlite3.connect(":memory:", check_same_thread=False)

    def forward(name: str, position: int) -> Callable[..., SqlValue]:
        def call(*args: SqlValue) -> SqlValue:
            fixed = [now if isinstance(a, str) and a.lower() == "now" else a for a in args]
            if len(fixed) == position:
                fixed.append(now)
            row = builtin.execute(f"SELECT {name}({', '.join('?' * len(fixed))})", fixed)
            value: SqlValue = row.fetchone()[0]
            return value

        return call

    for name, position in _TIME_VALUE_POSITION.items():
        conn.create_function(name, -1, forward(name, position), deterministic=True)
    conn.create_function("current_date", 0, lambda: now[:10], deterministic=True)
    conn.create_function("current_time", 0, lambda: now[11:], deterministic=True)
    conn.create_function("current_timestamp", 0, lambda: now, deterministic=True)
