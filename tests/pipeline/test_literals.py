"""The literal check: which compared strings it looks up, what it reports, and the value repair
it triggers in the pipeline."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from pipeline_fakes import FRENCH, FakeLLM, config, request, run_pipeline

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.config import PRESETS, QueryMode, Settings, apply_overrides
from text2sql.data.saas import DEFAULT_DB_PATH, SAAS_DB_ID
from text2sql.pipeline import DatabaseResources
from text2sql.pipeline.literals import (
    ComparedLiteral,
    ValueMismatch,
    compared_literals,
    find_mismatches,
    literal_mismatches,
    mismatch_detail,
)
from text2sql.prompts import load_prompt
from text2sql.retrieval import ValueMatches
from text2sql.safety import ScopeContext

ResourcesFactory = Callable[..., DatabaseResources]
COMMANDER = ("commander", "Commander", "COMMANDER", " commander")


@pytest.fixture
def cards_db(tmp_path: Path) -> Path:
    path = tmp_path / "cards.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY, name TEXT, status TEXT, "Mana Cost" TEXT,
                power INTEGER, released DATE, rarity VARCHAR(10)
            );
            CREATE TABLE legalities (
                id INTEGER PRIMARY KEY, card_id INTEGER REFERENCES cards(id), format TEXT,
                status TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Ada Blade", "Legal", "{2}{W}", 3, "2020-01-05", "common"),
                (2, "O'Neil Fist", "Banned", "{R}", 5, "2021-03-01", "rare"),
                (3, "Cy Shield", " Restricted ", "{1}", 3, "2020-01-05", "Rare"),
            ],
        )
        formats = [*COMMANDER, "modern", "vintage"]
        conn.executemany(
            "INSERT INTO legalities (card_id, format, status) VALUES (?, ?, ?)",
            [(1 + i % 3, f, "Banned" if f == "modern" else "Legal") for i, f in enumerate(formats)],
        )
    conn.close()
    return path


@pytest.fixture
def schema(cards_db: Path) -> DatabaseSchema:
    return introspect_sqlite(cards_db)


def check(db: Path, sql: str, matches: ValueMatches | None = None) -> list[ValueMismatch]:
    return asyncio.run(literal_mismatches(sql, introspect_sqlite(db), db, matches or {}))


def where(condition: str) -> str:
    return f"SELECT T1.name FROM cards AS T1 WHERE {condition}"


def test_a_literal_in_the_wrong_case_is_reported_with_the_stored_value(cards_db: Path) -> None:
    assert check(cards_db, where("T1.status = 'legal'")) == [
        ValueMismatch(ComparedLiteral("cards", "status", "legal", like=False), ("Legal",), "case")
    ]


@pytest.mark.parametrize(
    "condition",
    [
        "T1.status = 'Legal'",
        "T1.status IN ('Legal', 'Banned')",
        "T1.status != 'Banned'",
        "T1.status LIKE 'legal'",  # LIKE ignores ASCII case, so the query already matches
    ],
)
def test_a_literal_the_column_holds_is_not_reported(cards_db: Path, condition: str) -> None:
    assert check(cards_db, where(condition)) == []


@pytest.mark.parametrize("condition", ["T1.status = 'restricted'", "T1.status LIKE 'restricted'"])
def test_surrounding_spaces_in_the_stored_value_count_as_close(
    cards_db: Path, condition: str
) -> None:
    [mismatch] = check(cards_db, where(condition))
    assert mismatch.stored == (" Restricted ",)


def test_every_comparison_form_is_checked_wherever_it_sits(cards_db: Path) -> None:
    sql = (
        "SELECT SUM(CASE WHEN T1.rarity = 'RARE' THEN 1 ELSE 0 END) FROM cards AS T1 "
        "WHERE T1.status IN ('legal', 'Banned') OR 'banned' = T1.status "
        "OR NOT T1.status IN ('restricted') OR T1.status <> 'legal'"
    )
    found = {(m.compared.column, m.compared.literal): set(m.stored) for m in check(cards_db, sql)}
    assert found == {
        ("rarity", "RARE"): {"rare", "Rare"},
        ("status", "legal"): {"Legal"},
        ("status", "banned"): {"Banned"},
        ("status", "restricted"): {" Restricted "},
    }


@pytest.mark.parametrize(
    "condition",
    [
        "T1.status LIKE 'leg%'",
        "T1.status LIKE 'l_gal'",
        "T1.status LIKE 'LEGAL!%' ESCAPE '!'",
        "lower(T1.status) = 'Legal'",
        "T1.status = T1.name",
        "T1.status IN (SELECT T2.status FROM legalities AS T2)",
    ],
)
def test_wildcard_patterns_and_computed_sides_are_not_checked(
    schema: DatabaseSchema, condition: str
) -> None:
    assert compared_literals(where(condition), schema) == []


@pytest.mark.parametrize(
    "condition", ["T1.power = '7'", "T1.released = '2020/01/05'", "T1.id IN ('9', '10')"]
)
def test_numeric_and_date_columns_are_skipped(schema: DatabaseSchema, condition: str) -> None:
    assert compared_literals(where(condition), schema) == []


@pytest.mark.parametrize(
    ("sql", "column"),
    [
        (
            "SELECT T1.name FROM cards AS T1 INNER JOIN legalities AS T2 "
            "ON T1.id = T2.card_id WHERE T2.status = 'banned'",
            ("legalities", "status"),
        ),
        (
            "WITH listed AS (SELECT T1.status AS state FROM cards AS T1) "
            "SELECT COUNT(*) FROM listed AS T2 WHERE T2.state = 'banned'",
            ("cards", "status"),
        ),
        (
            "SELECT COUNT(*) FROM (SELECT * FROM legalities) AS T3 WHERE T3.status = 'banned'",
            ("legalities", "status"),
        ),
        (
            "SELECT T1.name FROM cards AS T1 WHERE EXISTS (SELECT 1 FROM legalities AS T2 "
            "WHERE T2.card_id = T1.id AND T1.status = 'banned')",
            ("cards", "status"),
        ),
        ("SELECT name FROM cards WHERE status = 'banned'", ("cards", "status")),
    ],
)
def test_aliases_derived_tables_and_ctes_resolve_to_the_base_column(
    cards_db: Path, sql: str, column: tuple[str, str]
) -> None:
    [mismatch] = check(cards_db, sql)
    assert (mismatch.compared.table, mismatch.compared.column) == column
    assert mismatch.stored == ("Banned",)


def test_a_computed_cte_output_is_not_checked(schema: DatabaseSchema) -> None:
    sql = (
        "WITH x AS (SELECT lower(T1.status) AS s FROM cards AS T1) "
        "SELECT COUNT(*) FROM x AS T2 WHERE T2.s = 'Legal'"
    )
    assert compared_literals(sql, schema) == []


def test_the_literal_is_looked_up_as_a_bound_value(cards_db: Path) -> None:
    [quoted] = check(cards_db, where("T1.name = 'o''neil fist'"))
    assert quoted.stored == ("O'Neil Fist",)
    [spaced] = check(cards_db, where("T1.`Mana Cost` = '{2}{w}'"))
    assert (spaced.compared.column, spaced.stored) == ("Mana Cost", ("{2}{W}",))
    # Pasted into the lookup's text, this literal would match every row and hide the mismatch.
    hostile = "x' OR 'a' = 'a"
    sql = where("T1.status = 'x'' OR ''a'' = ''a'")
    [mismatch] = check(cards_db, sql, {("cards", "status"): ["Legal"]})
    assert (mismatch.compared.literal, mismatch.similarity) == (hostile, "retrieved")


def test_retrieved_values_are_offered_only_for_the_compared_column(cards_db: Path) -> None:
    sql = where("T1.status = 'Melbourne'")
    assert check(cards_db, sql) == []
    assert check(cards_db, sql, {("legalities", "status"): ["Legal"]}) == []
    [mismatch] = check(cards_db, sql, {("Cards", "Status"): ["Legal", "Banned", "x", "y"]})
    assert (mismatch.stored, mismatch.similarity) == (("Legal", "Banned", "x"), "retrieved")


def test_at_most_three_stored_values_are_named(cards_db: Path) -> None:
    sql = "SELECT COUNT(*) FROM legalities AS T2 WHERE T2.format = 'cOMMANDER'"
    [mismatch] = check(cards_db, sql)
    assert len(mismatch.stored) == 3
    assert set(mismatch.stored) <= set(COMMANDER)


def test_lookups_past_the_time_budget_are_skipped(cards_db: Path, schema: DatabaseSchema) -> None:
    compared = compared_literals(where("T1.status = 'legal'"), schema)
    assert compared
    assert find_mismatches(cards_db, compared, {}, budget_s=0.0) == []


def test_sql_that_does_not_parse_is_skipped(schema: DatabaseSchema) -> None:
    assert compared_literals("SELECT FROM WHERE", schema) == []


def test_the_detail_names_column_literal_and_stored_values(cards_db: Path) -> None:
    detail = mismatch_detail(check(cards_db, where("T1.`Mana Cost` = '{r}'")))
    assert detail == (
        "- cards.`Mana Cost` has no value '{r}'. Stored values that differ from it only in "
        "case or surrounding spaces: '{R}'."
    )


def test_literal_check_needs_repair() -> None:
    with pytest.raises(ValueError, match="literal_check needs repair=true"):
        apply_overrides(PRESETS["baseline"], {"literal_check": "true"})
    on = apply_overrides(PRESETS["baseline"], {"repair": "true", "literal_check": "true"})
    assert on.literal_check and on.repair


LOWER_FRENCH = "SELECT T1.name FROM singer AS T1 WHERE T1.country = 'france'"


@pytest.mark.parametrize(
    ("mode", "limit"), [(QueryMode.BENCHMARK, ""), (QueryMode.PRODUCTION, " LIMIT 10")]
)
def test_a_case_mismatch_triggers_a_value_repair_with_the_stored_value(
    settings: Settings, resources_factory: ResourcesFactory, mode: QueryMode, limit: str
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [LOWER_FRENCH + limit, FRENCH + limit]})

    answer, trace = run_pipeline(
        llm, config(repair=True, literal_check=True), resources_factory(mode=mode)
    )

    candidate = trace.candidates[0]
    assert [a.repair_kind for a in candidate.attempts] == ["value", None]
    assert candidate.attempts[0].status == "empty"
    assert llm.feedback == [candidate.attempts[0].feedback]
    repair = load_prompt("repair")
    assert llm.feedback[0] == "\n\n".join(
        [
            repair.render(
                "value",
                detail="- singer.country has no value 'france'. Stored values that differ "
                "from it only in case or surrounding spaces: 'France'.",
            ),
            repair.render("value_check"),
        ]
    )
    assert answer.sql == FRENCH + limit


def test_without_literal_check_the_mismatch_is_not_repaired(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [LOWER_FRENCH, FRENCH]})

    answer, trace = run_pipeline(llm, config(repair=True), resources_factory())

    assert answer.sql == LOWER_FRENCH
    assert llm.calls_for("repair") == []
    assert trace.candidates[0].attempts[0].repair_kind is None


def test_a_value_repair_counts_against_max_repairs(
    settings: Settings, resources_factory: ResourcesFactory
) -> None:
    llm = FakeLLM(settings, sql={("direct_full", 0): [LOWER_FRENCH, LOWER_FRENCH, FRENCH]})

    answer, trace = run_pipeline(
        llm, config(repair=True, literal_check=True, max_repairs=1), resources_factory()
    )

    candidate = trace.candidates[0]
    assert [a.repair_kind for a in candidate.attempts] == ["value", None]
    assert len(llm.calls_for("repair")) == 1
    assert answer.sql == LOWER_FRENCH


@pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="data/saas/crm.sqlite not generated (make saas)"
)
def test_tenant_mode_never_runs_the_lookups(settings: Settings, events_path: Path) -> None:
    sql = "SELECT T1.name FROM accounts AS T1 WHERE T1.lifecycle_stage = 'cuStomer' LIMIT 200"
    res = DatabaseResources.load(
        SAAS_DB_ID, dataset="saas", mode=QueryMode.TENANT, events_path=events_path
    )
    try:
        # Unscoped, the lookups would find the stored spellings of other tenants' rows too.
        compared = compared_literals(sql, res.visible_schema)
        assert find_mismatches(DEFAULT_DB_PATH, compared, {}) != []
        llm = FakeLLM(settings, sql={("direct_full", 0): [sql, sql]})
        req = request(QueryMode.TENANT, db_id=SAAS_DB_ID, scope=ScopeContext(tenant_id=2))

        _, trace = run_pipeline(llm, config(repair=True, literal_check=True), res, req)
    finally:
        res.close()

    assert trace.candidates[0].executed
    assert llm.calls_for("repair") == []
