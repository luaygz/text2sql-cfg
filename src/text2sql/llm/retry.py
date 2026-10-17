"""Retry policy for transient API failures.

Retried: 429 (rate limits, flex "resource unavailable"), 408, 409, 5xx, timeouts and
connection errors. Not retried: quota and billing 429s (retrying cannot restore access) and
every other 4xx. A server hint (`retry-after-ms`, `Retry-After`, or on a 429 the reset time of
an exhausted `x-ratelimit-*` bucket) is a minimum wait, with a little jitter on top; without one
the wait is exponential with jitter. The SDK's own retries are disabled so the two loops do not
multiply.
"""

from __future__ import annotations

import asyncio
import email.utils
import random
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import openai
import structlog

log = structlog.get_logger(__name__)

_RETRYABLE_4XX = frozenset({408, 409, 429})
# Error codes the API documents for 429s that need a human (credits, spend or usage limits).
_BILLING_CODES = frozenset(
    {
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }
)
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


def parse_duration(text: str) -> float | None:
    """Seconds in a rate-limit reset value such as `1s`, `6m0s` or `250ms`."""
    parts = _DURATION_PART.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text.strip():
        return None
    return sum(float(n) * _UNIT_SECONDS[u] for n, u in parts)


def server_delay(headers: Mapping[str, str], status: int) -> float | None:
    """The minimum wait the server asked for, if it said. `headers` is the SDK's response
    headers, whose lookups are case-insensitive."""
    if (ms := headers.get("retry-after-ms")) is not None:
        try:
            return float(ms) / 1000
        except ValueError:
            pass
    if (after := headers.get("retry-after")) is not None:
        try:
            return float(after)
        except ValueError:
            parsed = email.utils.parsedate_tz(after)
            if parsed is not None:
                return max(0.0, email.utils.mktime_tz(parsed) - time.time())
    if status != 429:
        return None
    resets = [
        parse_duration(headers.get(f"x-ratelimit-reset-{bucket}", ""))
        for bucket in ("requests", "tokens")
        if headers.get(f"x-ratelimit-remaining-{bucket}") == "0"
    ]
    known = [r for r in resets if r is not None]
    return max(known) if known else None


def _is_billing_error(exc: openai.APIStatusError) -> bool:
    return exc.code in _BILLING_CODES or getattr(exc, "type", None) == "insufficient_quota"


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, openai.APIConnectionError):  # includes APITimeoutError
        return True
    if not isinstance(exc, openai.APIStatusError):
        return False
    if exc.status_code == 429:
        return not _is_billing_error(exc)
    return exc.status_code >= 500 or exc.status_code in _RETRYABLE_4XX


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 6
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    max_server_delay_s: float = 600.0
    """A server hint longer than this means give up now rather than retry early."""

    def delay_for(self, exc: BaseException, attempt: int) -> float | None:
        """Seconds to wait before retry number `attempt + 1`, or None if `exc` is final."""
        if attempt >= self.max_retries or not is_transient(exc):
            return None
        hint = (
            server_delay(exc.response.headers, exc.status_code)
            if isinstance(exc, openai.APIStatusError)
            else None
        )
        if hint is None:
            return self._backoff(attempt)
        if hint > self.max_server_delay_s:
            return None
        return hint + random.uniform(0, self.base_delay_s)

    def _backoff(self, attempt: int) -> float:
        ceiling = min(self.max_delay_s, self.base_delay_s * 2**attempt)
        return random.uniform(ceiling / 2, ceiling)

    async def run[T](self, call: Callable[[], Awaitable[T]], *, purpose: str) -> T:
        attempt = 0
        while True:
            try:
                return await call()
            except Exception as exc:
                delay = self.delay_for(exc, attempt)
                if delay is None:
                    raise
                log.warning(
                    "llm.retry",
                    purpose=purpose,
                    attempt=attempt + 1,
                    delay_s=round(delay, 3),
                    error=type(exc).__name__,
                    status=getattr(exc, "status_code", None),
                )
                await asyncio.sleep(delay)
                attempt += 1
