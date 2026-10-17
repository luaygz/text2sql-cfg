"""`python -m text2sql.data.saas.evalset build|spotcheck` (see data/saas/README.md)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from text2sql.data.saas.evalset.build import (
    PHASE,
    PHASE_CAP_USD,
    REPORT_PATH,
    SCHEMA_SNAPSHOT_PATH,
    build_evalset,
    phase_spend_usd,
    write_outputs,
    write_schema_snapshot,
)
from text2sql.data.saas.evalset.models import EVAL_PATH, FEWSHOT_PATH, load_saas_eval
from text2sql.data.saas.evalset.spotcheck import WORKSHEET_PATH, sample_items, write_worksheet

app = typer.Typer(help="Build the SaaS evaluation set and few-shot pool.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """SaaS evaluation set commands."""


@app.command("snapshot-schema")
def snapshot_schema() -> None:
    """Freeze the current catalog rendering as the build's schema text (the next build re-drafts
    everything through the API)."""
    write_schema_snapshot()
    typer.echo(f"wrote {SCHEMA_SNAPSHOT_PATH}")


@app.command()
def build(
    offline: Annotated[
        bool, typer.Option(help="Replay from the response cache only; never call the API.")
    ] = False,
    batch: Annotated[
        list[str] | None,
        typer.Option(help="Pilot: draft only these plan batches and write nothing."),
    ] = None,
) -> None:
    """Draft, verify, review and select; write eval.jsonl, fewshot_pool.jsonl and the report."""
    report, items, pool, spend = asyncio.run(build_evalset(offline=offline, only_batches=batch))
    summary = report.model_dump(exclude={"rejections"})
    typer.echo(json.dumps(summary, indent=2))
    typer.echo(f"{len(report.rejections)} rejected candidates")
    if batch is None:
        write_outputs(report, items, pool)
        typer.echo(f"wrote {len(items)} items to {EVAL_PATH}, {len(pool)} to {FEWSHOT_PATH}")
        typer.echo(f"build report: {REPORT_PATH}")
    typer.echo(spend)
    typer.echo(f"phase {PHASE}: ${phase_spend_usd():.4f} of ${PHASE_CAP_USD:.2f} spent so far")


@app.command()
def spotcheck(
    n: Annotated[int, typer.Option(help="Approximate sample size.")] = 30,
    seed: Annotated[int, typer.Option(help="Sample seed; record it with the results.")] = 1,
    out: Annotated[Path, typer.Option(help="Worksheet path.")] = WORKSHEET_PATH,
) -> None:
    """Write a worksheet of a seeded, bucket-stratified sample for a human spot check."""
    sample = sample_items(load_saas_eval(), n, seed)
    write_worksheet(sample, out)
    typer.echo(f"wrote {len(sample)} items to {out}")


if __name__ == "__main__":
    app()
