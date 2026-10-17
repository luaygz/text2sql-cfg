"""JSON-lines logging (structlog) and trace spans exported to JSONL.

Spans follow the OpenTelemetry data model (trace and span ids, parent, name, start and end in
Unix nanoseconds, status, attributes, resource) so the files can be loaded into OTel tooling,
but no collector or SDK is needed: each finished span is one line in
`runs/traces/<run_id>.jsonl`. Parent links come from a context variable, so spans opened inside
`asyncio` tasks nest under the span that was current when the task was created.
"""

from __future__ import annotations

import json
import logging
import secrets
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog
from structlog.typing import EventDict, WrappedLogger

from text2sql.config import get_settings

AttributeValue = str | int | float | bool | None


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    start_time_unix_nano: int
    attributes: dict[str, AttributeValue] = field(default_factory=dict)

    def set(self, **attributes: AttributeValue) -> None:
        self.attributes.update(attributes)


@dataclass
class _Run:
    run_id: str
    trace_path: Path


_current_span: ContextVar[Span | None] = ContextVar("text2sql_span", default=None)
_runs: list[_Run] = []
"""The active run, if any; a list so it can be replaced without a `global` statement."""


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"


def start_run(run_id: str | None = None, *, traces_dir: Path | None = None) -> str:
    """Make `run_id` (default: a fresh id) the run that spans, logs and the ledger refer to."""
    run_id = run_id or new_run_id()
    directory = traces_dir or get_settings().runs_dir / "traces"
    _runs[:] = [_Run(run_id, directory / f"{run_id}.jsonl")]
    structlog.contextvars.bind_contextvars(run_id=run_id)
    return run_id


def current_run_id() -> str:
    """The active run id, starting a run with a fresh id on first use."""
    if not _runs:
        start_run()
    return _runs[0].run_id


def trace_path() -> Path:
    current_run_id()
    return _runs[0].trace_path


@contextmanager
def span(name: str, **attributes: AttributeValue) -> Iterator[Span]:
    """Time a unit of work; the span is written when the block exits, with ERROR status if it
    raised. Add attributes discovered during the work with `Span.set`."""
    parent = _current_span.get()
    current = Span(
        name=name,
        trace_id=parent.trace_id if parent else secrets.token_hex(16),
        span_id=secrets.token_hex(8),
        parent_id=parent.span_id if parent else None,
        start_time_unix_nano=time.time_ns(),
        attributes=dict(attributes),
    )
    token = _current_span.set(current)
    status: dict[str, str] = {"code": "OK"}
    try:
        yield current
    except BaseException as exc:
        status = {"code": "ERROR", "message": f"{type(exc).__name__}: {exc}"}
        raise
    finally:
        _current_span.reset(token)
        _export(current, time.time_ns(), status)


def _export(finished: Span, end_time_unix_nano: int, status: dict[str, str]) -> None:
    record = {
        "trace_id": finished.trace_id,
        "span_id": finished.span_id,
        "parent_id": finished.parent_id,
        "name": finished.name,
        "kind": "INTERNAL",
        "start_time_unix_nano": finished.start_time_unix_nano,
        "end_time_unix_nano": end_time_unix_nano,
        "status": status,
        "attributes": finished.attributes,
        "resource": {"service.name": "text2sql", "run.id": current_run_id()},
    }
    path = trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _add_trace_context(_logger: WrappedLogger, _method: str, event: EventDict) -> EventDict:
    current = _current_span.get()
    if current is not None:
        event.setdefault("trace_id", current.trace_id)
        event.setdefault("span_id", current.span_id)
    return event


_STDERR_LOCK = threading.Lock()


class _CurrentStderrLogger:
    """Writes each rendered line to whatever `sys.stderr` is at call time.

    structlog's `PrintLoggerFactory(file=sys.stderr)` binds the stream object once; when
    something swaps and later closes `sys.stderr` (a CLI test runner, a notebook), every cached
    logger keeps writing to the closed stream and raises. Lines come from the event loop and
    from worker threads, so each one is written whole under a lock, as structlog's PrintLogger
    does, to keep the output one JSON object per line.
    """

    def msg(self, message: str) -> None:
        with _STDERR_LOCK:
            stream = sys.stderr
            stream.write(message + "\n")
            stream.flush()

    debug = info = warning = warn = error = critical = exception = fatal = log = msg


def _stderr_logger(*_args: object) -> _CurrentStderrLogger:
    return _CurrentStderrLogger()


def configure_logging(level: str = "INFO") -> None:
    """Render every structlog event as one JSON line on stderr, tagged with run and span ids."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_trace_context,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=_stderr_logger,
        cache_logger_on_first_use=True,
    )
