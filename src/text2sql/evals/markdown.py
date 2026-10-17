"""Markdown formatting shared by per-run reports and RESULTS.md.

Cell text comes from benchmark questions, database values and model output, so everything that
lands in a table cell is escaped and everything multi-line goes into a fence that its content
cannot close.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from text2sql.evals.metrics import PairedComparison, Rate

_BACKTICK_RUN = re.compile(r"`+")


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def rate_ci(rate: Rate) -> str:
    """`61.2% (57.0-65.4)`: estimate and 95% bootstrap interval."""
    return f"{pct(rate.value)} ({100 * rate.ci_low:.1f}-{100 * rate.ci_high:.1f})"


def delta_ci(comparison: PairedComparison) -> str:
    """`+2.4 pts (-0.8, +5.6)`: paired EX difference and its 95% bootstrap interval."""
    c = comparison
    return f"{100 * c.delta:+.1f} pts ({100 * c.delta_ci_low:+.1f}, {100 * c.delta_ci_high:+.1f})"


def p_value(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def usd(amount: float) -> str:
    return f"${amount:.4f}" if amount < 1 else f"${amount:,.2f}"


def seconds(value: float) -> str:
    return f"{value:.1f} s"


def cell(text: object, *, max_chars: int = 80) -> str:
    """One table cell: single line, pipes escaped, long values cut with an ellipsis."""
    flat = " ".join(str(text).split())
    if len(flat) > max_chars:
        flat = flat[: max_chars - 1] + "…"
    return flat.replace("\\", "\\\\").replace("|", "\\|")


def table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """A GitHub table; callers escape free text with `cell` before passing it in."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def fence(text: str, lang: str = "") -> list[str]:
    """A fenced block longer than any backtick run inside `text`."""
    longest = max((len(m.group()) for m in _BACKTICK_RUN.finditer(text)), default=0)
    marker = "`" * max(3, longest + 1)
    return [marker + lang, text.rstrip("\n"), marker]
