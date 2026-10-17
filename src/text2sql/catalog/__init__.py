"""Schema catalog: per-database metadata, statistics and descriptions feeding every stage.

`text2sql.catalog.describe` (LLM descriptions) is not re-exported here because it imports the
LLM client, which itself depends on `text2sql.catalog.schema`.
"""

from text2sql.catalog.builder import build_catalog
from text2sql.catalog.model import Catalog, CatalogColumn, CatalogTable, SampleValue
from text2sql.catalog.render import estimate_tokens, render_matched_values, render_schema
from text2sql.catalog.store import catalog_path, load_catalog, save_catalog

__all__ = [
    "Catalog",
    "CatalogColumn",
    "CatalogTable",
    "SampleValue",
    "build_catalog",
    "catalog_path",
    "estimate_tokens",
    "load_catalog",
    "render_matched_values",
    "render_schema",
    "save_catalog",
]
