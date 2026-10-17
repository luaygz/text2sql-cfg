"""Time limits for SQLite measured in virtual-machine steps instead of seconds.

A wall-clock limit makes the outcome of a slow query depend on how busy the machine is: in the
final dev runs a prediction that takes 9 s on an idle machine hit BIRD's 30 s limit while eight
questions ran at once, and a replay scored it differently. SQLite's progress handler runs every
`CHECK_INTERVAL` virtual-machine instructions, so counting its calls gives a budget that ends at
the same instruction on every run. Connections that use a budget must be opened with
`cached_statements=0`: SQLite starts a re-run statement's progress count where its previous run
stopped, so a reused prepared statement would make the charge depend on history.

Budgets are written in seconds and converted at `STEPS_PER_SECOND`, measured on the reference
machine (Ryzen-class desktop, SQLite 3.50.4): BIRD's slowest gold query that finishes (question
518) ran 3.03e9 steps in 36 s, about 84 M steps/s, and a heavy NOT EXISTS prediction ran 1.07e9
steps in 8.9 s. At 84 M steps/s the official 30 s limit is 2.52e9 steps, which keeps both on the
side of the limit they fell on when timed alone.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

STEPS_PER_SECOND: Final = 84_000_000
CHECK_INTERVAL: Final = 10_000


def steps_for(seconds: float) -> int:
    """The step budget that stands for `seconds` of SQLite work on the reference machine."""
    if seconds <= 0:
        raise ValueError(f"a budget must be positive, got {seconds} s")
    return max(CHECK_INTERVAL, int(seconds * STEPS_PER_SECOND))


class StepBudget:
    """A progress handler that interrupts the statement once `steps` instructions have run, or
    once `wall_s` seconds have passed if a wall-clock limit is given.

    The two serve different ends. The step budget is what decides an outcome reproducibly
    (benchmark candidates, scoring). The wall-clock limit is a guarantee about time, for requests
    where a user is waiting and a slow query is a denial-of-service risk (production and tenant
    modes), and a backstop elsewhere against query shapes that run few steps per second. A
    statement stopped by the clock may have finished on an idle machine, so its outcome depends on
    load; `exhausted` and `timed_out` say which limit stopped it.

    One budget can span several statements (`used` keeps counting across them).
    """

    def __init__(self, steps: int, *, wall_s: float | None = None) -> None:
        self.steps = steps
        self.used = 0
        self.exhausted = False
        self.timed_out = False
        self._deadline = None if wall_s is None else time.monotonic() + wall_s

    @property
    def stopped(self) -> bool:
        return self.exhausted or self.timed_out

    def __call__(self) -> int:
        self.used += CHECK_INTERVAL
        if self.used > self.steps:
            self.exhausted = True
            return 1
        if self._deadline is not None and time.monotonic() > self._deadline:
            self.timed_out = True
            return 1
        return 0


@contextmanager
def step_budget(
    conn: sqlite3.Connection, steps: int, *, wall_s: float | None = None
) -> Iterator[StepBudget]:
    """Install a `StepBudget` on `conn` for the duration of the block."""
    budget = StepBudget(steps, wall_s=wall_s)
    conn.set_progress_handler(budget, CHECK_INTERVAL)
    try:
        yield budget
    finally:
        conn.set_progress_handler(None, 0)
