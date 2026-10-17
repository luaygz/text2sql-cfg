"""Per-database resources: loaded once, shared by every request against the database.

A `DatabaseResources` holds what does not depend on the question: the catalog, the full and
visible schemas, the rendered full schema, the full-schema grammar for the request mode, the
value and column indexes (loaded on first use) and the `QueryGuard`. The mode-dependent limits
live here too, so the grammar's LIMIT bound, the validator's row cap and the executor's row cap
always agree.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Literal, Self

from text2sql.catalog import Catalog, load_catalog, render_schema
from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.data.bird import bird_db_path
from text2sql.data.saas import DEFAULT_DB_PATH, load_saas_schema, saas_scope_policy
from text2sql.execution import ExecutionLimits
from text2sql.grammar import GrammarOptions, SqlGrammar, build_grammar
from text2sql.pipeline.events import CollectingEventLog
from text2sql.retrieval import ColumnIndex, ValueIndex
from text2sql.safety import ScopePolicy
from text2sql.safety.guard import QueryGuard
from text2sql.sqlite_clock import BENCHMARK_NOW

Dataset = Literal["bird", "saas"]

GUARD_WORKERS = 4
"""Executor worker processes per database; the default schedule runs five candidates at once."""


@dataclass(frozen=True, slots=True)
class ModeLimits:
    max_rows: int
    """LIMIT bound in the grammar and validator, and the executor's row cap."""
    timeout_s: float


MODE_LIMITS: Mapping[QueryMode, ModeLimits] = MappingProxyType(
    {
        # BIRD gold queries often omit LIMIT and some scan large tables; EX is scored separately
        # with BIRD's own 30 s evaluator, so this only bounds the candidates' cost.
        QueryMode.BENCHMARK: ModeLimits(max_rows=1000, timeout_s=10.0),
        # The SaaS tenant grammar was probed and accepted with max_rows 200 (ADR-005).
        QueryMode.PRODUCTION: ModeLimits(max_rows=200, timeout_s=2.0),
        QueryMode.TENANT: ModeLimits(max_rows=200, timeout_s=2.0),
    }
)


def grammar_options(mode: QueryMode) -> GrammarOptions:
    """Options of every grammar built for `mode`: abstention is allowed outside the benchmark."""
    return GrammarOptions(
        mode=mode,
        max_rows=MODE_LIMITS[mode].max_rows,
        allow_abstain=mode is not QueryMode.BENCHMARK,
    )


def execution_limits(mode: QueryMode, *, evaluation: bool = False) -> ExecutionLimits:
    """The executor limits for candidates in `mode`.

    Where a user is waiting (production and tenant requests), a slow query is a denial of
    service, so the time limit is wall-clock as well as a step budget. Benchmark candidates and
    every evaluation run are limited by step count alone, so a replay at another machine load
    reaches the same outcome; benchmark candidates also read a fixed "now", so a replay on
    another day does too (ADR-007).
    """
    limits = MODE_LIMITS[mode]
    benchmark = mode is QueryMode.BENCHMARK
    return ExecutionLimits(
        timeout_s=limits.timeout_s,
        max_rows=limits.max_rows,
        wall_clock=not (benchmark or evaluation),
        clock=BENCHMARK_NOW if benchmark else None,
    )


def database_schemas(
    db_id: str, *, dataset: Dataset, db_path: Path | None = None
) -> tuple[Catalog, DatabaseSchema, ScopePolicy | None]:
    """The catalog, the full schema (scoping columns included) and the scope policy.

    BIRD databases have no policy and their full schema is the catalog's. For the SaaS database
    the full schema comes from the database file, because the catalog leaves out the tenant
    column and the hidden columns that the scoping layer must still know about.
    """
    catalog = load_catalog(db_id)
    if dataset == "bird":
        return catalog, catalog.schema(), None
    return catalog, load_saas_schema(db_path or DEFAULT_DB_PATH), saas_scope_policy()


def full_grammar(
    db_id: str, *, dataset: Dataset, mode: QueryMode, db_path: Path | None = None
) -> SqlGrammar:
    """The full-schema grammar the pipeline uses for `db_id` in `mode`, without loading the
    value index or starting the guard's workers."""
    _, full, policy = database_schemas(db_id, dataset=dataset, db_path=db_path)
    visible = policy.visible_schema(full) if policy is not None else full
    return build_grammar(visible, grammar_options(mode))


class DatabaseResources:
    """Everything question-independent about one database in one mode. Close it when done."""

    def __init__(
        self,
        *,
        db_id: str,
        dataset: Dataset,
        mode: QueryMode,
        db_path: Path,
        catalog: Catalog,
        full_schema: DatabaseSchema,
        policy: ScopePolicy | None,
        event_log: CollectingEventLog,
        value_index: ValueIndex | None = None,
        column_index: ColumnIndex | None = None,
        evaluation: bool = False,
    ) -> None:
        """`evaluation` marks an evaluation run, where no user is waiting: candidates are then
        limited by step count alone in every mode (`execution_limits`)."""
        if dataset == "bird" and mode is QueryMode.TENANT:
            raise ValueError("BIRD databases have no tenants; use benchmark or production mode")
        if dataset == "saas" and mode is not QueryMode.TENANT:
            # Without scoping, every tenant's rows would be readable.
            raise ValueError("the SaaS database is only served in tenant mode")
        self.db_id = db_id
        self.dataset: Dataset = dataset
        self.mode = mode
        self.db_path = db_path
        self.catalog = catalog
        self.full_schema = full_schema
        self.policy = policy
        self.visible_schema = policy.visible_schema(full_schema) if policy else full_schema
        self.limits = MODE_LIMITS[mode]
        self.options = grammar_options(mode)
        self.full_grammar = build_grammar(self.visible_schema, self.options)
        self.full_schema_text = render_schema(catalog, subset=self.visible_schema)
        self.event_log = event_log
        self.guard = QueryGuard(
            db_path=db_path,
            full_schema=full_schema,
            mode=mode,
            policy=policy,
            limits=execution_limits(mode, evaluation=evaluation),
            max_rows=self.limits.max_rows,
            event_log=event_log,
            max_workers=GUARD_WORKERS,
        )
        self._value_index = value_index
        self._column_index = column_index
        self._index_lock = threading.Lock()

    @classmethod
    def load(
        cls,
        db_id: str,
        *,
        dataset: Dataset,
        mode: QueryMode,
        db_path: Path | None = None,
        events_path: Path | None = None,
        evaluation: bool = False,
    ) -> DatabaseResources:
        """Load the catalog and build the grammar and guard. `db_path` defaults to the Mini-Dev
        release for BIRD and data/saas/crm.sqlite for SaaS, `events_path` to the default safety
        event log. SaaS is served only in tenant mode, BIRD in benchmark or production mode.
        `evaluation` is set by the eval runner (see `__init__`)."""
        path = db_path or (bird_db_path(db_id) if dataset == "bird" else DEFAULT_DB_PATH)
        catalog, full, policy = database_schemas(db_id, dataset=dataset, db_path=path)
        return cls(
            db_id=db_id,
            dataset=dataset,
            mode=mode,
            db_path=path,
            catalog=catalog,
            full_schema=full,
            policy=policy,
            event_log=CollectingEventLog(events_path),
            evaluation=evaluation,
        )

    def value_index(self) -> ValueIndex:
        """The value index, loaded on first use (FileNotFoundError names the build command)."""
        with self._index_lock:
            if self._value_index is None:
                self._value_index = ValueIndex.load(self.db_id)
            return self._value_index

    def column_index(self) -> ColumnIndex:
        """The column-embedding index schema linking shortlists from, loaded on first use."""
        with self._index_lock:
            if self._column_index is None:
                self._column_index = ColumnIndex.load(self.db_id)
            return self._column_index

    def close(self) -> None:
        self.guard.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
