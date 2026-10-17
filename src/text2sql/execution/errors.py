"""Why a query produced no result.

`str(exc)` is written for the repair loop: it can be shown to the model as-is, so it carries
SQLite's own wording ("no such column: x") and never a Python traceback.
"""

from __future__ import annotations

from typing import Final

OUT_OF_MEMORY: Final = "query ran out of memory"
"""`ResultTooLarge` message when the worker hit `ExecutionLimits.max_memory_bytes`."""


class ExecutionError(Exception):
    """Base class. Raised directly only when the sandbox worker itself fails."""


# These names are part of the cross-module interface, hence the N818 waivers.
class QueryTimeout(ExecutionError):  # noqa: N818
    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"query exceeded the {timeout_s:g} s time limit")
        self.timeout_s = timeout_s


class AccessDenied(ExecutionError):  # noqa: N818
    """The authorizer, or the read-only connection under it, refused the statement.

    `action` is the SQLite authorizer action ("READ", "PRAGMA", "FUNCTION", "INSERT", ...) or
    "WRITE" when the read-only connection blocked a write the authorizer never saw.
    """

    def __init__(self, action: str, target: str) -> None:
        super().__init__(f"not authorized: {action} {target}".rstrip())
        self.action = action
        self.target = target


class QueryFailed(ExecutionError):  # noqa: N818
    """SQLite rejected or aborted the statement; the message is SQLite's error text."""


class ResultTooLarge(QueryFailed):
    """The query read, built or returned more data than `ExecutionLimits` allows.

    Raised for a result over `max_result_bytes`, a value over `max_value_bytes` (SQLite's
    "string or blob too big") and a worker that hit `max_memory_bytes`. A `QueryFailed` subclass,
    so the repair loop can show the message to the model like any other failure.
    """
