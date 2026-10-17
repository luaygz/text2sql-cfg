"""The N-sweep chart: EX and cost per question against the number of candidates, by difficulty.

SVG output is byte-for-byte reproducible for the same inputs and matplotlib version: element ids
come from a fixed hash salt and the date metadata is dropped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from text2sql.evals.metrics import GroupSummary


@dataclass(frozen=True, slots=True)
class SweepPoint:
    n_candidates: int
    overall: GroupSummary
    by_difficulty: Mapping[str, GroupSummary]


def plot_n_sweep(
    points: Sequence[SweepPoint], difficulties: Sequence[str], path: Path, *, title: str
) -> None:
    import matplotlib as mpl
    from matplotlib.figure import Figure

    ns = [p.n_candidates for p in points]
    with mpl.rc_context({"svg.hashsalt": "text2sql-results", "svg.fonttype": "path"}):
        fig = Figure(figsize=(10, 4), layout="constrained")
        accuracy = fig.add_subplot(1, 2, 1)
        cost = fig.add_subplot(1, 2, 2)
        overall_ex = [100 * p.overall.ex.value for p in points]
        accuracy.errorbar(
            ns,
            overall_ex,
            yerr=[
                [ex - 100 * p.overall.ex.ci_low for ex, p in zip(overall_ex, points, strict=True)],
                [100 * p.overall.ex.ci_high - ex for ex, p in zip(overall_ex, points, strict=True)],
            ],
            marker="o",
            color="black",
            capsize=3,
            label="all (95% CI)",
        )
        accuracy.plot(
            ns,
            [100 * p.overall.pass_at_n.value for p in points],
            linestyle="--",
            color="grey",
            label="all, oracle pass@N",
        )
        cost.plot(
            ns,
            [p.overall.cost_per_question_usd for p in points],
            marker="o",
            color="black",
            label="all",
        )
        for difficulty in difficulties:
            xs = [p.n_candidates for p in points if difficulty in p.by_difficulty]
            groups = [p.by_difficulty[difficulty] for p in points if difficulty in p.by_difficulty]
            accuracy.plot(xs, [100 * g.ex.value for g in groups], marker="o", label=difficulty)
            cost.plot(xs, [g.cost_per_question_usd for g in groups], marker="o", label=difficulty)
        for axes, ylabel in ((accuracy, "EX (%)"), (cost, "cost per question (USD)")):
            axes.set_xlabel("candidates (N)")
            axes.set_ylabel(ylabel)
            axes.set_xticks(ns)
            axes.grid(alpha=0.3)
            axes.legend(fontsize="small")
        fig.suptitle(title)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, format="svg", metadata={"Date": None})
