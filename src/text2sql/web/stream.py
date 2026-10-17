"""One pipeline run streamed to the browser as NDJSON, one JSON object per line.

Line types, in order: `run` (what is being run, for which identity), any number of `event`
(a `PipelineEvent`), then exactly one terminal line, `done` (the `Answer`) or `error`.
The terminal line is written in a `finally` before anything else can fail there, so it does
not depend on logging working: a structlog logger bound to a closed stderr once swallowed it.
The run executes in its own task and is not cancelled when the client goes away: an API call
already in flight is billed either way, and finishing it keeps the spend ledger exact.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Protocol

import structlog

from text2sql.llm import BudgetExceeded, CacheMiss
from text2sql.pipeline import Answer, PipelineEvent, Request

log = structlog.get_logger(__name__)

NDJSON = "application/x-ndjson"

# Exceptions whose messages are safe and useful to show: spend caps, offline replay gaps and
# missing build artifacts. Anything else is reported without its message, which could carry
# request internals.
_REPORTED: tuple[tuple[type[Exception], str], ...] = (
    (BudgetExceeded, "budget_exceeded"),
    (CacheMiss, "cache_miss"),
    (FileNotFoundError, "missing_resource"),
)


class PipelineRunner(Protocol):
    async def run(
        self, request: Request, *, on_event: Callable[[PipelineEvent], None] | None = None
    ) -> tuple[Answer, object]: ...


def encode(line: Mapping[str, object]) -> bytes:
    # default=str: event data is meant to be JSON already; a stray value (bytes from a BLOB
    # column) is shown as text rather than ending the stream.
    return (json.dumps(line, default=str, ensure_ascii=False) + "\n").encode()


def event_line(event: PipelineEvent) -> dict[str, object]:
    return {
        "type": "event",
        "stage": event.stage,
        "status": event.status,
        "elapsed_s": round(event.elapsed_s, 4),
        "data": event.data,
    }


INTERRUPTED: dict[str, object] = {
    "type": "error",
    "error": "interrupted",
    "detail": "the run stopped before it finished (server shutting down?)",
}
"""Terminal line when the task ends without a result or an exception (cancellation)."""


def error_line(exc: Exception) -> dict[str, object]:
    for kind, name in _REPORTED:
        if isinstance(exc, kind):
            return {"type": "error", "error": name, "detail": str(exc)}
    return {
        "type": "error",
        "error": "internal_error",
        "detail": "the pipeline failed; the server log has the traceback",
    }


def start_run(
    runner: PipelineRunner,
    request: Request,
    *,
    header: Mapping[str, object],
    on_finish: Callable[[], None],
    tasks: set[asyncio.Task[None]],
) -> AsyncIterator[bytes]:
    """Start `request` now and return the iterator of its NDJSON lines.

    `on_finish` runs when the pipeline task ends, whether or not anyone reads the stream, so
    a concurrency slot cannot leak. `tasks` keeps a strong reference to the running task.
    """
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    started = time.perf_counter()

    async def run() -> None:
        terminal = INTERRUPTED
        try:
            answer, _trace = await runner.run(
                request, on_event=lambda event: queue.put_nowait(encode(event_line(event)))
            )
            terminal = {
                "type": "done",
                "answer": answer.model_dump(mode="json"),
                "wall_s": round(time.perf_counter() - started, 3),
            }
        except Exception as exc:
            terminal = error_line(exc)
            if terminal["error"] == "internal_error":
                # May itself raise (a broken log stream); the finally still ends the stream,
                # and asyncio reports the task's exception through stdlib logging.
                log.exception("demo_run_failed", db_id=request.db_id)
        finally:
            queue.put_nowait(encode(terminal))
            queue.put_nowait(None)
            on_finish()

    task = asyncio.create_task(run())
    tasks.add(task)
    task.add_done_callback(tasks.discard)

    async def lines() -> AsyncIterator[bytes]:
        yield encode(header)
        while (item := await queue.get()) is not None:
            yield item

    return lines()
