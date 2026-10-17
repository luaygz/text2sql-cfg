"""Run every adversarial case through the full guard and through each layer alone.

Full guard: `QueryGuard` in tenant mode over the SaaS database, exactly as the pipeline uses it.

Each layer alone, with the layers before it switched off:

- grammar:   the tenant-mode grammar parses the raw SQL.
- validator: `validate_sql` checks the raw SQL against the visible schema.
- scoping:   `apply_scope` rewrites the raw SQL, and the result runs on a permissive executor
             (every table, column and function except load_extension, recursion allowed) so
             that anything scoping lets through shows up as a leak. That executor still refuses
             writes and PRAGMAs, which layer 4 is not responsible for; such a refusal is
             recorded as `passed`, never as a layer 4 stop.
- executor:  the raw SQL runs with the guard's access policy and no scoping parameters.

The database is opened read-only by every executor; its checksum is compared before and after.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import tempfile
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from text2sql.catalog.schema import DatabaseSchema, introspect_sqlite
from text2sql.config import QueryMode
from text2sql.data.saas import saas_scope_policy
from text2sql.data.saas.generate import file_sha256, generate_database
from text2sql.evals.report import current_git_sha
from text2sql.evals.safety_suite.cases import CASES_PATH, SafetyCase, load_cases
from text2sql.evals.safety_suite.render import REPORT_DIR, write_safety_report
from text2sql.evals.safety_suite.results import (
    SQLITE_ERROR_RULE,
    CaseResult,
    GuardOutcome,
    LayerOutcome,
    SafetySuiteReport,
    build_report,
)
from text2sql.execution import (
    AccessDenied,
    AccessPolicy,
    ExecutionError,
    ExecutionLimits,
    QueryResult,
    SandboxedExecutor,
)
from text2sql.grammar import GrammarOptions, GrammarRejection, SqlGrammar, build_grammar
from text2sql.safety import (
    GuardRejection,
    Layer,
    QueryGuard,
    SafetyEventLog,
    ScopeContext,
    ScopePolicy,
    ScopeViolation,
    ValidationConfig,
    ValidationError,
    apply_scope,
    validate_sql,
)
from text2sql.safety.guard import limit_rule
from text2sql.safety.leaks import Execution, LeakDetector

SUITE_LIMITS: Final = ExecutionLimits(timeout_s=1.0)
"""A shorter deadline than production's 2 s: the timeout cases only need to show it fires."""
MAX_ROWS: Final = 1000
CONCURRENCY: Final = 4
MAX_DETAIL_CHARS: Final = 200


def run_safety_suite(
    *,
    db_path: Path | None = None,
    cases_path: Path = CASES_PATH,
    out_dir: Path | None = REPORT_DIR,
    limits: ExecutionLimits = SUITE_LIMITS,
) -> SafetySuiteReport:
    """Run the suite and, when `out_dir` is set, write JSON, Markdown and the SVG chart there.

    `db_path` None generates the deterministic SaaS database into a temporary directory, so the
    suite needs neither `make data` nor network access.
    """
    cases = load_cases(cases_path)
    with tempfile.TemporaryDirectory(prefix="t2sql-safety-") as scratch:
        db = db_path if db_path is not None else _fresh_database(Path(scratch))
        before = file_sha256(db)
        events = SafetyEventLog(Path(scratch) / "safety_events.jsonl")
        with _quiet_sqlglot():
            results = asyncio.run(_run_cases(db, cases, limits, events))
        report = build_report(
            _with_event_checks(results, events),
            created_at=datetime.now(UTC),
            git_sha=current_git_sha(),
            db_sha256=before,
            cases_sha256=file_sha256(cases_path),
            db_unchanged=file_sha256(db) == before,
        )
    if out_dir is not None:
        write_safety_report(report, out_dir)
    return report


@contextmanager
def _quiet_sqlglot() -> Iterator[None]:
    # sqlglot warns on every DDL/PRAGMA it parses as an opaque command; the suite runs dozens on
    # purpose and records how each layer handled them.
    logger = logging.getLogger("sqlglot")
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous)


@dataclass(frozen=True, slots=True)
class _Harness:
    policy: ScopePolicy
    full: DatabaseSchema
    visible: DatabaseSchema
    grammar: SqlGrammar
    validation: ValidationConfig
    guard: QueryGuard
    layer3: SandboxedExecutor
    permissive: SandboxedExecutor
    detector: LeakDetector


async def _run_cases(
    db: Path, cases: Sequence[SafetyCase], limits: ExecutionLimits, events: SafetyEventLog
) -> list[CaseResult]:
    policy = saas_scope_policy()
    full = introspect_sqlite(db)
    visible = policy.visible_schema(full)
    guard = QueryGuard(
        db_path=db,
        full_schema=full,
        mode=QueryMode.TENANT,
        policy=policy,
        limits=limits,
        max_rows=MAX_ROWS,
        event_log=events,
        max_workers=CONCURRENCY,
    )
    layer3 = SandboxedExecutor(db, limits=limits, access=guard.access, max_workers=CONCURRENCY)
    permissive = SandboxedExecutor(
        db,
        limits=limits,
        access=AccessPolicy(functions=_every_function_but_load_extension(), allow_recursive=True),
        max_workers=CONCURRENCY,
    )
    with guard, layer3, permissive:
        harness = _Harness(
            policy=policy,
            full=full,
            visible=visible,
            grammar=build_grammar(visible, GrammarOptions(QueryMode.TENANT, max_rows=MAX_ROWS)),
            validation=guard.validation,
            guard=guard,
            layer3=layer3,
            permissive=permissive,
            detector=LeakDetector.from_database(db, policy),
        )
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(case: SafetyCase) -> CaseResult:
            async with gate:
                return await _run_case(harness, case)

        return list(await asyncio.gather(*(one(case) for case in cases)))


async def _run_case(h: _Harness, case: SafetyCase) -> CaseResult:
    scope = ScopeContext(case.tenant, case.user)
    guard = await _through_guard(h, case, scope)
    isolation: dict[Layer, LayerOutcome] = {
        "grammar": _grammar_alone(h, case),
        "validator": _validator_alone(h, case),
        "scoping": await _scoping_alone(h, case, scope),
        "executor": await _executor_alone(h, case, scope),
    }
    must_stop = case.expect != "contain"
    held = {"stopped"} if must_stop else {"stopped", "executed"}
    return CaseResult(
        id=case.id,
        category=case.category,
        expect=case.expect,
        layers=case.layers,
        sql=case.sql,
        tenant=case.tenant,
        user=case.user,
        guard=guard,
        isolation=isolation,
        violation_at_executor=case.expect == "reject" and guard.reached_executor,
        violation_at_db=guard.executed and (bool(guard.leaks) or must_stop),
        isolation_failures=[layer for layer in case.layers if isolation[layer].outcome not in held],
        unlogged_stop=False,
    )


async def _through_guard(h: _Harness, case: SafetyCase, scope: ScopeContext) -> GuardOutcome:
    try:
        done = await h.guard.run(
            case.sql, grammar=h.grammar, scope=scope, context={"case": case.id}
        )
    except GuardRejection as exc:
        return _guard_stop(exc.layer, exc.rule, exc.detail, reached=exc.layer == "executor")
    except ExecutionError as exc:
        rule = limit_rule(exc) or SQLITE_ERROR_RULE
        return _guard_stop("executor", rule, str(exc), reached=True)
    return GuardOutcome(
        stopped_at=None,
        rule=None,
        detail=_rows_detail(done.result),
        reached_executor=True,
        executed=True,
        leaks=_leaks(h, case, scope, done.executed_sql, done.result),
        events=0,
    )


def _guard_stop(layer: Layer, rule: str, detail: str, *, reached: bool) -> GuardOutcome:
    return GuardOutcome(
        stopped_at=layer,
        rule=rule,
        detail=_short(detail),
        reached_executor=reached,
        executed=False,
        leaks=[],
        events=0,
    )


def _grammar_alone(h: _Harness, case: SafetyCase) -> LayerOutcome:
    try:
        h.grammar.parse(case.sql)
    except GrammarRejection as exc:
        return LayerOutcome(outcome="stopped", detail=_short(str(exc)))
    return LayerOutcome(outcome="passed", detail="parses")


def _validator_alone(h: _Harness, case: SafetyCase) -> LayerOutcome:
    try:
        validate_sql(case.sql, h.visible, h.validation)
    except ValidationError as exc:
        return LayerOutcome(outcome="stopped", detail=_short(f"{exc.rule}: {exc.detail}"))
    return LayerOutcome(outcome="passed", detail="valid")


async def _scoping_alone(h: _Harness, case: SafetyCase, scope: ScopeContext) -> LayerOutcome:
    try:
        scoped = apply_scope(case.sql, h.policy, scope, schema=h.full)
    except ScopeViolation as exc:
        return LayerOutcome(outcome="stopped", detail=_short(f"{exc.rule}: {exc.detail}"))
    try:
        result = await h.permissive.execute_async(scoped.sql, scoped.params)
    except ExecutionError as exc:
        if isinstance(exc, AccessDenied) or limit_rule(exc) is not None:
            return LayerOutcome(outcome="passed", detail=_short(f"permissive executor: {exc}"))
        return LayerOutcome(outcome="stopped", detail=_short(f"rewritten query failed: {exc}"))
    return _executed(h, case, scope, scoped.sql, result)


async def _executor_alone(h: _Harness, case: SafetyCase, scope: ScopeContext) -> LayerOutcome:
    try:
        result = await h.layer3.execute_async(case.sql)
    except ExecutionError as exc:
        return LayerOutcome(outcome="stopped", detail=_short(f"{type(exc).__name__}: {exc}"))
    return _executed(h, case, scope, case.sql, result)


def _executed(
    h: _Harness, case: SafetyCase, scope: ScopeContext, sql: str, result: QueryResult
) -> LayerOutcome:
    leaks = _leaks(h, case, scope, sql, result)
    if leaks:
        return LayerOutcome(outcome="leaked", detail=_short("; ".join(leaks[:3])))
    return LayerOutcome(outcome="executed", detail=_rows_detail(result))


def _leaks(
    h: _Harness, case: SafetyCase, scope: ScopeContext, sql: str, result: QueryResult
) -> list[str]:
    leaks = h.detector.leaks(Execution(sql, result.rows), scope)
    if case.expect_rows is not None:
        rows = [list(row) for row in result.rows]
        if rows != case.expect_rows:
            leaks.append(f"result {rows[:3]} is not the caller's own {case.expect_rows}")
    return leaks


def _with_event_checks(results: list[CaseResult], log: SafetyEventLog) -> list[CaseResult]:
    """Attach the logged events to each case and flag stops that were not logged exactly once."""
    logged: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for event in log.read():
        logged[event.context.get("case", "")].append((event.layer, event.rule))
    checked: list[CaseResult] = []
    for r in results:
        events = logged.get(r.id, [])
        logs_expected = r.guard.stopped_at is not None and r.guard.rule != SQLITE_ERROR_RULE
        expected = [(r.guard.stopped_at, r.guard.rule)] if logs_expected else []
        guard = r.guard.model_copy(update={"events": len(events)})
        checked.append(r.model_copy(update={"guard": guard, "unlogged_stop": events != expected}))
    return checked


def _every_function_but_load_extension() -> frozenset[str]:
    con = sqlite3.connect(":memory:")
    try:
        names = {
            str(name).lower() for (name,) in con.execute("SELECT name FROM pragma_function_list")
        }
    finally:
        con.close()
    return frozenset(names - {"load_extension"})


def _fresh_database(directory: Path) -> Path:
    path = directory / "crm.sqlite"
    generate_database(path)
    return path


def _rows_detail(result: QueryResult) -> str:
    return f"{len(result.rows)} rows{' (truncated)' if result.truncated else ''}"


def _short(text: str) -> str:
    first = text.strip().split("\n", 1)[0]
    return first if len(first) <= MAX_DETAIL_CHARS else first[: MAX_DETAIL_CHARS - 3] + "..."
