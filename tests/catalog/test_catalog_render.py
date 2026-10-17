from __future__ import annotations

from pathlib import Path

import pytest

from text2sql.catalog import (
    Catalog,
    CatalogColumn,
    CatalogTable,
    build_catalog,
    render_matched_values,
    render_schema,
)
from text2sql.catalog.descriptions import ColumnNotes, Descriptions
from text2sql.catalog.schema import Column, DatabaseSchema, Table


@pytest.fixture
def catalog(shop_db: Path) -> Catalog:
    notes = Descriptions(
        columns={("customers", "city"): ColumnNotes("Home city", "Capitalised\nEnglish name")},
        tables={"customers": "People who buy things"},
    )
    return build_catalog(shop_db, "shop", descriptions=notes)


def test_render_is_deterministic_across_json_round_trip(catalog: Catalog) -> None:
    reloaded = Catalog.model_validate_json(catalog.model_dump_json())
    assert render_schema(reloaded) == render_schema(catalog)


def test_identifiers_are_quoted_like_the_grammar_and_fks_are_listed(catalog: Catalog) -> None:
    lines = render_schema(catalog).splitlines()
    assert lines[:3] == [
        "【DB_ID】 shop",
        "【Schema】",
        "# Table: customers, People who buy things",
    ]
    assert "# Table: `order`" in lines  # ORDER is an SQLite keyword
    assert any(line.startswith("(`Full Name`:TEXT,") for line in lines)
    assert "(customer_id:INTEGER, Foreign Key, Examples: [1, 3, 2])," in lines
    fks = lines[lines.index("【Foreign keys】") + 1 :]
    assert fks == ["`order`.customer_id=customers.id", "accounts.owner_customer_id=customers.id"]


def test_column_line_has_type_markers_description_notes_and_literal_examples(
    catalog: Catalog,
) -> None:
    lines = render_schema(catalog).splitlines()
    assert (
        "(city:TEXT, Home city, Notes: Capitalised English name, "
        "Examples: ['Paris', 'Berlin', 'Oslo'])," in lines
    )
    assert "(id:INTEGER, Primary Key, Examples: [1, 2, 3])," in lines
    # Typeless column: no type after the name; text '1' and integer 1 stay distinguishable.
    assert "(code, Examples: [1, '1'])" in lines
    assert "(status:TEXT, Examples: ['O''Brien', 'a', 'b'])," in lines


@pytest.mark.parametrize(
    ("type_", "samples", "shown"),
    [
        ("TEXT", ("a" * 20, "b", "c", "d"), "['aaaaaaaaaaaaaaaaaaaa', 'b', 'c']"),
        ("TEXT", ("a" * 21, "b", "c"), f"['{'a' * 21}']"),
        ("TEXT", ("a" * 51, "b"), None),
        ("DATE", ("2020-01-01", "2020-01-02"), "['2020-01-01']"),
    ],
)
def test_examples_follow_m_schema_length_rules(
    type_: str, samples: tuple[str, ...], shown: str | None
) -> None:
    column = CatalogColumn(name="v", type=type_, samples=samples)
    catalog = Catalog(
        db_id="x",
        tables=(CatalogTable(name="t", row_count=3, profiled_rows=3, columns=(column,)),),
    )
    line = render_schema(catalog).splitlines()[4]
    assert line == (f"(v:{type_})" if shown is None else f"(v:{type_}, Examples: {shown})")


def test_samples_and_descriptions_can_be_switched_off(catalog: Catalog) -> None:
    bare = render_schema(catalog, samples=False, descriptions=False)
    assert "Examples:" not in bare
    assert "Home city" not in bare
    assert "Notes:" not in bare
    assert "People who buy" not in bare
    assert "(city:TEXT)," in bare.splitlines()


def test_subset_keeps_join_columns_and_only_their_foreign_keys(catalog: Catalog) -> None:
    subset = catalog.schema().subset({"order": ["amount"], "customers": ["city"]})
    text = render_schema(catalog, subset=subset)
    assert "accounts" not in text
    assert "status" not in text
    assert "notes" not in text
    assert "(customer_id:INTEGER, Foreign Key" in text  # FK column kept although not asked for
    assert "(id:INTEGER, Primary Key" in text
    assert text.endswith("【Foreign keys】\n`order`.customer_id=customers.id")


def test_subset_naming_columns_outside_the_catalog_is_rejected(catalog: Catalog) -> None:
    bogus = DatabaseSchema(
        db_id="shop", tables=(Table(name="customers", columns=(Column(name="password"),)),)
    )
    with pytest.raises(ValueError, match="password"):
        render_schema(catalog, subset=bogus)
    with pytest.raises(ValueError, match="ghost"):
        render_schema(catalog, subset=DatabaseSchema(db_id="shop", tables=(Table("ghost", ()),)))


def test_matched_values_come_last_in_catalog_order(catalog: Catalog) -> None:
    plain = render_schema(catalog)
    text = render_schema(
        catalog,
        matched_values={
            ("order", "status"): ["O'Brien"],
            ("CUSTOMERS", "City"): ["Paris", "Paris", "Oslo"],
            ("ghost", "col"): ["z"],
        },
    )
    # The cacheable prefix is unchanged; the question-specific part is appended.
    assert text.startswith(plain + "\n")
    assert text[len(plain) + 1 :].splitlines() == [
        "【Matched values】",
        "customers.city: 'Paris', 'Oslo'",
        "`order`.status: 'O''Brien'",
    ]


def test_matched_values_outside_the_subset_are_dropped(catalog: Catalog) -> None:
    subset = catalog.schema().subset({"customers": ["city"]})
    text = render_schema(catalog, subset=subset, matched_values={("order", "status"): ["a"]})
    assert "Matched values" not in text


def test_matched_values_block_alone_for_the_user_message(catalog: Catalog) -> None:
    matched = {("customers", "city"): ["Oslo"]}
    block = render_matched_values(catalog, matched)
    assert block == "【Matched values】\ncustomers.city: 'Oslo'"
    assert render_schema(catalog, matched_values=matched).endswith("\n" + block)
    subset = catalog.schema().subset({"order": None})
    assert render_matched_values(catalog, matched, subset=subset) == ""
