"""Grammar size estimate and the gold-SQL coverage pipeline."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from text2sql.catalog.schema import Column, DatabaseSchema, Table, introspect_sqlite
from text2sql.config import REPO_ROOT, QueryMode
from text2sql.grammar import GrammarOptions, build_grammar
from text2sql.grammar.coverage import GoldQuery, measure_coverage, render_markdown
from text2sql.grammar.size import measure_grammar, regex_stats

requires_bird = pytest.mark.skipif(
    not (REPO_ROOT / "data" / "bird" / "mini_dev_sqlite.json").is_file(),
    reason="BIRD data absent; run the bird download",
)


def _random_schema(columns: int, width: int = 16) -> DatabaseSchema:
    rnd = random.Random(7)
    names = [
        "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(width))
        for _ in range(columns)
    ]
    return DatabaseSchema(
        db_id="random", tables=(Table(name="items", columns=tuple(Column(n) for n in names)),)
    )


def test_regex_stats_counts_atoms_and_branches() -> None:
    assert regex_stats(r"(?:ab|c[0-9]{2}|\.)") == (5, 2)
    assert regex_stats(r"[^'\\;]") == (1, 0)


def test_rule_symbols_are_counted() -> None:
    size = measure_grammar('start: "a" b? c*\nb: "x" | "y"\nc: B\n    | "z"\nB: /q|r/\n')
    assert (size.rules, size.symbol_refs, size.regex_atoms, size.regex_alternatives) == (3, 7, 2, 1)


def test_load_grows_with_the_schema() -> None:
    small = build_grammar(_random_schema(20)).size
    large = build_grammar(_random_schema(200)).size
    assert small.api_load < large.api_load
    assert small.fits_api_budget


def test_estimate_matches_the_measured_api_limit() -> None:
    # ADR-005: the API accepted this template with 215 random 16-letter columns and rejected
    # it with 216; 376/378 at 8 letters, 123/125 at 30 letters.
    for accepted, rejected, width in ((215, 216, 16), (376, 378, 8), (123, 125, 30)):
        assert build_grammar(_random_schema(accepted, width)).size.api_load <= 1.01
        assert build_grammar(_random_schema(rejected, width)).size.api_load >= 0.99


def test_oversized_grammar_is_flagged() -> None:
    grammar = build_grammar(_random_schema(400))
    assert not grammar.size.fits_api_budget


def test_coverage_reports_covered_failed_and_unchanged_results(
    shop_db: Path, shop_schema: DatabaseSchema
) -> None:
    queries = [
        GoldQuery(1, "shop", "bird", "select c.name from customers c where c.city = 'Paris'"),
        GoldQuery(2, "shop", "bird", "SELECT name, RANK() OVER (ORDER BY id) FROM customers"),
        GoldQuery(3, "shop", "arcwise", "SELECT GROUP_CONCAT(name) FROM customers"),
        GoldQuery(4, "shop", "arcwise", "DELETE FROM customers"),
    ]
    cases, grammars = measure_coverage(queries, lambda _: shop_schema, db_paths=lambda _: shop_db)
    by_id = {c.question_id: c for c in cases}
    assert by_id[1].covered and by_id[1].same_result is True and by_id[1].guidance_agrees
    assert by_id[2].category == "window function"
    assert by_id[3].category == "function not in allowlist: GROUP_CONCAT"
    assert by_id[4].category == "normalization failed" and by_id[4].normalized is None
    assert set(grammars) == {"shop"}

    from text2sql.grammar.coverage import CoverageReport

    report = CoverageReport(
        dataset="fixture", split="all", created_at="now", options="x", databases=[], cases=cases
    )
    assert report.coverage("bird") == 0.5
    markdown = render_markdown(report)
    assert "| bird | 2 | 1 | 50.0% | 2/2 | 2/2 |" in markdown
    assert "window function: 1" in markdown


@pytest.mark.bird
@requires_bird
def test_every_minidev_database_has_a_grammar_within_budget() -> None:
    from text2sql.data.bird import bird_db_path, minidev_db_ids

    for db_id in minidev_db_ids():
        schema = introspect_sqlite(bird_db_path(db_id), db_id)
        for options in (GrammarOptions(), GrammarOptions(QueryMode.TENANT, allow_abstain=True)):
            assert build_grammar(schema, options).size.fits_api_budget, db_id


@pytest.mark.bird
@requires_bird
def test_minidev_gold_coverage_is_at_least_95_percent() -> None:
    from text2sql.data.bird import bird_db_path, load_minidev

    queries = [GoldQuery(e.question_id, e.db_id, "bird", e.gold_sql) for e in load_minidev()]
    cases, _ = measure_coverage(queries, lambda db: introspect_sqlite(bird_db_path(db), db))
    assert sum(c.covered for c in cases) / len(cases) >= 0.95
    assert all(c.guidance_agrees is not False for c in cases)


@pytest.mark.bird
@requires_bird
def test_coverage_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    import typer
    from typer.testing import CliRunner

    from text2sql.grammar.coverage import CoverageReport, main

    app = typer.Typer()
    app.command()(main)
    result = CliRunner().invoke(app, ["--split", "test", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    report = CoverageReport.model_validate_json(
        (tmp_path / "grammar_coverage_test.json").read_text()
    )
    assert report.coverage("bird") >= 0.95
    assert "## Failures by category" in (tmp_path / "grammar_coverage_test.md").read_text()


FIXTURE = Path(__file__).parent / "fixtures" / "bird_dev_gold.json"


def test_dev_gold_coverage_on_the_committed_fixture() -> None:
    from text2sql.grammar.coverage import CoverageFixture

    fixture = CoverageFixture.model_validate_json(FIXTURE.read_text())
    cases, grammars = measure_coverage(fixture.queries, fixture.database_schema)
    for source in ("bird", "arcwise"):
        picked = [c for c in cases if c.source == source]
        assert len(picked) > 300
        assert sum(c.covered for c in picked) / len(picked) >= 0.95, source
    assert all(c.guidance_agrees is not False for c in cases)
    assert all(g.size.fits_api_budget for g in grammars.values())


@pytest.mark.bird
@requires_bird
def test_committed_fixture_matches_the_data(tmp_path: Path) -> None:
    import typer
    from typer.testing import CliRunner

    from text2sql.grammar.coverage import main

    app = typer.Typer()
    app.command()(main)
    target = tmp_path / "fixture.json"
    result = CliRunner().invoke(app, ["--split", "dev", "--write-fixture", str(target)])
    assert result.exit_code == 0, result.output
    assert target.read_text() == FIXTURE.read_text(), "regenerate with --write-fixture"
