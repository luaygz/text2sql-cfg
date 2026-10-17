"""Execute every Mini-Dev gold query (original and Arcwise-Plat-SQL) on both database releases.

    uv run --frozen python -m text2sql.data.bird_gold_check [--timeout 30]

Prints a JSON summary: how many gold queries error or time out under BIRD's 30 s limit, how many
Arcwise gold queries return a different result set from the original gold (BIRD set semantics),
and how many original gold results change between the Mini-Dev and Dev database releases. The
numbers back docs/adr/003-bird-data.md. Local only; no API calls.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Literal

import typer
from pydantic import BaseModel

from text2sql.data.bird import BirdExample, DbRelease, bird_db_path, load_minidev
from text2sql.evals.bird_metric import (
    OFFICIAL_TIMEOUT_S,
    Row,
    SqlRunError,
    SqlTimeoutError,
    execute_readonly,
    results_match,
)

type Outcome = list[Row] | Literal["error", "timeout"]


class FailureCounts(BaseModel):
    errors: list[int]
    timeouts: list[int]


class GoldCheckReport(BaseModel):
    timeout_s: float
    questions: int
    arcwise_questions: int
    original_on_minidev: FailureCounts
    original_on_dev: FailureCounts
    arcwise_on_dev: FailureCounts
    arcwise_on_minidev: FailureCounts
    arcwise_differs_on_dev: list[int]
    """Both golds ran on the dev release and their result sets are not equal (as BIRD compares)."""
    arcwise_differs_on_minidev: list[int]
    original_differs_across_releases: list[int]
    arcwise_differs_across_releases: list[int]
    arcwise_changed_by_db: dict[str, int]


def _run(sql: str, example: BirdExample, release: DbRelease, timeout_s: float) -> Outcome:
    try:
        return execute_readonly(sql, bird_db_path(example.db_id, release), timeout_s=timeout_s)
    except SqlTimeoutError:
        return "timeout"
    except SqlRunError:
        return "error"


def _failures(outcomes: dict[int, Outcome]) -> FailureCounts:
    return FailureCounts(
        errors=sorted(q for q, o in outcomes.items() if o == "error"),
        timeouts=sorted(q for q, o in outcomes.items() if o == "timeout"),
    )


def _differs(left: dict[int, Outcome], right: dict[int, Outcome]) -> list[int]:
    """Question ids where both ran and the result sets differ."""
    return sorted(
        q
        for q in left.keys() & right.keys()
        if isinstance(a := left[q], list)
        and isinstance(b := right[q], list)
        and not results_match(a, b)
    )


def check_gold(timeout_s: float = OFFICIAL_TIMEOUT_S) -> GoldCheckReport:
    examples = load_minidev()
    arcwise = [e for e in examples if e.gold_sql_arcwise is not None]
    orig_mini = {e.question_id: _run(e.gold_sql, e, "minidev", timeout_s) for e in examples}
    orig_dev = {e.question_id: _run(e.gold_sql, e, "dev", timeout_s) for e in examples}
    arc_dev = {e.question_id: _run(e.gold_sql_arcwise or "", e, "dev", timeout_s) for e in arcwise}
    arc_mini = {
        e.question_id: _run(e.gold_sql_arcwise or "", e, "minidev", timeout_s) for e in arcwise
    }
    differs_dev = _differs(arc_dev, orig_dev)
    db_of = {e.question_id: e.db_id for e in examples}
    return GoldCheckReport(
        timeout_s=timeout_s,
        questions=len(examples),
        arcwise_questions=len(arcwise),
        original_on_minidev=_failures(orig_mini),
        original_on_dev=_failures(orig_dev),
        arcwise_on_dev=_failures(arc_dev),
        arcwise_on_minidev=_failures(arc_mini),
        arcwise_differs_on_dev=differs_dev,
        arcwise_differs_on_minidev=_differs(arc_mini, orig_mini),
        original_differs_across_releases=_differs(orig_mini, orig_dev),
        arcwise_differs_across_releases=_differs(arc_mini, arc_dev),
        arcwise_changed_by_db=dict(sorted(Counter(db_of[q] for q in differs_dev).items())),
    )


def main(timeout: float = OFFICIAL_TIMEOUT_S) -> None:
    report = check_gold(timeout)
    typer.echo(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    typer.run(main)
