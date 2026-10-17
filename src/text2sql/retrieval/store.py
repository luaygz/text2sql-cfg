"""Where retrieval indexes live (data/indexes/, gitignored) and how to rebuild them."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from text2sql.config import get_settings
from text2sql.data.saas import SAAS_DB_ID

type Dataset = Literal["bird", "saas"]


def index_root() -> Path:
    return get_settings().data_dir / "indexes"


def database_dir(db_id: str) -> Path:
    """Value index and column embeddings of one database."""
    if not db_id or Path(db_id).name != db_id or db_id.startswith("."):
        raise ValueError(f"not a database id: {db_id!r}")
    return index_root() / db_id


def fewshot_dir(pool: Dataset) -> Path:
    return index_root() / "fewshot" / pool


def dataset_of(db_id: str) -> Dataset:
    return "saas" if db_id == SAAS_DB_ID else "bird"


def build_command(dataset: Dataset) -> str:
    return f"uv run --frozen python -m text2sql.retrieval build --dataset {dataset}"


def missing(path: Path, dataset: Dataset) -> FileNotFoundError:
    return FileNotFoundError(f"{path} is missing; build it with `{build_command(dataset)}`")
