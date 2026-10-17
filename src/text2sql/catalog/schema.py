"""Database schema model shared by grammar building, prompting, validation and scoping.

The schema is the single source of truth for which identifiers exist. The grammar builder turns
it into terminals, the prompt builder renders it for the model, and the AST validator checks
resolved identifiers against it. Names are matched case-insensitively, as SQLite does.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: str = ""
    primary_key: bool = False
    not_null: bool = False
    description: str | None = None
    """Human description (BIRD `database_description` CSV, SaaS data dictionary)."""
    value_description: str | None = None
    """Notes on encodings / units / allowed values, rendered next to the column."""
    sample_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ForeignKey:
    table: str
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True, slots=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    description: str | None = None

    def column(self, name: str) -> Column | None:
        key = name.lower()
        return next((c for c in self.columns if c.name.lower() == key), None)

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


@dataclass(frozen=True, slots=True)
class DatabaseSchema:
    db_id: str
    tables: tuple[Table, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    _index: Mapping[str, Table] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_index", {t.name.lower(): t for t in self.tables})

    def table(self, name: str) -> Table | None:
        return self._index.get(name.lower())

    def __iter__(self) -> Iterator[Table]:
        return iter(self.tables)

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tables)

    def subset(self, keep: Mapping[str, Collection[str] | None]) -> DatabaseSchema:
        """Restrict to the given tables; `None` keeps every column of that table.

        Primary-key and foreign-key columns of kept tables are always retained so that
        joins between kept tables stay expressible after schema linking prunes columns.
        """
        keep_l = {
            t.lower(): (None if cols is None else {c.lower() for c in cols})
            for t, cols in keep.items()
        }
        join_cols: dict[str, set[str]] = {}
        for fk in self.foreign_keys:
            if fk.table.lower() in keep_l and fk.ref_table.lower() in keep_l:
                join_cols.setdefault(fk.table.lower(), set()).add(fk.column.lower())
                join_cols.setdefault(fk.ref_table.lower(), set()).add(fk.ref_column.lower())
        tables: list[Table] = []
        for t in self.tables:
            key = t.name.lower()
            if key not in keep_l:
                continue
            wanted = keep_l[key]
            if wanted is None:
                tables.append(t)
                continue
            extra = join_cols.get(key, set())
            cols = tuple(
                c
                for c in t.columns
                if c.name.lower() in wanted or c.primary_key or c.name.lower() in extra
            )
            tables.append(replace(t, columns=cols))
        kept = {t.name.lower(): {c.name.lower() for c in t.columns} for t in tables}
        fks = tuple(
            fk
            for fk in self.foreign_keys
            if fk.column.lower() in kept.get(fk.table.lower(), set())
            and fk.ref_column.lower() in kept.get(fk.ref_table.lower(), set())
        )
        return DatabaseSchema(db_id=self.db_id, tables=tuple(tables), foreign_keys=fks)

    def without_columns(self, hidden: Mapping[str, Collection[str]]) -> DatabaseSchema:
        """Drop columns (e.g. `tenant_id`) so that neither prompt nor grammar can name them."""
        hidden_l = {t.lower(): {c.lower() for c in cols} for t, cols in hidden.items()}
        tables = tuple(
            replace(
                t,
                columns=tuple(
                    c
                    for c in t.columns
                    if c.name.lower() not in hidden_l.get(t.name.lower(), set())
                ),
            )
            for t in self.tables
        )
        kept = {t.name.lower(): {c.name.lower() for c in t.columns} for t in tables}
        fks = tuple(
            fk
            for fk in self.foreign_keys
            if fk.column.lower() in kept.get(fk.table.lower(), set())
            and fk.ref_column.lower() in kept.get(fk.ref_table.lower(), set())
        )
        return DatabaseSchema(db_id=self.db_id, tables=tables, foreign_keys=fks)


def quote_identifier(name: str) -> str:
    """Spell an identifier exactly as the grammar emits it (backticks when SQLite needs them).

    The rule lives in `text2sql.grammar.conventions.sql_identifier` so that prompts, grammar and
    gold-SQL normalization cannot drift apart. Imported here at call time because the grammar
    package imports this module.
    """
    from text2sql.grammar.conventions import sql_identifier

    return sql_identifier(name)


def introspect_sqlite(db_path: Path, db_id: str | None = None) -> DatabaseSchema:
    """Read tables, columns and foreign keys from a SQLite file opened read-only."""
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY rowid"
            )
        ]
        tables: list[Table] = []
        fks: list[ForeignKey] = []
        for name in names:
            qn = name.replace('"', '""')
            cols = tuple(
                Column(name=r[1], type=r[2] or "", not_null=bool(r[3]), primary_key=r[5] > 0)
                for r in conn.execute(f'PRAGMA table_info("{qn}")')
            )
            tables.append(Table(name=name, columns=cols))
            for r in conn.execute(f'PRAGMA foreign_key_list("{qn}")'):
                ref_table, from_col, to_col = r[2], r[3], r[4]
                if to_col is None:  # FK to the referenced table's primary key
                    ref_pk = [
                        c[1]
                        for c in conn.execute(
                            f'PRAGMA table_info("{ref_table.replace(chr(34), chr(34) * 2)}")'
                        )
                        if c[5] > 0
                    ]
                    to_col = ref_pk[0] if ref_pk else from_col
                fks.append(
                    ForeignKey(table=name, column=from_col, ref_table=ref_table, ref_column=to_col)
                )
        return DatabaseSchema(
            db_id=db_id or db_path.stem, tables=tuple(tables), foreign_keys=tuple(fks)
        )
    finally:
        conn.close()
