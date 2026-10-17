from __future__ import annotations

from pathlib import Path

from text2sql.catalog.descriptions import (
    ColumnNotes,
    decode_text,
    descriptions_from_schema,
    load_bird_descriptions,
)
from text2sql.catalog.schema import Column, DatabaseSchema, Table, introspect_sqlite

HEADER = "original_column_name,column_name,column_description,data_format,value_description\n"


def _write(directory: Path, name: str, data: bytes) -> None:
    directory.mkdir(exist_ok=True)
    (directory / name).write_bytes(data)


def test_decode_keeps_utf8_and_reads_stray_bytes_as_cp1252() -> None:
    raw = "café ".encode() + b"\x95 bullet \x96 dash \x81"
    text, fell_back = decode_text(raw)
    assert text == "café \u2022 bullet \u2013 dash \x81"
    assert fell_back
    assert decode_text(b"\xef\xbb\xbfplain") == ("plain", False)


def test_encodings_bom_and_name_mismatches_resolve_to_real_identifiers(
    shop_db: Path, tmp_path: Path
) -> None:
    schema = introspect_sqlite(shop_db)
    d = tmp_path / "database_description"
    # cp1252 file, upper-cased file name, column names with odd spacing/case.
    _write(
        d,
        "CUSTOMERS.csv",
        (
            HEADER
            + " full name ,,Name of the customer,text,\n"
            + "cty,city,City where the customer lives,text,\u201cParis\u201d or \u201cOslo\u201d\n"
            + "zzz,,ghost column,text,\n"
        ).encode("cp1252"),
    )
    # UTF-8 with BOM; header cells padded with spaces.
    _write(
        d,
        "order.csv",
        b"\xef\xbb\xbf original_column_name , column_name,column_description,data_format,"
        b"value_description\n"
        + b"order_id,order id,,integer,\n"
        + b"status,,Order status,text,Order status. 'a' = active; 'b' = billed\n",
    )
    _write(d, "orphans.csv", HEADER.encode())

    result = load_bird_descriptions(d, schema)

    assert result.columns[("customers", "Full Name")] == ColumnNotes("Name of the customer", None)
    assert result.columns[("customers", "city")] == ColumnNotes(
        "City where the customer lives", "\u201cParis\u201d or \u201cOslo\u201d"
    )
    # The expanded name only repeats the identifier, so no description is invented from it.
    assert result.columns[("order", "order_id")] == ColumnNotes(None, None)
    # Value notes that restate the description keep only what they add.
    assert result.columns[("order", "status")].value_description == "'a' = active; 'b' = billed"
    warnings = "\n".join(result.warnings)
    assert "CUSTOMERS.csv: not valid UTF-8" in warnings
    assert "'zzz' not in table 'customers'" in warnings
    assert "orphans.csv: no table" in warnings
    assert "no description file for table 'accounts'" in warnings
    assert "order.csv" not in warnings


def test_expanded_name_is_kept_when_it_adds_meaning(tmp_path: Path) -> None:
    schema = DatabaseSchema(
        db_id="fin", tables=(Table(name="district", columns=(Column(name="A11"),)),)
    )
    d = tmp_path / "desc"
    _write(d, "district.csv", (HEADER + "A11,average salary,,integer,\n").encode())
    assert load_bird_descriptions(d, schema).columns[("district", "A11")].description == (
        "average salary"
    )


def test_first_of_duplicate_rows_wins(tmp_path: Path) -> None:
    schema = DatabaseSchema(db_id="x", tables=(Table(name="t", columns=(Column(name="a"),)),))
    d = tmp_path / "desc"
    _write(d, "t.csv", (HEADER + "a,,first,,\nA ,,second,,\n").encode())
    result = load_bird_descriptions(d, schema)
    assert result.columns[("t", "a")].description == "first"
    assert any("described twice" in w for w in result.warnings)


def test_file_without_the_key_header_is_reported(tmp_path: Path) -> None:
    schema = DatabaseSchema(db_id="x", tables=(Table(name="t", columns=(Column(name="a"),)),))
    d = tmp_path / "desc"
    _write(d, "t.csv", b"name,description\na,something\n")
    result = load_bird_descriptions(d, schema)
    assert result.columns == {}
    assert result.warnings == ("t.csv: no original_column_name header",)


def test_dictionary_schema_descriptions_are_whitespace_cleaned() -> None:
    documented = DatabaseSchema(
        db_id="saas",
        tables=(
            Table(
                name="plans",
                description="  Price\nlist. ",
                columns=(Column(name="tier", description="Plan  tier.", value_description=""),),
            ),
        ),
    )
    result = descriptions_from_schema(documented)
    assert result.tables == {"plans": "Price list."}
    assert result.columns[("plans", "tier")] == ColumnNotes("Plan tier.", None)
