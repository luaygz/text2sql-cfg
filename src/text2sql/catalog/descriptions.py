"""Human column descriptions: BIRD `database_description/<table>.csv` files and data dictionaries.

BIRD's CSVs are hand-made and inconsistent: some are UTF-8 with a BOM, some cp1252/latin-1, some
mostly UTF-8 with a few stray cp1252 bytes; file names and `original_column_name` cells differ
from the real identifiers in case, whitespace and punctuation. Everything here resolves names
against the real schema and reports what it could not match instead of dropping it silently.
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from text2sql.catalog.schema import DatabaseSchema, Table

_BOM = b"\xef\xbb\xbf"
_FALLBACK_ERRORS = "text2sql.cp1252_fallback"


@dataclass(frozen=True, slots=True)
class ColumnNotes:
    description: str | None = None
    value_description: str | None = None


@dataclass(frozen=True, slots=True)
class Descriptions:
    """Descriptions resolved to exact schema names: `columns[(table, column)]`."""

    columns: Mapping[tuple[str, str], ColumnNotes] = field(default_factory=dict)
    tables: Mapping[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def _cp1252_fallback(err: UnicodeError) -> tuple[str, int]:
    if not isinstance(err, UnicodeDecodeError):
        raise err
    bad = err.object[err.start : err.end]
    # cp1252 leaves five bytes undefined; latin-1 maps every byte, so use it for those.
    text = "".join(bytes([b]).decode("cp1252", errors="ignore") or chr(b) for b in bad)
    return text, err.end


codecs.register_error(_FALLBACK_ERRORS, _cp1252_fallback)


def decode_text(raw: bytes) -> tuple[str, bool]:
    """Decode as UTF-8 (BOM stripped), reading invalid bytes as cp1252.

    Returns the text and whether any fallback was needed. Per-byte fallback keeps the valid
    UTF-8 in mixed files intact, which decoding the whole file as cp1252 would mangle.
    """
    raw = raw.removeprefix(_BOM)
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors=_FALLBACK_ERRORS), True


def clean_text(text: str | None) -> str | None:
    """Collapse whitespace (BIRD cells contain newlines and runs of spaces); empty -> None."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned or None


def name_key(name: str) -> str:
    """Loose identifier key: case, whitespace and punctuation ignored."""
    return re.sub(r"[^0-9a-z]", "", name.lower())


def load_bird_descriptions(description_dir: Path, schema: DatabaseSchema) -> Descriptions:
    """Read every `<table>.csv` in a BIRD `database_description` directory."""
    columns: dict[tuple[str, str], ColumnNotes] = {}
    warnings: list[str] = []
    described: set[str] = set()
    for path in sorted(description_dir.glob("*.csv")):
        table = _match_table(path.stem, schema)
        if table is None:
            warnings.append(f"{path.name}: no table named like {path.stem!r}")
            continue
        if table.name in described:
            warnings.append(f"{path.name}: second description file for {table.name!r}, ignored")
            continue
        described.add(table.name)
        text, fell_back = decode_text(path.read_bytes())
        if fell_back:
            warnings.append(f"{path.name}: not valid UTF-8, stray bytes read as cp1252")
        notes, file_warnings = _parse_table_csv(text, table)
        warnings.extend(f"{path.name}: {w}" for w in file_warnings)
        columns.update(((table.name, col), n) for col, n in notes.items())
    warnings.extend(
        f"no description file for table {t.name!r}" for t in schema if t.name not in described
    )
    return Descriptions(columns=columns, warnings=tuple(warnings))


def descriptions_from_schema(documented: DatabaseSchema) -> Descriptions:
    """Take descriptions already attached to a schema (the SaaS data dictionary)."""
    return Descriptions(
        columns={
            (t.name, c.name): ColumnNotes(
                description=clean_text(c.description),
                value_description=clean_text(c.value_description),
            )
            for t in documented
            for c in t.columns
        },
        tables={t.name: d for t in documented if (d := clean_text(t.description)) is not None},
    )


def _match_table(stem: str, schema: DatabaseSchema) -> Table | None:
    exact = schema.table(stem.strip())
    if exact is not None:
        return exact
    key = name_key(stem)
    return next((t for t in schema if name_key(t.name) == key), None)


def _parse_table_csv(text: str, table: Table) -> tuple[dict[str, ColumnNotes], list[str]]:
    reader = csv.reader(io.StringIO(text))
    header = [name_key(h) for h in next(reader, [])]
    try:
        i_orig = header.index("originalcolumnname")
    except ValueError:
        return {}, ["no original_column_name header"]
    position: dict[str, int] = {
        h: header.index(h)
        for h in ("columnname", "columndescription", "valuedescription")
        if h in header
    }

    def cell(row: list[str], key: str) -> str | None:
        i = position.get(key)
        return clean_text(row[i]) if i is not None and i < len(row) else None

    notes: dict[str, ColumnNotes] = {}
    warnings: list[str] = []
    for row in reader:
        original = clean_text(row[i_orig]) if i_orig < len(row) else None
        if original is None:
            continue
        expanded = cell(row, "columnname")
        column = _match_column(original, expanded, table)
        if column is None:
            warnings.append(f"column {original!r} not in table {table.name!r}")
            continue
        if column in notes:
            warnings.append(f"column {original!r} described twice, kept the first")
            continue
        description = _merge_description(column, expanded, cell(row, "columndescription"))
        notes[column] = ColumnNotes(
            description=description,
            value_description=_strip_repeat(cell(row, "valuedescription"), description),
        )
    return notes, warnings


def _match_column(original: str, expanded: str | None, table: Table) -> str | None:
    exact = table.column(original)
    if exact is not None:
        return exact.name
    for candidate in (original, expanded):
        if candidate is None:
            continue
        key = name_key(candidate)
        found = next((c.name for c in table.columns if name_key(c.name) == key), None)
        if found is not None:
            return found
    return None


def _merge_description(column: str, expanded: str | None, description: str | None) -> str | None:
    """Join BIRD's expanded name and description, dropping parts that only repeat the name."""
    name = name_key(column)
    if description is not None and name_key(description) == name:
        description = None
    if expanded is not None and (
        name_key(expanded) == name
        or (description is not None and name_key(expanded) in name_key(description))
    ):
        expanded = None
    return "; ".join(p for p in (expanded, description) if p is not None) or None


def _strip_repeat(notes: str | None, description: str | None) -> str | None:
    """BIRD value notes often restate the description first; keep only what they add."""
    if notes is None or description is None:
        return notes
    if notes.lower().startswith(description.lower()):
        notes = notes[len(description) :].lstrip(" .;:,")
    return notes or None
