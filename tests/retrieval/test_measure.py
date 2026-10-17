from __future__ import annotations

import pytest

from text2sql.catalog import Catalog
from text2sql.catalog.schema import DatabaseSchema
from text2sql.evals.metrics import GoldColumnsError
from text2sql.retrieval.measure import QuestionMeasure, gold_literals, summarize


@pytest.fixture
def schema(geo_catalog: Catalog) -> DatabaseSchema:
    return geo_catalog.schema()


def test_gold_literals_resolve_aliases_and_skip_patterns(schema: DatabaseSchema) -> None:
    sql = (
        "SELECT T1.name FROM city AS T1 JOIN country AS T2 ON T1.country_id = T2.country_id "
        "WHERE 'Germany' = T2.name AND T1.name IN ('Berlin', 'Paris') AND T1.candidate LIKE 'Lee' "
        "AND T1.name LIKE '%ork' AND T1.NAME <> 'york' AND T1.population = 5"
    )
    assert gold_literals(sql, schema) == {
        ("country", "name", "Germany"),
        ("city", "name", "Berlin"),
        ("city", "name", "Paris"),
        ("city", "candidate", "Lee"),
        ("city", "name", "york"),
    }


def test_gold_literals_inside_subqueries(schema: DatabaseSchema) -> None:
    sql = (
        "SELECT name FROM city "
        "WHERE country_id IN (SELECT country_id FROM country WHERE code = 'DE')"
    )
    assert gold_literals(sql, schema) == {("country", "code", "DE")}


def test_unparseable_gold_is_an_error(schema: DatabaseSchema) -> None:
    with pytest.raises(GoldColumnsError):
        gold_literals("SELEC name FROM", schema)


def _measure(
    qid: int,
    gold: list[tuple[str, str]] | None,
    linked: list[tuple[str, str]],
    *,
    passes: tuple[list[tuple[str, str]], list[tuple[str, str]]] = ([], []),
    shortlist: list[tuple[str, str]] | None = None,
    literals: list[tuple[str, str, str]] | None = None,
    retrievable: list[bool] | None = None,
    hits: list[bool] | None = None,
) -> QuestionMeasure:
    return QuestionMeasure(
        question_id=qid,
        db_id="geo",
        difficulty="simple",
        gold_columns=gold,
        linked_columns=linked,
        passes=list(passes),
        shortlist=shortlist or [],
        value_columns=[],
        full_columns=14,
        full_tokens=400,
        linked_tokens=100,
        gold_literals=literals or [],
        literal_retrievable=retrievable or [],
        literal_hits=hits or [],
        cost_usd=0.01,
    )


def test_summary_counts_full_recall_sizes_and_literal_hits(schema: DatabaseSchema) -> None:
    results = [
        _measure(
            1,
            [("city", "name"), ("country", "name")],
            [("city", "city_id"), ("city", "name"), ("country", "country_id"), ("country", "Name")],
            passes=([("city", "name")], [("country", "name")]),
            literals=[("city", "name", "Paris"), ("city", "name", "Atlantis")],
            retrievable=[True, False],
            hits=[True, False],
        ),
        _measure(
            2,
            [("city", "candidate"), ("city", "name")],
            [("city", "city_id"), ("city", "name")],
            passes=([("city", "name")], []),
            shortlist=[("city", "candidate")],
        ),
        _measure(3, None, [("city", "name")]),  # unresolvable gold: not in recall
    ]
    summary = summarize(results, {"geo": schema})
    assert (summary.questions, summary.gold_resolved) == (3, 2)
    returned, no_shortlist, pass1, pass2, no_llm = summary.variants
    assert (returned.full_recall.k, returned.full_recall.n) == (1, 2)
    assert returned.mean_column_recall == pytest.approx(0.75)
    assert no_shortlist.full_recall.k == 1  # q2 needs the shortlisted city.candidate
    assert pass1.full_recall.k == 1  # q1 needs pass 2's country.name
    assert pass2.mean_column_recall == pytest.approx(0.5)
    assert no_llm.mean_column_recall == pytest.approx(0.25)
    assert summary.full_recall_by_difficulty["simple"].k == 1
    assert summary.table_recall.k == 2
    assert (summary.literals, summary.retrievable_literals) == (2, 1)
    assert summary.literal_hit_rate is not None and summary.literal_hit_rate.value == 1.0
    assert summary.cost_usd == pytest.approx(0.03)
