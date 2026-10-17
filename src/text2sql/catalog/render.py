"""Schema text for prompts, in the style of XiYan-SQL's M-Schema.

```
【DB_ID】 california_schools
【Schema】
# Table: frpm
[
(CDSCode:TEXT, Primary Key, Foreign Key, Examples: ['01100170109835', '01100170112607']),
(`Academic Year`:TEXT, Examples: ['2014-2015'])
]
【Foreign keys】
frpm.CDSCode=schools.CDSCode
【Matched values】
schools.County: 'Alameda'
```

Output depends only on the catalog and the arguments, and tables, columns and foreign keys keep
catalog order, so the same database renders to the same bytes and stays in the prompt cache.
Question-specific matched values come last for the same reason; `render_matched_values` returns
that block alone for prompts that put it in the user message instead. Identifiers are written
with `quote_identifier`, exactly as the grammar emits them. Sample values are rendered as SQL
literals (`'1'` vs `1`), which shows the storage type and marks them as data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from text2sql.catalog.model import Catalog, CatalogColumn, CatalogTable, SampleValue
from text2sql.catalog.schema import DatabaseSchema, ForeignKey, quote_identifier

MAX_EXAMPLES = 3
MAX_MATCHED_VALUES = 5
# M-Schema's example rules (XGenerationLab/M-Schema, m_schema.py): one example for date/time
# columns or when any example is longer than 20 characters, none when any is longer than 50.
_ONE_EXAMPLE_CHARS = 20
_NO_EXAMPLE_CHARS = 50
_DATE_TYPES = frozenset({"DATE", "TIME", "DATETIME", "TIMESTAMP"})


def render_schema(
    catalog: Catalog,
    *,
    subset: DatabaseSchema | None = None,
    samples: bool = True,
    descriptions: bool = True,
    matched_values: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> str:
    """Render the whole catalog, or only the tables and columns present in `subset`."""
    tables, foreign_keys = _selection(catalog, subset)
    fk_columns = {(fk.table.lower(), fk.column.lower()) for fk in foreign_keys}
    lines = [f"【DB_ID】 {catalog.db_id}", "【Schema】"]
    for table, columns in tables:
        header = f"# Table: {quote_identifier(table.name)}"
        if descriptions and table.description:
            header += f", {_one_line(table.description)}"
        lines.append(header)
        lines.append("[")
        lines.append(
            ",\n".join(
                _column_line(
                    c,
                    (table.name.lower(), c.name.lower()) in fk_columns,
                    samples=samples,
                    descriptions=descriptions,
                )
                for c in columns
            )
        )
        lines.append("]")
    if foreign_keys:
        lines.append("【Foreign keys】")
        lines.extend(
            f"{_qualified(fk.table, fk.column)}={_qualified(fk.ref_table, fk.ref_column)}"
            for fk in foreign_keys
        )
    text = "\n".join(lines)
    matched = _matched_block(tables, matched_values or {})
    return f"{text}\n{matched}" if matched else text


def render_matched_values(
    catalog: Catalog,
    matched_values: Mapping[tuple[str, str], Sequence[str]],
    *,
    subset: DatabaseSchema | None = None,
) -> str:
    """Only the `【Matched values】` block ("" when nothing applies).

    For prompts that keep the rendered schema as a cacheable prefix and put question-specific
    text in the user message. Values for columns outside `subset` are dropped, since the model
    could not use those columns anyway.
    """
    tables, _ = _selection(catalog, subset)
    return _matched_block(tables, matched_values)


def estimate_tokens(text: str) -> int:
    """Rough prompt size (4 characters per token), for size reports, not for billing."""
    return (len(text) + 3) // 4


type _Selection = tuple[list[tuple[CatalogTable, list[CatalogColumn]]], tuple[ForeignKey, ...]]


def _selection(catalog: Catalog, subset: DatabaseSchema | None) -> _Selection:
    if subset is None:
        return [(t, list(t.columns)) for t in catalog.tables], catalog.foreign_keys
    picked: list[tuple[CatalogTable, list[CatalogColumn]]] = []
    for table in catalog.tables:
        wanted = subset.table(table.name)
        if wanted is None:
            continue
        names = {c.name.lower() for c in wanted.columns}
        unknown = names - {c.name.lower() for c in table.columns}
        if unknown:
            raise ValueError(f"subset columns not in catalog table {table.name!r}: {unknown}")
        picked.append((table, [c for c in table.columns if c.name.lower() in names]))
    missing = {t.name for t in subset} - {t.name for t, _ in picked}
    if missing:
        raise ValueError(f"subset tables not in catalog {catalog.db_id!r}: {missing}")
    present = {(t.name.lower(), c.name.lower()) for t, cols in picked for c in cols}
    fks = tuple(
        fk
        for fk in catalog.foreign_keys
        if (fk.table.lower(), fk.column.lower()) in present
        and (fk.ref_table.lower(), fk.ref_column.lower()) in present
    )
    return picked, fks


def _column_line(column: CatalogColumn, is_fk: bool, *, samples: bool, descriptions: bool) -> str:
    name = quote_identifier(column.name)
    parts = [f"{name}:{column.type.upper()}" if column.type else name]
    if column.primary_key:
        parts.append("Primary Key")
    if is_fk:
        parts.append("Foreign Key")
    if descriptions:
        if column.best_description:
            parts.append(_one_line(column.best_description))
        if column.value_description:
            parts.append(f"Notes: {_one_line(column.value_description)}")
    examples = _examples(column) if samples else []
    if examples:
        parts.append(f"Examples: [{', '.join(examples)}]")
    return f"({', '.join(parts)})"


def _examples(column: CatalogColumn) -> list[str]:
    values = column.samples[:MAX_EXAMPLES]
    if not values:
        return []
    longest = max(len(str(v)) for v in values)
    if column.type.upper() in _DATE_TYPES:
        values = values[:1]
    elif longest > _NO_EXAMPLE_CHARS:
        return []
    elif longest > _ONE_EXAMPLE_CHARS:
        values = values[:1]
    return [_literal(v) for v in values]


def _matched_block(
    tables: Iterable[tuple[CatalogTable, list[CatalogColumn]]],
    matched_values: Mapping[tuple[str, str], Sequence[str]],
) -> str:
    by_key: dict[tuple[str, str], list[str]] = {}
    for (table_name, column_name), values in matched_values.items():
        by_key.setdefault((table_name.lower(), column_name.lower()), []).extend(values)
    lines: list[str] = []
    for table, columns in tables:
        for column in columns:
            found = by_key.get((table.name.lower(), column.name.lower()))
            if not found:
                continue
            # Exact spelling: these are the literals the model should copy into the query.
            unique = list(dict.fromkeys(found))[:MAX_MATCHED_VALUES]
            literals = ", ".join(_string_literal(v) for v in unique)
            lines.append(f"{_qualified(table.name, column.name)}: {literals}")
    return "\n".join(["【Matched values】", *lines]) if lines else ""


def _literal(value: SampleValue) -> str:
    if isinstance(value, str):
        return _string_literal(_one_line(value))
    return repr(value)


def _string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _qualified(table: str, column: str) -> str:
    return f"{quote_identifier(table)}.{quote_identifier(column)}"


def _one_line(text: str) -> str:
    return " ".join(text.split())
