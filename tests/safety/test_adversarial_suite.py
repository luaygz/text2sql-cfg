"""The SQL-level adversarial suite, run under pytest: no network, no API key, no `make data`.

`run_safety_suite` generates the deterministic SaaS database into a temporary directory and runs
every case in evals/safety/cases.yaml through the full guard and through each layer alone.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from text2sql.data.saas import planted_injections
from text2sql.evals.safety_suite import (
    CASES_PATH,
    SafetySuiteReport,
    load_cases,
    run_safety_suite,
)
from text2sql.evals.safety_suite.render import CHART_FILE, JSON_FILE, MARKDOWN_FILE

SPEC_CATEGORIES = {
    "ddl_dml",
    "multi_statement",
    "comment",
    "system_catalog",
    "attach_and_io",
    "function_allowlist",
    "resource_exhaustion",
    "cross_tenant",
    "hidden_column",
    "placeholder",
    "homoglyph",
    "quoting",
    "in_table",
    "over_long",
    "injection_payload",
}


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("safety-report")


@pytest.fixture(scope="module")
def report(out_dir: Path) -> SafetySuiteReport:
    return run_safety_suite(out_dir=out_dir)


def failing(report: SafetySuiteReport, check: Callable[..., bool]) -> list[str]:
    return [r.id for r in report.results if check(r)]


def test_no_violation_reaches_layer_3_or_the_database(report: SafetySuiteReport) -> None:
    assert failing(report, lambda r: r.violation_at_executor) == []
    assert failing(report, lambda r: r.violation_at_db) == []
    assert report.violations_at_executor == report.violations_at_db == 0
    assert report.db_unchanged


def test_every_responsible_layer_stops_its_cases_on_its_own(report: SafetySuiteReport) -> None:
    assert failing(report, lambda r: r.isolation_failures) == []
    for layer, count in report.responsible_by_layer.items():
        assert count.cases >= 20, f"{layer} is responsible for too few cases to show anything"
        assert count.held == count.cases


def test_every_stop_is_logged_as_exactly_one_safety_event(report: SafetySuiteReport) -> None:
    assert failing(report, lambda r: r.unlogged_stop) == []
    stopped = [r for r in report.results if r.guard.stopped_at is not None]
    assert stopped
    assert all(r.guard.events == 1 for r in stopped)


def test_the_suite_covers_the_spec(report: SafetySuiteReport) -> None:
    assert report.n_cases >= 100
    assert set(report.cases_by_category) >= SPEC_CATEGORIES
    assert report.passed
    assert sum(report.stops_by_layer.values()) == report.n_cases


def test_contain_cases_would_leak_without_scoping(report: SafetySuiteReport) -> None:
    # Each cross-tenant probe must be a live attack: run unscoped by layer 3 alone it leaks.
    contain = [r for r in report.results if r.expect == "contain"]
    assert len(contain) >= 30
    assert [r.id for r in contain if r.isolation["executor"].outcome != "leaked"] == []


def test_bounded_cases_are_stopped_by_layer_3(report: SafetySuiteReport) -> None:
    bounded = [r for r in report.results if r.expect == "bounded"]
    assert bounded
    assert {r.guard.stopped_at for r in bounded} == {"executor"}
    assert {r.guard.rule for r in bounded} <= {"timeout", "too_large"}


def test_every_planted_injection_has_a_payload_case() -> None:
    payload_tenants = {c.tenant for c in load_cases() if c.category == "injection_payload"}
    assert {i.tenant_id for i in planted_injections()} <= payload_tenants


def test_report_files_are_written_and_round_trip(report: SafetySuiteReport, out_dir: Path) -> None:
    data = json.loads((out_dir / JSON_FILE).read_text(encoding="utf-8"))
    assert SafetySuiteReport.model_validate(data) == report
    markdown = (out_dir / MARKDOWN_FILE).read_text(encoding="utf-8")
    assert "| Violations reaching the database | 0 |" in markdown
    assert all(f"`{r.id}`" in markdown for r in report.results)
    assert (out_dir / CHART_FILE).read_text(encoding="utf-8").lstrip().startswith("<?xml")


def test_the_console_summary_names_failing_cases(report: SafetySuiteReport) -> None:
    assert "PASS" in report.summary()
    assert "violations reaching the database: 0" in report.summary()

    first = report.results[0]
    broken = report.model_copy(
        update={
            "violations_at_db": 1,
            "results": [first.model_copy(update={"violation_at_db": True})],
        }
    )
    assert not broken.passed
    assert "FAIL" in broken.summary()
    assert f"failing cases: {first.id}" in broken.summary()


def write_cases(path: Path, cases: str) -> Path:
    path.write_text(
        "version: 1\ndefault_tenant: 2\ncategories:\n"
        "  c: {description: d, expect: reject, layers: [grammar]}\n"
        f"  k: {{description: d, expect: contain, layers: [scoping]}}\ncases:\n{cases}",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("cases", "message"),
    [
        ("  - {id: a, category: missing, sql: x}\n", "unknown category"),
        ("  - {id: a, category: c, sql: x}\n  - {id: a, category: c, sql: y}\n", "duplicate"),
        ("  - {id: a, category: c, sql: x, expand: {N: {text: a, times: 2}}}\n", "expand key"),
        ("  - {id: a, category: k, sql: x, layers: [grammar]}\n", "only scoping and executor"),
        ("  - {id: a, category: c, sql: x, expect_rows: [[1]]}\n", "expect_rows"),
    ],
)
def test_malformed_case_files_are_refused(tmp_path: Path, cases: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_cases(write_cases(tmp_path / "cases.yaml", cases))


def test_case_defaults_and_expansion(tmp_path: Path) -> None:
    path = write_cases(
        tmp_path / "cases.yaml",
        '  - {id: a, category: c, sql: "x{N}y", expand: {N: {text: ab, times: 3}}}\n'
        "  - {id: b, category: k, sql: z, tenant: 5, user: 9}\n",
    )
    first, second = load_cases(path)
    assert (first.sql, first.tenant, first.expect, first.layers) == (
        "xabababy",
        2,
        "reject",
        ("grammar",),
    )
    assert (second.tenant, second.user, second.expect) == (5, 9, "contain")


def test_the_committed_case_file_loads() -> None:
    cases = load_cases(CASES_PATH)
    assert len({c.id for c in cases}) == len(cases)
