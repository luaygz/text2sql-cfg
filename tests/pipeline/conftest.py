"""Fixtures for the pipeline tests: isolated settings, traces and safety log, and a tiny
database to build `DatabaseResources` on. No network."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pipeline_fakes import REPO_ROOT, make_database, make_resources

from text2sql.config import Settings
from text2sql.observability import start_run
from text2sql.pipeline import DatabaseResources


@pytest.fixture(autouse=True)
def trace_run(tmp_path: Path) -> None:
    start_run("pipeline-test", traces_dir=tmp_path / "traces")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        openai_api_key=None,
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "spend_ledger.jsonl",
        runs_dir=tmp_path / "runs",
        pricing_path=REPO_ROOT / "config" / "pricing.yaml",
        phase="test",
    )


@pytest.fixture
def events_path(tmp_path: Path) -> Path:
    return tmp_path / "safety_events.jsonl"


@pytest.fixture
def resources_factory(
    tmp_path: Path, events_path: Path
) -> Iterator[Callable[..., DatabaseResources]]:
    """Build resources on the tiny database; keyword arguments go to `make_resources`."""
    db_path = make_database(tmp_path / "concerts.sqlite")
    made: list[DatabaseResources] = []

    def factory(**kwargs: Any) -> DatabaseResources:
        res = make_resources(db_path, events_path, **kwargs)
        made.append(res)
        return res

    yield factory
    for res in made:
        res.close()
