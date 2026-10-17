from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import BaseModel
from retrieval_fakes import FakeLLM, analysis, meta

from text2sql.catalog import Catalog
from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.llm import Message, StructuredCallFailed
from text2sql.retrieval import linking
from text2sql.retrieval.columns import ColumnIndex, column_document, query_texts
from text2sql.retrieval.linking import LinkedColumn, LinkSelection, assemble, link_schema
from text2sql.retrieval.types import LinkResult, ValueMatches

E1 = [1.0] + [0.0] * 255


@pytest.fixture
def no_shortlist_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Random fake embeddings make the shortlist arbitrary; keep it out of the union."""
    monkeypatch.setattr(linking, "SHORTLIST_COLUMNS", 0)


def _select(*columns: tuple[str, str], tables: Sequence[str] = ()) -> LinkSelection:
    return LinkSelection(
        tables=list(tables), columns=[LinkedColumn(table=t, column=c) for t, c in columns]
    )


def _is_reversed(messages: Sequence[Message]) -> bool:
    text = messages[0].text
    return text.index("# Table: city") < text.index("# Table: country")


def _llm(first: LinkSelection | Exception, second: LinkSelection | Exception) -> FakeLLM:
    def answer(output: type[BaseModel], messages: Sequence[Message]) -> BaseModel | Exception:
        assert output is LinkSelection
        return second if _is_reversed(messages) else first

    return FakeLLM(answer)


def _link(
    llm: FakeLLM, catalog: Catalog, values: ValueMatches | None = None, question: str = "Q?"
) -> LinkResult:
    index, _ = asyncio.run(ColumnIndex.build(catalog, llm))
    return asyncio.run(
        link_schema(
            llm,
            catalog,
            question=question,
            evidence="hint",
            analysis=analysis(keywords=["city"]),
            values=values or {},
            model="small",
            effort="none",
            columns=index,
        )
    )


@pytest.mark.usefixtures("no_shortlist_columns")
def test_union_of_both_passes_plus_values_and_join_keys(geo_catalog: Catalog) -> None:
    llm = _llm(
        _select(("city", "name")),
        _select(("COUNTRY", "Name"), ("ghost", "col"), ("city", "nope"), tables=["city"]),
    )
    result = _link(llm, geo_catalog, values={("city", "candidate"): ["Lee"]})
    assert {t.name: [c.name for c in t.columns] for t in result.schema.tables} == {
        "country": ["country_id", "name"],
        "city": ["city_id", "country_id", "name", "candidate"],
    }
    assert result.columns == {
        ("country", "country_id"), ("country", "name"),
        ("city", "city_id"), ("city", "country_id"), ("city", "name"), ("city", "candidate"),
    }  # fmt: skip
    assert result.passes == (frozenset({("city", "name")}), frozenset({("country", "name")}))
    assert len(result.calls) == 3  # one embedding call, two selection passes


def test_each_pass_sees_the_whole_schema_in_its_own_fixed_order(geo_catalog: Catalog) -> None:
    llm = _llm(_select(), _select())
    _link(llm, geo_catalog)
    first, second = (messages for messages, _, _ in llm.structured_calls)
    assert not _is_reversed(first) and _is_reversed(second)
    assert all(m[0].cache_breakpoint and m[0].role == "developer" for m in (first, second))
    assert "Question: Q?" in first[1].text and "Evidence: hint" in first[1].text
    assert llm.output_caps == [linking.MAX_OUTPUT_TOKENS] * 2


def test_a_failed_pass_leaves_the_other_and_keeps_its_cost(geo_catalog: Catalog) -> None:
    failure = StructuredCallFailed("refusal", "no", meta=meta("failed", 0.25), raw_text=None)
    result = _link(_llm(failure, _select(("city", "name"))), geo_catalog)
    assert ("city", "name") in result.columns
    assert any(c.purpose == "failed" and c.cost_usd == 0.25 for c in result.calls)


@pytest.mark.usefixtures("no_shortlist_columns")
def test_nothing_selected_and_no_values_links_nothing(geo_catalog: Catalog) -> None:
    result = _link(_llm(_select(), _select()), geo_catalog)
    assert result.schema.tables == () and result.columns == frozenset()


def test_top_shortlist_columns_are_kept_without_any_selection(geo_catalog: Catalog) -> None:
    result = _link(_llm(_select(), _select()), geo_catalog)
    top = result.shortlist[: linking.SHORTLIST_COLUMNS]
    assert top and set(top) <= result.columns


def test_tables_sharing_a_key_name_keep_it_without_a_declared_foreign_key() -> None:
    full = DatabaseSchema(
        db_id="shop",
        tables=(
            Table("orders", (Column("order_id", primary_key=True), Column("CustomerID"))),
            Table("customers", (Column("customerid", primary_key=True), Column("name"))),
            Table("notes", (Column("name"), Column("CustomerID"))),
        ),
    )
    linked = assemble(full, [("orders", "order_id"), ("Customers", "name")], tables=["orders"])
    assert {t.name: [c.name for c in t.columns] for t in linked.tables} == {
        "orders": ["order_id", "CustomerID"],
        "customers": ["customerid", "name"],
    }
    alone = assemble(full, [("notes", "name"), ("customers", "name")])
    assert [c.name for c in alone.tables[1].columns] == ["name", "CustomerID"]  # pk in customers


def test_wide_schemas_show_only_touched_tables(
    geo_catalog: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linking, "FULL_VIEW_MAX_TOKENS", 1)
    monkeypatch.setattr(linking, "TOP_PER_QUERY", 1)
    city = geo_catalog.table("city")
    name = city.column("name") if city else None
    assert city is not None and name is not None
    llm = _llm(_select(), _select())
    llm.vectors = {column_document(city, name): E1, "Where?": E1, "hint": E1, "city": E1}
    result = _link(llm, geo_catalog, values={("country", "code"): ["DE"]}, question="Where?")
    assert result.shortlist == (("city", "name"),)
    shown = llm.structured_calls[0][0][0].text
    assert "# Table: city" in shown and "# Table: country" in shown
    assert "# Table: accounts" not in shown


def test_stale_column_index_is_refused(geo_catalog: Catalog) -> None:
    llm = _llm(_select(), _select())
    index, _ = asyncio.run(ColumnIndex.build(geo_catalog, llm))
    changed = geo_catalog.model_copy(update={"tables": geo_catalog.tables[:1]})
    with pytest.raises(ValueError, match="stale"):
        asyncio.run(
            link_schema(
                llm,
                changed,
                question="Q",
                evidence=None,
                analysis=analysis(),
                values={},
                model="m",
                effort="none",
                columns=index,
            )
        )


def test_column_index_round_trip(data_dir: Path, geo_catalog: Catalog) -> None:
    llm = FakeLLM()
    built, _ = asyncio.run(ColumnIndex.build(geo_catalog, llm))
    built.save()
    loaded = ColumnIndex.load("geo")
    assert loaded.columns == built.columns and loaded.matches(geo_catalog)
    assert (loaded.vectors == built.vectors).all()


def test_nearest_unions_each_querys_top_columns(geo_catalog: Catalog) -> None:
    index, _ = asyncio.run(ColumnIndex.build(geo_catalog, FakeLLM()))
    queries = index.vectors[[0, 4]]  # two queries that equal two column documents
    top = index.nearest(queries, 1)
    assert [col for col, _ in top] == [index.columns[0], index.columns[4]]
    assert all(score == pytest.approx(1.0) for _, score in top)


def test_query_texts_drop_blanks_and_duplicates() -> None:
    assert query_texts(" Q ", None, ["city", "", "Q", " city "]) == ["Q", "city"]
