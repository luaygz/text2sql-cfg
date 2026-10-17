"""Catalogs built from the real BIRD Mini-Dev databases (skipped when data/bird is absent)."""

from __future__ import annotations

import pytest

from text2sql.catalog import build_catalog, estimate_tokens, render_schema
from text2sql.catalog.schema import quote_identifier
from text2sql.data import bird


def _minidev_ids() -> tuple[str, ...]:
    try:
        ids = bird.minidev_db_ids()
        for db_id in ids:
            bird.bird_db_path(db_id)
    except FileNotFoundError:
        return ()
    return ids


DB_IDS = _minidev_ids()

# Description rows in BIRD's CSVs that name a column the database does not have.
KNOWN_UNMATCHED = {"constructors.csv: column 'wins' not in table 'constructors'"}

pytestmark = [
    pytest.mark.bird,
    pytest.mark.skipif(not DB_IDS, reason="BIRD data absent; run the bird download"),
]


def test_all_eleven_minidev_databases_are_covered() -> None:
    assert len(DB_IDS) == 11


@pytest.mark.parametrize("db_id", DB_IDS)
def test_every_table_gets_its_description_file_and_renders(db_id: str) -> None:
    catalog = build_catalog(
        bird.bird_db_path(db_id), db_id, description_dir=bird.bird_description_dir(db_id)
    )
    problems = [
        w
        for w in catalog.warnings
        if "stray bytes read as cp1252" not in w and w not in KNOWN_UNMATCHED
    ]
    assert problems == []
    assert sum(1 for t in catalog.tables for c in t.columns if c.description) > 0
    text = render_schema(catalog)
    for table in catalog.tables:
        assert f"# Table: {quote_identifier(table.name)}" in text
        for column in table.columns:
            assert f"({quote_identifier(column.name)}" in text
    # The full-schema strategy sends this whole block; keep it far below context limits.
    assert estimate_tokens(text) < 8000
