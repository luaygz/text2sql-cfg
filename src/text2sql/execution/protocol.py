"""The JSON messages exchanged between `SandboxedExecutor` and its worker process.

JSON rather than pickle: the worker runs attacker-influenced SQL, so the parent treats every reply
as untrusted bytes. Unpickling them would give a compromised worker code execution in the parent
process, which holds the API key. Blobs travel as `{"b": "<base64>"}`; no other value in a reply is
a JSON object.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final

from text2sql.execution.errors import (
    AccessDenied,
    ExecutionError,
    QueryFailed,
    QueryTimeout,
    ResultTooLarge,
)
from text2sql.execution.models import AccessPolicy, ExecutionLimits, Params, QueryResult, Row

READY: Final = b'{"ready":true}'

_CELL_TYPES: Final = frozenset({int, float, str, bytes, type(None)})
_JSON_EXPANSION: Final = 12
"""Most JSON bytes one counted byte can become: a character outside the BMP is one `len()` unit
and two `\\uXXXX` escapes. Numbers, NULLs and blobs stay below it thanks to the 8-byte overhead."""
_ENVELOPE_BYTES: Final = 4096


def max_reply_bytes(request_bytes: int, limits: ExecutionLimits) -> int:
    """Longest reply an honest worker can send for a request; anything longer is refused unread.

    Results are bounded by `max_result_bytes`, error messages by the SQL they quote.
    """
    return _JSON_EXPANSION * (limits.max_result_bytes + request_bytes) + _ENVELOPE_BYTES


def encode_setup(db_path: Path, access: AccessPolicy, clock: str | None) -> bytes:
    readable = (
        None
        if access.readable is None
        else {table: sorted(columns) for table, columns in access.readable.items()}
    )
    return _dumps(
        {
            "db_path": str(db_path),
            "readable": readable,
            "functions": sorted(access.functions),
            "allow_recursive": access.allow_recursive,
            "clock": clock,
        }
    )


def decode_setup(data: bytes) -> tuple[Path, AccessPolicy, str | None]:
    message = json.loads(data)
    readable = message["readable"]
    access = AccessPolicy(
        readable=None
        if readable is None
        else {table: frozenset(columns) for table, columns in readable.items()},
        functions=frozenset(message["functions"]),
        allow_recursive=bool(message["allow_recursive"]),
    )
    return Path(message["db_path"]), access, message["clock"]


def encode_request(sql: str, params: Params | None, limits: ExecutionLimits) -> bytes:
    return _dumps({"sql": sql, "params": dict(params or {}), "limits": asdict(limits)})


def decode_request(data: bytes) -> tuple[str, dict[str, int | float | str], ExecutionLimits]:
    message = json.loads(data)
    return message["sql"], message["params"], ExecutionLimits(**message["limits"])


def encode_result(result: QueryResult) -> bytes:
    return _dumps(
        {
            "columns": result.columns,
            "rows": result.rows,
            "truncated": result.truncated,
            "elapsed_s": result.elapsed_s,
        }
    )


def encode_error(exc: ExecutionError) -> bytes:
    if isinstance(exc, QueryTimeout):
        return _dumps({"error": "timeout", "timeout_s": exc.timeout_s})
    if isinstance(exc, AccessDenied):
        return _dumps({"error": "denied", "action": exc.action, "target": exc.target})
    if isinstance(exc, ResultTooLarge):
        return _dumps({"error": "too_large", "message": str(exc)})
    return _dumps({"error": "failed", "message": str(exc)})


def decode_reply(data: bytes) -> QueryResult | ExecutionError:
    """Parse and validate a worker reply. Raises ExecutionError if it is malformed."""
    try:
        message = json.loads(data, object_hook=_decode_blob)
    except (ValueError, RecursionError) as exc:
        raise _malformed() from exc
    match message:
        case {"error": "timeout", "timeout_s": float() | int() as timeout_s}:
            return QueryTimeout(float(timeout_s))
        case {"error": "denied", "action": str(action), "target": str(target)}:
            return AccessDenied(action, target)
        case {"error": "too_large", "message": str(text)}:
            return ResultTooLarge(text)
        case {"error": "failed", "message": str(text)}:
            return QueryFailed(text)
        case {
            "columns": list(columns),
            "rows": list(rows),
            "truncated": bool(truncated),
            "elapsed_s": float() | int() as elapsed_s,
        } if all(isinstance(name, str) for name in columns):
            return QueryResult(
                columns=tuple(columns),
                rows=_rows(rows, width=len(columns)),
                truncated=truncated,
                elapsed_s=float(elapsed_s),
            )
    raise _malformed()


def check_ready(data: bytes) -> None:
    """Accept the worker's start-up reply; raise the error it reported, if any."""
    if data == READY:
        return
    outcome = decode_reply(data)
    raise outcome if isinstance(outcome, ExecutionError) else _malformed()


def _rows(rows: list[Any], *, width: int) -> tuple[Row, ...]:
    checked: list[Row] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise _malformed()
        if not all(type(cell) in _CELL_TYPES for cell in row):
            raise _malformed()
        checked.append(tuple(row))
    return tuple(checked)


def _dumps(message: dict[str, Any]) -> bytes:
    return json.dumps(message, default=_encode_blob, separators=(",", ":")).encode()


def _encode_blob(value: object) -> dict[str, str]:
    if isinstance(value, bytes):
        return {"b": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"cannot encode {type(value).__name__}")


def _decode_blob(obj: dict[str, Any]) -> object:
    if obj.keys() == {"b"} and isinstance(obj["b"], str):
        try:
            return base64.b64decode(obj["b"], validate=True)
        except binascii.Error as exc:
            raise ValueError("invalid blob encoding") from exc
    return obj


def _malformed() -> ExecutionError:
    return ExecutionError("sandbox worker sent a malformed reply")
