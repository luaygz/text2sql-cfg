"""`python -m text2sql.retrieval build --dataset bird|saas` and `... measure`.

`app` is also mounted by the project CLI as `text2sql index`.
"""

from __future__ import annotations

import asyncio
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from text2sql.catalog import load_catalog
from text2sql.config import get_settings
from text2sql.llm import LLMClient
from text2sql.retrieval.build import BuiltIndex, build_indexes
from text2sql.retrieval.measure import measure_split, summarize, write_results

app = typer.Typer(help="Retrieval indexes under data/indexes/.", no_args_is_help=True)
console = Console(width=None if sys.stdout.isatty() else 120)


class DatasetOption(StrEnum):
    BIRD = "bird"
    SAAS = "saas"


@app.callback()
def main() -> None:
    """Retrieval index commands."""


@app.command()
def build(
    dataset: Annotated[DatasetOption, typer.Option(help="Which databases and few-shot pool.")],
    db: Annotated[list[str] | None, typer.Option(help="Only these BIRD db_ids.")] = None,
    skip_fewshot: Annotated[
        bool, typer.Option("--skip-fewshot", help="Do not (re)build the few-shot pool.")
    ] = False,
) -> None:
    """Value indexes and column embeddings per database, then the few-shot pool."""
    built, spend = asyncio.run(_build(dataset, db, fewshot=not skip_fewshot))
    report = Table("index", "name", "entries", "seconds", "path")
    for b in built:
        report.add_row(b.kind, b.name, str(b.entries), f"{b.seconds:.1f}", str(b.path))
    console.print(report)
    console.print(spend)


async def _build(
    dataset: DatasetOption, db_ids: list[str] | None, *, fewshot: bool
) -> tuple[list[BuiltIndex], str]:
    async with LLMClient(get_settings()) as llm:
        built = await build_indexes(dataset.value, llm=llm, db_ids=db_ids, fewshot=fewshot)
        return built, llm.budget.summary().render()


@app.command()
def measure(
    limit: Annotated[int | None, typer.Option(help="Only the first N dev questions.")] = None,
) -> None:
    """Linking recall, linked-schema size and value hit rate on the BIRD dev split."""
    summary, path, spend = asyncio.run(_measure(limit))
    console.print_json(summary)
    console.print(f"per-question results and summary in {path.parent}")
    console.print(spend)


async def _measure(limit: int | None) -> tuple[str, Path, str]:
    async with LLMClient(get_settings()) as llm:
        results = await measure_split(llm, limit=limit)
        schemas = {db: load_catalog(db).schema() for db in {r.db_id for r in results}}
        summary = summarize(results, schemas)
        path = write_results(results, summary)
        return summary.model_dump_json(), path, llm.budget.summary().render()
