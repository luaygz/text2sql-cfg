"""`python -m text2sql.catalog build --dataset bird|saas [--no-llm]`."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table as RichTable

from text2sql.catalog.builder import build_catalog
from text2sql.catalog.describe import DescribeReport, StructuredLLM, describe_columns
from text2sql.catalog.descriptions import descriptions_from_schema
from text2sql.catalog.model import Catalog
from text2sql.catalog.render import estimate_tokens, render_schema
from text2sql.catalog.store import catalog_path, save_catalog
from text2sql.config import get_settings
from text2sql.data import bird, saas

app = typer.Typer(help="Build schema catalogs (data/catalog/<db_id>.json).", no_args_is_help=True)
console = Console(width=None if sys.stdout.isatty() else 120)


class Dataset(StrEnum):
    BIRD = "bird"
    SAAS = "saas"


@dataclass(frozen=True, slots=True)
class _Built:
    catalog: Catalog
    profile_s: float
    llm: DescribeReport | None


@app.callback()
def main() -> None:
    """Schema catalog commands."""


@app.command()
def build(
    dataset: Annotated[Dataset, typer.Option(help="Which databases to catalog.")],
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM column descriptions.")] = False,
    db: Annotated[list[str] | None, typer.Option(help="Only these BIRD db_ids.")] = None,
) -> None:
    """Profile each database, attach descriptions, add LLM descriptions, save JSON."""
    jobs = _bird_jobs(db) if dataset is Dataset.BIRD else _saas_jobs()
    built, spend = asyncio.run(_build_all(jobs, describe=not no_llm))
    report = RichTable(
        "db_id", "tables", "columns", "profile s", "chars", "~tokens", "warnings", "llm calls",
        "cache hits", "llm $",
    )  # fmt: skip
    for b in built:
        text = render_schema(b.catalog)
        report.add_row(
            b.catalog.db_id,
            str(len(b.catalog.tables)),
            str(sum(len(t.columns) for t in b.catalog.tables)),
            f"{b.profile_s:.2f}",
            str(len(text)),
            str(estimate_tokens(text)),
            str(len(b.catalog.warnings)),
            "-" if b.llm is None else str(b.llm.calls),
            "-" if b.llm is None else str(b.llm.cache_hits),
            "-" if b.llm is None else f"{b.llm.cost_usd:.4f}",
        )
    console.print(report)
    if built:
        console.print(f"catalogs written to {catalog_path(built[0].catalog.db_id).parent}")
    if spend:
        console.print(spend)


def _bird_jobs(only: list[str] | None) -> list[Callable[[], Catalog]]:
    return [
        partial(
            build_catalog,
            bird.bird_db_path(db_id),
            db_id,
            description_dir=bird.bird_description_dir(db_id),
        )
        for db_id in (only or bird.minidev_db_ids())
    ]


def _saas_jobs() -> list[Callable[[], Catalog]]:
    def job() -> Catalog:
        documented = saas.load_saas_schema(saas.DEFAULT_DB_PATH)
        return build_catalog(
            saas.DEFAULT_DB_PATH,
            saas.SAAS_DB_ID,
            descriptions=descriptions_from_schema(documented),
            policy=saas.saas_scope_policy(),
        )

    return [job]


async def _build_all(
    jobs: list[Callable[[], Catalog]], *, describe: bool
) -> tuple[list[_Built], str | None]:
    """Built catalogs, plus the LLM spend summary when descriptions were requested."""
    if not describe:
        return [await _build_one(job, None) for job in jobs], None
    from text2sql.llm.client import LLMClient  # imports the OpenAI SDK; only when needed

    async with LLMClient(get_settings()) as llm:
        built = [await _build_one(job, llm) for job in jobs]
        return built, llm.budget.summary().render()


async def _build_one(job: Callable[[], Catalog], llm: StructuredLLM | None) -> _Built:
    started = time.perf_counter()
    catalog = job()
    profile_s = time.perf_counter() - started
    report = None
    if llm is not None:
        report = await describe_columns(catalog, llm, model=get_settings().small_model)
        catalog = report.catalog
    save_catalog(catalog)
    return _Built(catalog=catalog, profile_s=profile_s, llm=report)
