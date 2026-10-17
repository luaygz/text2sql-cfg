"""Catalog files: `data/catalog/<db_id>.json`, rebuilt by `python -m text2sql.catalog build`."""

from __future__ import annotations

from pathlib import Path

from text2sql.catalog.model import Catalog
from text2sql.config import get_settings


def default_catalog_dir() -> Path:
    return get_settings().data_dir / "catalog"


def catalog_path(db_id: str, catalog_dir: Path | None = None) -> Path:
    return (catalog_dir or default_catalog_dir()) / f"{db_id}.json"


def save_catalog(catalog: Catalog, catalog_dir: Path | None = None) -> Path:
    path = catalog_path(catalog.db_id, catalog_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return path


def load_catalog(db_id: str, catalog_dir: Path | None = None) -> Catalog:
    """Load a built catalog; raises FileNotFoundError naming the build command if it is missing."""
    path = catalog_path(db_id, catalog_dir)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found; build it with `uv run --frozen python -m text2sql.catalog build`"
        )
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))
