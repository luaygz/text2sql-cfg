"""Build every retrieval index of a dataset: value LSH and column embeddings per database, plus
the few-shot pool. Value indexes need no API; embeddings and pool masking go through LLMClient,
so with `offline=True` settings they replay from the response cache."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from text2sql.catalog import load_catalog
from text2sql.config import get_settings
from text2sql.data import bird, saas
from text2sql.retrieval.analysis import DEFAULT_ANALYSIS_EFFORT
from text2sql.retrieval.calls import RetrievalLLM
from text2sql.retrieval.columns import ColumnIndex
from text2sql.retrieval.fewshot import FewShotIndex, saas_pool_path
from text2sql.retrieval.store import Dataset, database_dir, fewshot_dir
from text2sql.retrieval.values import ValueIndex
from text2sql.safety.policy import ScopePolicy

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BuiltIndex:
    kind: Literal["values", "columns", "fewshot"]
    name: str
    """Database id, or the pool name for few-shot indexes."""
    path: Path
    entries: int
    """Indexed values, column documents or pool questions."""
    seconds: float


@dataclass(frozen=True)
class _Source:
    db_id: str
    db_path: Path
    policy: ScopePolicy | None


def _sources(dataset: Dataset, db_ids: Sequence[str] | None) -> list[_Source]:
    if dataset == "saas":
        return [_Source(saas.SAAS_DB_ID, saas.DEFAULT_DB_PATH, saas.saas_scope_policy())]
    return [_Source(d, bird.bird_db_path(d), None) for d in (db_ids or bird.minidev_db_ids())]


async def build_indexes(
    dataset: Dataset,
    *,
    llm: RetrievalLLM,
    db_ids: Sequence[str] | None = None,
    fewshot: bool = True,
) -> list[BuiltIndex]:
    """Build and save the indexes of `dataset` (BIRD: the Mini-Dev databases unless `db_ids`
    names some). The saas few-shot pool is skipped with a warning while its source file is
    missing."""
    built: list[BuiltIndex] = []
    for source in _sources(dataset, db_ids):
        catalog = load_catalog(source.db_id)
        started = time.perf_counter()
        values = ValueIndex.build(catalog, source.db_path, policy=source.policy)
        values.save()
        directory = database_dir(source.db_id)
        built.append(
            BuiltIndex("values", source.db_id, directory, len(values.values), _since(started))
        )
        started = time.perf_counter()
        columns, _ = await ColumnIndex.build(catalog, llm)
        columns.save()
        built.append(
            BuiltIndex("columns", source.db_id, directory, len(columns.columns), _since(started))
        )
    if fewshot:
        if dataset == "saas" and not saas_pool_path().is_file():
            log.warning("retrieval.fewshot.skipped", reason=f"{saas_pool_path()} is missing")
        else:
            built.append(await _build_pool(dataset, llm))
    return built


async def _build_pool(pool: Dataset, llm: RetrievalLLM) -> BuiltIndex:
    started = time.perf_counter()
    model = get_settings().small_model
    index, skipped = await FewShotIndex.build(
        pool, llm, model=model, effort=DEFAULT_ANALYSIS_EFFORT
    )
    index.save(model=model, effort=DEFAULT_ANALYSIS_EFFORT, skipped=skipped)
    return BuiltIndex("fewshot", pool, fewshot_dir(pool), len(index.items), _since(started))


def _since(started: float) -> float:
    return time.perf_counter() - started
