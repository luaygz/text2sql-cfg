"""Column documents of one database and their embeddings: the first pass of schema linking.

One document per column holds the table and column names, the table description, the human (or
else LLM) column description and the value description, which is what CHESS's context retrieval
embeds (as separate documents per field; one combined document is enough here and costs a third
of the vectors). Documents are embedded once per database and stored under
data/indexes/<db_id>/ next to the value index.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from text2sql.catalog import Catalog, CatalogColumn, CatalogTable
from text2sql.llm import CallMeta
from text2sql.retrieval.calls import EMBEDDING_DIMENSIONS, EmbeddingLLM, Matrix, embed
from text2sql.retrieval.store import database_dir, dataset_of, missing

PURPOSE = "retrieval.columns"
MAX_DOCUMENT_CHARS = 600


def column_document(table: CatalogTable, column: CatalogColumn) -> str:
    parts = [f"Table {table.name}"]
    if table.description:
        parts[0] += f" ({table.description})"
    parts.append(f"column {column.name}")
    if column.best_description:
        parts.append(column.best_description)
    if column.value_description:
        parts.append(column.value_description)
    text = ". ".join(" ".join(p.split()) for p in parts)
    return text[:MAX_DOCUMENT_CHARS]


class _ColumnsFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format_version: Literal[1] = 1
    db_id: str
    dimensions: int
    columns: list[tuple[str, str]]
    documents: list[str]


@dataclass(frozen=True)
class ColumnIndex:
    db_id: str
    columns: tuple[tuple[str, str], ...]
    """(table, column) in catalog spelling, catalog order."""
    documents: tuple[str, ...]
    vectors: Matrix

    @classmethod
    async def build(cls, catalog: Catalog, llm: EmbeddingLLM) -> tuple[ColumnIndex, CallMeta]:
        pairs = [(t, c) for t in catalog.tables for c in t.columns]
        documents = tuple(column_document(t, c) for t, c in pairs)
        vectors, meta = await embed(llm, documents, purpose=PURPOSE)
        columns = tuple((t.name, c.name) for t, c in pairs)
        return cls(catalog.db_id, columns, documents, vectors), meta

    @classmethod
    def load(cls, db_id: str) -> ColumnIndex:
        directory = database_dir(db_id)
        path = directory / "columns.json"
        if not path.is_file():
            raise missing(path, dataset_of(db_id))
        stored = _ColumnsFile.model_validate_json(path.read_bytes())
        vectors = np.load(directory / "columns.npy")
        if stored.dimensions != EMBEDDING_DIMENSIONS or vectors.shape != (
            len(stored.columns),
            EMBEDDING_DIMENSIONS,
        ):
            raise ValueError(f"{path} does not match the current embedding settings; rebuild it")
        return cls(
            stored.db_id,
            tuple((t, c) for t, c in stored.columns),
            tuple(stored.documents),
            vectors.astype(np.float32),
        )

    def save(self) -> None:
        directory = database_dir(self.db_id)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "columns.npy", self.vectors)
        stored = _ColumnsFile(
            db_id=self.db_id,
            dimensions=EMBEDDING_DIMENSIONS,
            columns=list(self.columns),
            documents=list(self.documents),
        )
        (directory / "columns.json").write_text(stored.model_dump_json(), encoding="utf-8")

    def matches(self, catalog: Catalog) -> bool:
        """Whether this index was built from a catalog with the same columns and documents."""
        pairs = [(t, c) for t in catalog.tables for c in t.columns]
        return self.documents == tuple(column_document(t, c) for t, c in pairs)

    def nearest(self, queries: Matrix, k: int) -> list[tuple[tuple[str, str], float]]:
        """Union of each query's `k` most similar columns, with the best cosine any query gave,
        highest first."""
        if not len(queries) or not self.columns:
            return []
        scores = queries @ self.vectors.T
        best: dict[int, float] = {}
        for row in scores:
            for i in np.argsort(-row, kind="stable")[:k]:
                best[int(i)] = max(best.get(int(i), -1.0), float(row[i]))
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(self.columns[i], score) for i, score in ranked]


def query_texts(question: str, evidence: str | None, keywords: Sequence[str]) -> list[str]:
    """The question, the evidence and each keyword on its own. CHESS embeds question plus
    keyword and evidence plus keyword; bare keywords recur across questions, so their
    embeddings are cache hits and the committed response cache grows by far less."""
    texts = [question, evidence or "", *keywords]
    return list(dict.fromkeys(t for t in (" ".join(t.split()) for t in texts) if t))
