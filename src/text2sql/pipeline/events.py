"""Progress events for live views, and per-request collection of safety events.

`PipelineEvent`s go to an optional synchronous callback (the web demo streams them). A callback
that raises is logged and ignored: a broken viewer must never change an answer.

Safety events are written by the shared per-database guard, which serves many requests at once.
`CollectingEventLog` also appends each event to the list bound to the current request's context,
so every request's trace holds exactly the events its own candidates caused.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

import structlog

from text2sql.evals.records import JsonScalar
from text2sql.safety import SafetyEvent, SafetyEventLog

log = structlog.get_logger(__name__)

type EventValue = JsonScalar | list[EventValue] | dict[str, EventValue]
EventStatus = Literal["started", "finished", "info"]


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    stage: str
    status: EventStatus
    elapsed_s: float
    """Seconds since `Pipeline.run` started."""
    data: dict[str, EventValue] = field(default_factory=dict)
    """Small, JSON-serialisable payload."""


type EventCallback = Callable[[PipelineEvent], None]


class EventSink:
    """Sends events to the callback, if there is one."""

    def __init__(self, callback: EventCallback | None, started: float) -> None:
        self._callback = callback
        self._started = started

    @property
    def enabled(self) -> bool:
        """Callers check this before building a payload that costs anything."""
        return self._callback is not None

    def emit(
        self, stage: str, status: EventStatus, data: dict[str, EventValue] | None = None
    ) -> None:
        if self._callback is None:
            return
        event = PipelineEvent(stage, status, time.perf_counter() - self._started, data or {})
        try:
            self._callback(event)
        except Exception:
            log.warning("pipeline_event_callback_failed", stage=stage, status=status, exc_info=True)


_collector: ContextVar[list[SafetyEvent] | None] = ContextVar(
    "text2sql_safety_collector", default=None
)


@contextmanager
def collect_safety_events(into: list[SafetyEvent]) -> Iterator[None]:
    """Append every event recorded in this context (and tasks started from it) to `into`."""
    token = _collector.set(into)
    try:
        yield
    finally:
        _collector.reset(token)


class CollectingEventLog(SafetyEventLog):
    """The JSONL safety log, plus a copy of each event for the request that caused it."""

    def record(self, event: SafetyEvent) -> None:
        super().record(event)
        collected = _collector.get()
        if collected is not None:
            collected.append(event)
