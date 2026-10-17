"""`SandboxedExecutor`: run one SQL statement against a SQLite file inside a killable worker.

Process model: each executor keeps a small pool (at most `max_workers`) of persistent worker
processes for its database, started on first use. Inside the worker a query is bounded by a
budget of SQLite VM steps and, unless `ExecutionLimits.wall_clock` is off, by its wall-clock
limit. The parent waits for a reply for `kill_after(limits)` seconds and then kills the worker,
which is replaced on the next call. docs/adr/007-sandboxed-executor.md has the measurements.

Concurrency: `execute` is thread-safe; at most `max_workers` statements run at once and further
callers block until a worker is free. `execute_async` runs `execute` in a thread, and waits for a
free slot on the event loop first, so queued calls do not each hold a thread.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import threading
import weakref
from multiprocessing.connection import Connection
from pathlib import Path
from types import TracebackType
from typing import Final, Self

from text2sql.execution.errors import ExecutionError, QueryTimeout
from text2sql.execution.models import AccessPolicy, ExecutionLimits, Params, QueryResult
from text2sql.execution.protocol import (
    check_ready,
    decode_reply,
    encode_request,
    encode_setup,
    max_reply_bytes,
)

KILL_GRACE_S: Final = 1.0
"""With a wall-clock limit: time past `timeout_s` before the kill. The handler normally stops the
query on time; this covers result serialization and work hidden inside single VM steps."""
KILL_FACTOR: Final = 5.0
KILL_MIN_GRACE_S: Final = 10.0
STARTUP_TIMEOUT_S: Final = 30.0
STOP_TIMEOUT_S: Final = 1.0
MAX_HANDSHAKE_REPLY_BYTES: Final = 65_536
DEFAULT_LIMITS: Final = ExecutionLimits()


def kill_after(limits: ExecutionLimits) -> float:
    """Wall-clock seconds the parent waits for a reply before killing the worker.

    With `wall_clock` on, the kill follows the time limit closely: a user is waiting, and it also
    ends work hidden inside single VM steps, which the progress handler never gets to check.
    Without it the kill is only a backstop, set well above the step budget's nominal duration so
    that load alone does not decide outcomes; it still ends a hung worker and queries whose steps
    run 20 to over 100 times longer than the calibration rate (long-text sorts, LIKE scans).
    """
    if limits.wall_clock:
        return limits.timeout_s + KILL_GRACE_S
    return max(KILL_FACTOR * limits.timeout_s, limits.timeout_s + KILL_MIN_GRACE_S)


class SandboxedExecutor:
    def __init__(
        self,
        db_path: Path,
        *,
        limits: ExecutionLimits = DEFAULT_LIMITS,
        access: AccessPolicy | None = None,
        max_workers: int = 2,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        # The workers' clock is fixed when they open the database (see `ExecutionLimits.clock`).
        self._setup = encode_setup(
            db_path.resolve(strict=True), access or AccessPolicy(), limits.clock
        )
        self._limits = limits
        self._max_workers = max_workers
        self._slots = threading.BoundedSemaphore(max_workers)
        self._lock = threading.Lock()
        self._idle: list[_Worker] = []
        self._closed = False
        self._gates: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
            weakref.WeakKeyDictionary()
        )

    def execute(
        self, sql: str, params: Params | None = None, *, limits: ExecutionLimits | None = None
    ) -> QueryResult:
        """Run one statement. Raises QueryTimeout, AccessDenied or QueryFailed; never retries.

        `limits` overrides the executor's limits for this call (e.g. a longer timeout for gold SQL),
        except for the clock, which is fixed for the executor's life: a different one is a
        ValueError.
        """
        limits = limits or self._limits
        if limits.clock != self._limits.clock:
            raise ValueError(
                f"this executor's clock is {self._limits.clock!r}, not {limits.clock!r}"
            )
        request = encode_request(sql, params, limits)
        max_reply = max_reply_bytes(len(request), limits)
        with self._slots:
            worker = self._checkout()
            try:
                reply = worker.call(request, kill_after(limits), max_reply)
                outcome = None if reply is None else decode_reply(reply)
            except BaseException:
                worker.kill()
                raise
            if outcome is None:
                worker.kill()
                raise QueryTimeout(limits.timeout_s)
            self._checkin(worker)
        if isinstance(outcome, ExecutionError):
            raise outcome
        return outcome

    async def execute_async(
        self, sql: str, params: Params | None = None, *, limits: ExecutionLimits | None = None
    ) -> QueryResult:
        """`execute` without blocking the event loop.

        Cancelling the awaiting task does not stop a query already sent to a worker; it finishes
        or times out within the limits and the worker returns to the pool.
        """
        async with self._gate():
            return await asyncio.to_thread(self.execute, sql, params, limits=limits)

    def close(self) -> None:
        """Stop idle workers now; workers busy in other threads stop when their query ends."""
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, []
        for worker in idle:
            worker.stop()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _checkout(self) -> _Worker:
        with self._lock:
            if self._closed:
                raise RuntimeError("executor is closed")
            while self._idle:
                worker = self._idle.pop()
                if worker.alive:
                    return worker
                worker.kill()
        return _Worker.start(self._setup)

    def _checkin(self, worker: _Worker) -> None:
        with self._lock:
            if not self._closed:
                self._idle.append(worker)
                return
        worker.stop()

    def _gate(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        with self._lock:
            gate = self._gates.get(loop)
            if gate is None:
                gate = self._gates[loop] = asyncio.Semaphore(self._max_workers)
            return gate


class _Worker:
    """One worker process and the socket to it."""

    def __init__(self, process: subprocess.Popen[bytes], conn: Connection) -> None:
        self._process = process
        self._conn = conn

    @classmethod
    def start(cls, setup: bytes) -> _Worker:
        ours, theirs = socket.socketpair()
        with theirs:
            try:
                # -P: do not put the working directory on sys.path in the worker.
                process = subprocess.Popen(
                    [sys.executable, "-P", "-m", "text2sql.execution.worker", str(theirs.fileno())],
                    pass_fds=(theirs.fileno(),),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
            except BaseException:
                ours.close()
                raise
        worker = cls(process, Connection(ours.detach()))
        try:
            worker._handshake(setup)
        except BaseException:
            worker.kill()
            raise
        return worker

    def _handshake(self, setup: bytes) -> None:
        reply = self.call(setup, STARTUP_TIMEOUT_S, MAX_HANDSHAKE_REPLY_BYTES)
        if reply is None:
            raise ExecutionError(f"sandbox worker did not start within {STARTUP_TIMEOUT_S:g} s")
        check_ready(reply)

    @property
    def alive(self) -> bool:
        return self._process.poll() is None

    def call(self, message: bytes, wait_s: float, max_reply: int) -> bytes | None:
        """Send one message and return the reply, or None if none arrived within `wait_s`.

        A reply longer than `max_reply` bytes is refused before it is read into memory.
        """
        try:
            self._conn.send_bytes(message)
            if not self._conn.poll(wait_s):
                return None
            return self._conn.recv_bytes(max_reply)
        except EOFError as exc:
            raise ExecutionError("sandbox worker exited unexpectedly") from exc
        except OSError as exc:  # also "bad message length" for an oversized reply
            raise ExecutionError(f"sandbox worker connection failed: {exc}") from exc

    def stop(self) -> None:
        self._conn.close()  # the worker sees EOF and exits
        try:
            self._process.wait(timeout=STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            self.kill()

    def kill(self) -> None:
        self._process.kill()
        self._process.wait()
        self._conn.close()
