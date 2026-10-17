"""Layer 3: the sandboxed SQLite executor (read-only connection, authorizer, timeouts, worker)."""

from text2sql.execution.errors import (
    AccessDenied,
    ExecutionError,
    QueryFailed,
    QueryTimeout,
    ResultTooLarge,
)
from text2sql.execution.executor import SandboxedExecutor
from text2sql.execution.models import (
    DEFAULT_FUNCTIONS,
    AccessPolicy,
    Cell,
    ExecutionLimits,
    Params,
    QueryResult,
    Row,
)

__all__ = [
    "DEFAULT_FUNCTIONS",
    "AccessDenied",
    "AccessPolicy",
    "Cell",
    "ExecutionError",
    "ExecutionLimits",
    "Params",
    "QueryFailed",
    "QueryResult",
    "QueryTimeout",
    "ResultTooLarge",
    "Row",
    "SandboxedExecutor",
]
