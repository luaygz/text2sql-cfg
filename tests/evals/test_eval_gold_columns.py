from __future__ import annotations

import pytest

from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.evals.metrics import GoldColumnsError, gold_columns


def _table(name: str, *columns: str) -> Table:
    return Table(name=name, columns=tuple(Column(name=c) for c in columns))


SCHEMA = DatabaseSchema(
    db_id="california_schools",
    tables=(
        _table("frpm", "CDSCode", "County Name", "Free Meal Count (K-12)", "Enrollment (K-12)"),
        _table("schools", "CDSCode", "City", "Zip", "School"),
        _table("satscores", "cds", "NumTstTakr", "AvgScrMath"),
    ),
)


def test_resolves_t1_t2_aliases_and_backticked_names():
    sql = (
        "SELECT T2.City FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode "
        "WHERE T1.`County Name` = 'Alameda' "
        "ORDER BY T1.`Free Meal Count (K-12)` / T1.`Enrollment (K-12)` DESC LIMIT 1"
    )
    assert gold_columns(sql, SCHEMA) == {
        ("schools", "City"),
        ("frpm", "CDSCode"),
        ("schools", "CDSCode"),
        ("frpm", "County Name"),
        ("frpm", "Free Meal Count (K-12)"),
        ("frpm", "Enrollment (K-12)"),
    }


def test_cte_outputs_resolve_to_the_base_columns_they_read():
    sql = (
        "WITH c AS (SELECT CDSCode, `County Name` AS cn FROM frpm) "
        "SELECT s.City, c.cn FROM c JOIN schools s ON s.CDSCode = c.CDSCode"
    )
    assert gold_columns(sql, SCHEMA) == {
        ("frpm", "CDSCode"),
        ("frpm", "County Name"),
        ("schools", "City"),
        ("schools", "CDSCode"),
    }


def test_cte_named_like_a_base_table_shadows_it():
    sql = "WITH schools AS (SELECT CDSCode AS City FROM frpm) SELECT schools.City FROM schools"
    assert gold_columns(sql, SCHEMA) == {("frpm", "CDSCode")}


def test_uncorrelated_and_correlated_subqueries():
    in_subquery = (
        "SELECT City FROM schools WHERE CDSCode IN "
        "(SELECT CDSCode FROM frpm WHERE `Enrollment (K-12)` > 100)"
    )
    assert gold_columns(in_subquery, SCHEMA) == {
        ("schools", "City"),
        ("schools", "CDSCode"),
        ("frpm", "CDSCode"),
        ("frpm", "Enrollment (K-12)"),
    }
    correlated = (
        "SELECT T1.School FROM schools T1 WHERE EXISTS (SELECT 1 FROM satscores T2 "
        "WHERE T2.cds = T1.CDSCode AND T2.AvgScrMath > 500)"
    )
    assert gold_columns(correlated, SCHEMA) == {
        ("schools", "School"),
        ("schools", "CDSCode"),
        ("satscores", "cds"),
        ("satscores", "AvgScrMath"),
    }


def test_derived_table_in_from_and_select_alias_in_order_by():
    sql = (
        "SELECT sub.n FROM (SELECT COUNT(*) AS n, City FROM schools GROUP BY City) AS sub "
        "ORDER BY sub.n DESC"
    )
    assert gold_columns(sql, SCHEMA) == {("schools", "City")}
    by_alias = "SELECT City, COUNT(*) AS cnt FROM schools GROUP BY City ORDER BY cnt DESC"
    assert gold_columns(by_alias, SCHEMA) == {("schools", "City")}


def test_double_quoted_string_literal_is_not_a_column():
    # SQLite falls back to a string literal when "..." names no column; BIRD gold SQL does this.
    sql = 'SELECT City FROM schools WHERE Zip = "94501"'
    assert gold_columns(sql, SCHEMA) == {("schools", "City"), ("schools", "Zip")}


def test_identifiers_are_case_insensitive_and_returned_in_schema_spelling():
    sql = "SELECT city FROM SCHOOLS WHERE `county name` IS NULL OR cdscode = 'x'"
    # `county name` is not a column of schools, so it is skipped rather than misattributed.
    assert gold_columns(sql, SCHEMA) == {("schools", "City"), ("schools", "CDSCode")}


def test_star_counts_every_column_of_the_table():
    assert gold_columns("SELECT * FROM satscores", SCHEMA) == {
        ("satscores", "cds"),
        ("satscores", "NumTstTakr"),
        ("satscores", "AvgScrMath"),
    }


def test_set_operation_branches_are_both_read():
    sql = "SELECT City FROM schools UNION SELECT `County Name` FROM frpm"
    assert gold_columns(sql, SCHEMA) == {("schools", "City"), ("frpm", "County Name")}


def test_unparseable_sql_raises():
    with pytest.raises(GoldColumnsError):
        gold_columns("SELECT FROM WHERE (", SCHEMA)
