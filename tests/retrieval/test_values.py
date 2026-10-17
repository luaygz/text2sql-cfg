from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from conftest import TENANT_POLICY
from retrieval_fakes import FakeLLM, analysis

from text2sql.catalog import Catalog, CatalogColumn
from text2sql.data.saas import DEFAULT_DB_PATH, SAAS_DB_ID, canary_values, saas_scope_policy
from text2sql.retrieval.store import build_command
from text2sql.retrieval.values import (
    MAX_VALUES_PER_COLUMN,
    ValueIndex,
    eligible_column,
    keep_column,
    search_strings,
)


def _indexed(index: ValueIndex) -> dict[tuple[str, str], list[str]]:
    return {(t, c): index.column_values(t, c) for t, c in index.columns}


class TestColumnFilters:
    @pytest.mark.parametrize(
        ("name", "type_", "primary_key", "expected"),
        [
            ("name", "TEXT", False, True),
            ("candidate", "TEXT", False, True),  # contains "date" but is not a date
            ("player_api_id", "INTEGER", False, False),
            ("mtgjsonV4Id", "TEXT", False, False),
            ("homepage_url", "TEXT", False, False),
            ("Email", "TEXT", False, False),
            ("birth_date", "TEXT", False, False),
            ("lastLoginTime", "TEXT", False, False),
            ("StreetAbr", "TEXT", False, False),
            ("code", "TEXT", True, False),
            ("issued", "DATE", False, False),
            ("amount", "REAL", False, False),
            ("code", "", False, True),  # untyped columns can hold text
        ],
    )
    def test_eligible_column(
        self, name: str, type_: str, primary_key: bool, expected: bool
    ) -> None:
        column = CatalogColumn(name=name, type=type_, primary_key=primary_key)
        assert eligible_column(column) is expected

    def test_values_that_look_like_numbers_dates_or_urls_disqualify_a_column(self) -> None:
        assert keep_column("label", ["red", "green", "blue"])
        assert not keep_column("zip", ["94606", "94606-1234", "10001"])
        assert not keep_column("opened", ["2001-02-03", "2004-05-06 10:00:00"])
        assert not keep_column("site", ["https://a.example", "www.b.example"])
        assert not keep_column("label", [])

    def test_long_free_text_is_skipped_unless_few_values(self) -> None:
        prose = [f"{i} " + "a long sentence of free text " * 3 for i in range(200)]
        assert not keep_column("notes", prose)
        assert keep_column("notes", prose[:50])
        assert keep_column("full_name", prose)  # name columns get a larger allowance


def test_search_strings_follow_chess() -> None:
    assert search_strings("Ian James Thorpe") == [
        "Ian James Thorpe", "Ian", "James Thorpe", "Ian James", "Thorpe",
    ]  # fmt: skip
    assert search_strings("bond_type = '#'") == [
        "bond_type = '#'", "bond_type", "= '#'", "bond_type =", "#",
    ]  # fmt: skip
    assert search_strings("  ") == []


class TestBuild:
    def test_indexes_only_entity_columns(self, geo_catalog: Catalog, geo_db: Path) -> None:
        index = ValueIndex.build(geo_catalog, geo_db)
        indexed = _indexed(index)
        assert indexed[("city", "name")] == sorted(
            ["New York", "Newark", "New Orleans", "Berlin", "Paris", "Munich", "Hamburg", "york"]
        )
        assert ("city", "candidate") in indexed
        for skipped in ("homepage_url", "founded", "population", "city_id"):
            assert ("city", skipped) not in indexed

    def test_tenant_tables_are_skipped_without_a_policy(
        self, tenant_catalog: Catalog, geo_db: Path
    ) -> None:
        index = ValueIndex.build(tenant_catalog, geo_db)
        assert not any(t == "accounts" for t, _ in index.columns)

    def test_tenant_tables_contribute_only_values_every_tenant_has(
        self, tenant_catalog: Catalog, geo_db: Path
    ) -> None:
        index = ValueIndex.build(tenant_catalog, geo_db, policy=TENANT_POLICY)
        indexed = _indexed(index)
        assert indexed[("accounts", "stage")] == ["lost", "won"]  # "pending" is tenant 1 only
        assert indexed[("accounts", "name")] == ["Shared Co"]
        assert "Acme Secret One" not in index.values and "Globex Secret Two" not in index.values

    def test_round_trip_and_missing_index_error(
        self, data_dir: Path, geo_catalog: Catalog, geo_db: Path
    ) -> None:
        with pytest.raises(FileNotFoundError, match=re.escape(build_command("bird"))):
            ValueIndex.load("geo")
        built = ValueIndex.build(geo_catalog, geo_db)
        built.save()
        loaded = ValueIndex.load("geo")
        assert loaded.columns == built.columns and loaded.values == built.values
        found, _ = asyncio.run(loaded.match(analysis(literals=["paris"]), question="", llm=None))
        assert found == {("city", "name"): ["Paris"]}


@pytest.mark.skipif(not DEFAULT_DB_PATH.exists(), reason="SaaS database not generated")
def test_saas_index_holds_no_canary(data_dir: Path) -> None:
    from text2sql.catalog import build_catalog
    from text2sql.catalog.descriptions import descriptions_from_schema
    from text2sql.data.saas import load_saas_schema

    policy = saas_scope_policy()
    catalog = build_catalog(
        DEFAULT_DB_PATH,
        SAAS_DB_ID,
        descriptions=descriptions_from_schema(load_saas_schema(DEFAULT_DB_PATH)),
        policy=policy,
    )
    index = ValueIndex.build(catalog, DEFAULT_DB_PATH, policy=policy)
    values = {v.casefold() for v in index.values}
    leaked = [c for c in map(str, canary_values()) if c.casefold() in values]
    assert index.values and not leaked


class TestMatch:
    @pytest.fixture
    def index(self, geo_catalog: Catalog, geo_db: Path) -> ValueIndex:
        return ValueIndex.build(geo_catalog, geo_db)

    def test_exact_match_ignores_case_and_spacing(self, index: ValueIndex) -> None:
        found, calls = asyncio.run(
            index.match(analysis(literals=["  new   YORK "]), question="", llm=None)
        )
        assert found[("city", "name")][0] == "New York"
        assert calls == []

    def test_typo_is_found_through_lsh_and_edit_similarity(self, index: ValueIndex) -> None:
        found, _ = asyncio.run(index.match(analysis(literals=["Hamburgg"]), question="", llm=None))
        assert found == {("city", "name"): ["Hamburg"]}

    def test_quoted_question_text_is_searched(self, index: ValueIndex) -> None:
        found, _ = asyncio.run(index.match(analysis(), question="Cities in 'Germany'?", llm=None))
        assert found == {("country", "name"): ["Germany"]}

    def test_embedding_pass_drops_lexically_close_but_unrelated_values(
        self, index: ValueIndex
    ) -> None:
        same = [1.0] + [0.0] * 255
        llm = FakeLLM(vectors={"New Yrok": same, "New York": same})
        found, calls = asyncio.run(
            index.match(analysis(literals=["New Yrok"]), question="", llm=llm)
        )
        assert found == {("city", "name"): ["New York"]}
        assert len(calls) == 1
        embedded = llm.embedded[0]
        assert "New Yrok" in embedded and "New York" in embedded
        assert set(embedded) <= {"New Yrok", "New", "Yrok", *index.values}  # LSH candidates only

    def test_without_llm_the_edit_cut_alone_decides(self, index: ValueIndex) -> None:
        found, _ = asyncio.run(index.match(analysis(literals=["New Yrok"]), question="", llm=None))
        assert found[("city", "name")][0] == "New York"
        assert len(found[("city", "name")]) <= MAX_VALUES_PER_COLUMN

    def test_values_per_column_are_capped(self, index: ValueIndex) -> None:
        found, _ = asyncio.run(
            index.match(analysis(literals=list(index.values)), question="", llm=None)
        )
        assert all(len(v) <= MAX_VALUES_PER_COLUMN for v in found.values())
        assert (
            found[("city", "name")] == index.column_values("city", "name")[:MAX_VALUES_PER_COLUMN]
        )

    def test_no_terms_no_matches(self, index: ValueIndex) -> None:
        assert asyncio.run(index.match(analysis(), question="How many?", llm=FakeLLM())) == ({}, [])
