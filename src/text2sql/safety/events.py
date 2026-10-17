"""Safety events: one JSONL record per rejection at any of the four layers.

Every rejection is recorded, never silently fixed. The adversarial suite counts events per layer
to show where each attack was stopped.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter

from text2sql.config import get_settings
from text2sql.safety.errors import Layer, SafetyError


@dataclass(frozen=True, slots=True)
class SafetyEvent:
    layer: Layer
    rule: str
    detail: str
    sql: str | None = None
    context: dict[str, str] = field(default_factory=dict)
    """Request metadata such as question id, tenant id, candidate strategy."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_error(
        cls, error: SafetyError, *, sql: str | None, context: dict[str, str] | None = None
    ) -> SafetyEvent:
        return cls(error.layer, error.rule, error.detail, sql, dict(context or {}))


_EVENT = TypeAdapter(SafetyEvent)


class SafetyEventLog:
    """Append-only JSONL log, safe to share between threads."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else get_settings().runs_dir / "safety_events.jsonl"
        self._lock = threading.Lock()

    def record(self, event: SafetyEvent) -> None:
        line = _EVENT.dump_json(event).decode() + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def read(self) -> list[SafetyEvent]:
        """Every recorded event, validated; an absent log is empty."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [_EVENT.validate_json(line) for line in handle if line.strip()]
