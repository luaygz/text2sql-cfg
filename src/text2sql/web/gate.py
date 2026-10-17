"""Admission control for pipeline runs: one at a time, and a cap on starts per window.

Every run can spend real API money, so the demo refuses (HTTP 429) instead of queueing.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Refusal:
    reason: str
    retry_after_s: int


class RunGate:
    def __init__(
        self,
        *,
        max_runs: int = 6,
        window_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_runs < 1 or window_s <= 0:
            raise ValueError("max_runs must be positive and window_s greater than zero")
        self._max_runs = max_runs
        self._window_s = window_s
        self._clock = clock
        self._starts: deque[float] = deque()
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def try_acquire(self) -> Refusal | None:
        """Claim the single run slot, or say why not. Synchronous, so atomic under asyncio."""
        if self._busy:
            return Refusal("another question is still running; one run at a time", 5)
        now = self._clock()
        while self._starts and now - self._starts[0] >= self._window_s:
            self._starts.popleft()
        if len(self._starts) >= self._max_runs:
            wait = self._starts[0] + self._window_s - now
            return Refusal(
                f"rate limit: at most {self._max_runs} runs per {self._window_s:g} s",
                max(1, math.ceil(wait)),
            )
        self._starts.append(now)
        self._busy = True
        return None

    def release(self) -> None:
        self._busy = False
