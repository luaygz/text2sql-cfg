"""Sandbox worker process: `python -m text2sql.execution.worker <socket fd>`.

A worker serves one database for its whole life: it reads a setup message, opens the sandbox, then
answers one request at a time until the socket closes. The executor kills it if a query overruns.
"""

from __future__ import annotations

import resource
import signal
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from multiprocessing.connection import Connection
from pathlib import Path

from text2sql.execution.errors import OUT_OF_MEMORY, ExecutionError, QueryFailed, ResultTooLarge
from text2sql.execution.models import ExecutionLimits, Params
from text2sql.execution.protocol import (
    READY,
    decode_request,
    decode_setup,
    encode_error,
    encode_result,
)
from text2sql.execution.sandbox import Sandbox

type MemoryCap = Callable[[int], None]


def serve(conn: Connection, *, cap_memory: MemoryCap | None = None) -> None:
    """Answer requests until EOF. `cap_memory(n)` runs before each query with its memory limit."""
    db_path, access, clock = decode_setup(conn.recv_bytes())
    try:
        sandbox = Sandbox(db_path, access, clock=clock)
    except sqlite3.Error as exc:
        conn.send_bytes(encode_error(QueryFailed(str(exc))))
        return
    with closing(sandbox):
        conn.send_bytes(READY)
        while True:
            try:
                data = conn.recv_bytes()
            except EOFError:
                return
            sql, params, limits = decode_request(data)
            if cap_memory is not None:
                cap_memory(limits.max_memory_bytes)
            conn.send_bytes(_answer(sandbox, sql, params, limits))


def _answer(sandbox: Sandbox, sql: str, params: Params, limits: ExecutionLimits) -> bytes:
    try:
        return encode_result(sandbox.run(sql, params, limits))
    except ExecutionError as exc:
        return encode_error(exc)
    except MemoryError:  # building the reply did not fit
        pass
    # Encoded after the except block, once the partial reply it referenced has been released.
    return encode_error(ResultTooLarge(OUT_OF_MEMORY))


def heap_cap() -> MemoryCap:
    """Limit data-segment growth beyond the current size with RLIMIT_DATA, which since Linux 4.7
    also applies to mmap, so large allocations count. RLIMIT_AS would not work: file mappings,
    mostly the locale archive, already put an idle worker at about 260 MB."""
    # Field 6 of statm is data + stack, in pages; the stack is a few hundred kB of slack.
    base = int(Path("/proc/self/statm").read_text().split()[5]) * resource.getpagesize()
    _, hard = resource.getrlimit(resource.RLIMIT_DATA)

    def cap(allowance: int) -> None:
        soft = base + allowance
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        resource.setrlimit(resource.RLIMIT_DATA, (soft, hard))

    return cap


def main() -> None:
    # Ctrl-C reaches the whole process group; the parent handles it and stops its workers.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    with Connection(int(sys.argv[1])) as conn:
        serve(conn, cap_memory=heap_cap() if sys.platform == "linux" else None)


if __name__ == "__main__":
    main()
