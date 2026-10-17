"""Typed rejections raised by the safety layers.

Every rejection carries a stable `rule` id (aggregated in safety reports) and a human-readable
`detail`. A rejection is never repaired by the layer that raised it; the caller logs it as a
`SafetyEvent` and decides whether to retry generation.
"""

from __future__ import annotations

from typing import ClassVar, Literal

Layer = Literal["grammar", "validator", "scoping", "executor"]


class SafetyError(Exception):
    layer: ClassVar[Layer]

    def __init__(self, rule: str, detail: str) -> None:
        super().__init__(f"[{rule}] {detail}")
        self.rule = rule
        self.detail = detail


class ValidationError(SafetyError):
    """Layer 2: the SQL is not a single read-only SELECT over the visible schema."""

    layer = "validator"


class ScopeViolation(SafetyError):  # noqa: N818 - name fixed by the shared interface contract
    """Layer 4: a scoped table could not be guarded, or a guard could not be proven."""

    layer = "scoping"
