"""The four safety layers composed into one gate for model-produced SQL (docs/adr/015).

Order of a request:

    1. grammar    re-parse the tool input with the request's Lark grammar
    2. validator  sqlglot AST validation against the request's allowlist
    4. scoping    tenant (and user) guards spliced in and proven (tenant mode only)
    3. executor   read-only SQLite behind an authorizer, a deadline and size limits

Scoping runs before execution because it produces the SQL that is executed. Every layer assumes
the ones before it failed, so each is configured from the guard's own inputs, never from what an
earlier layer let through.

A rejection at any layer is written to the safety event log with the request context, then raised
as `GuardRejection`; nothing is repaired here. Ordinary SQLite errors (`QueryFailed`) and timeouts
(`QueryTimeout`) propagate unchanged because the repair loop feeds them back to the model, but a
timeout or an oversized value or result (`ResultTooLarge`) is also logged: each is layer 3
stopping a query that tried to use more than its share of the machine.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Final, Self

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import QueryMode
from text2sql.execution import (
    AccessDenied,
    AccessPolicy,
    ExecutionError,
    ExecutionLimits,
    QueryResult,
    QueryTimeout,
    ResultTooLarge,
    SandboxedExecutor,
)
from text2sql.grammar import GrammarRejection, SqlGrammar
from text2sql.safety.errors import Layer, SafetyError
from text2sql.safety.events import SafetyEvent, SafetyEventLog
from text2sql.safety.parsing import fold
from text2sql.safety.policy import ScopeContext, ScopePolicy
from text2sql.safety.scoping import apply_scope
from text2sql.safety.validator import ValidationConfig, validate_sql

GRAMMAR_RULE: Final = "not_in_grammar"
TIMEOUT_RULE: Final = "timeout"
TOO_LARGE_RULE: Final = "too_large"
MAX_DETAIL_CHARS: Final = 500
"""Lark lists every expected terminal in its error, which for a large schema runs to pages."""

_NO_CONTEXT: Final[Mapping[str, str]] = MappingProxyType({})


class GuardRejection(Exception):  # noqa: N818 - name fixed by the shared interface contract
    """A layer refused the query. Raised after the matching `SafetyEvent` was logged."""

    def __init__(self, layer: Layer, rule: str, detail: str) -> None:
        super().__init__(f"{layer} rejected the query [{rule}]: {detail}")
        self.layer: Layer = layer
        self.rule = rule
        self.detail = detail


@dataclass(frozen=True, slots=True)
class GuardResult:
    sql: str
    """The query as the model wrote it and layers 1 and 2 checked it."""
    executed_sql: str
    """What layer 3 ran: `sql` with tenant guards spliced in (`sql` itself outside tenant mode)."""
    params: Mapping[str, int]
    """Bound identity parameters, taken from `ScopeContext` only."""
    result: QueryResult


def limit_rule(error: ExecutionError) -> str | None:
    """The safety rule when `error` is layer 3 enforcing a resource limit, else None."""
    if isinstance(error, QueryTimeout):
        return TIMEOUT_RULE
    if isinstance(error, ResultTooLarge):
        return TOO_LARGE_RULE
    return None


def access_policy(
    full_schema: DatabaseSchema, *, mode: QueryMode, policy: ScopePolicy | None
) -> AccessPolicy:
    """Layer 3's allowlist for every request a guard serves.

    Without a scope policy (BIRD) every user table and column is readable. With one, the readable
    columns are the visible schema, plus the tenant column in tenant mode because the injected
    guards filter on it. Hidden columns stay unreadable either way.
    """
    if policy is None:
        return AccessPolicy()
    if mode is QueryMode.TENANT:
        return AccessPolicy(readable=policy.readable_columns(full_schema))
    visible = policy.visible_schema(full_schema)
    return AccessPolicy(
        readable={fold(t.name): frozenset(fold(c.name) for c in t.columns) for t in visible.tables}
    )


class QueryGuard:
    """Checks and runs model-produced SQL for one database; safe to share between tasks."""

    def __init__(
        self,
        *,
        db_path: Path,
        full_schema: DatabaseSchema,
        mode: QueryMode,
        policy: ScopePolicy | None,
        limits: ExecutionLimits,
        max_rows: int,
        event_log: SafetyEventLog,
        max_workers: int = 2,
    ) -> None:
        if mode is QueryMode.TENANT and policy is None:
            raise ValueError("tenant mode needs a ScopePolicy")
        self.mode = mode
        self.policy = policy
        self.full_schema = full_schema
        self.visible_schema = policy.visible_schema(full_schema) if policy else full_schema
        self.validation = ValidationConfig(mode=mode, max_rows=max_rows, scope=policy)
        self.access = access_policy(full_schema, mode=mode, policy=policy)
        self._scoping = policy if mode is QueryMode.TENANT else None
        self._event_log = event_log
        self._executor = SandboxedExecutor(
            db_path, limits=limits, access=self.access, max_workers=max_workers
        )

    async def run(
        self,
        text: str,
        *,
        grammar: SqlGrammar | None,
        allowed: DatabaseSchema | None = None,
        scope: ScopeContext | None = None,
        context: Mapping[str, str] = _NO_CONTEXT,
    ) -> GuardResult:
        """Pass `text` through layers 1, 2, 4 and 3; return the executed result.

        `grammar` is the grammar the text was generated under; None only in the grammar-off
        ablation. `allowed` is the request's allowlist (default: the visible schema), `scope` the
        authenticated caller (required in tenant mode, refused otherwise), `context` request
        metadata copied into every safety event (question id, strategy, candidate index).

        Raises `GuardRejection` (logged) when a layer refuses the query, and `QueryFailed` or
        `QueryTimeout` from the executor.
        """
        if self._scoping is not None and scope is None:
            raise ValueError("tenant mode needs the caller's ScopeContext")
        if self._scoping is None and scope is not None:
            raise ValueError(f"{self.mode.value} mode does not scope queries")
        if grammar is not None and grammar.options.mode is not self.mode:
            raise ValueError(f"a {grammar.options.mode.value} grammar cannot guard this mode")
        events = self._event_context(context, grammar, scope)
        executed_sql, params = self._check(text, grammar, allowed, scope, events)
        result = await self._execute(executed_sql, params, events)
        return GuardResult(sql=text, executed_sql=executed_sql, params=params, result=result)

    def _check(
        self,
        text: str,
        grammar: SqlGrammar | None,
        allowed: DatabaseSchema | None,
        scope: ScopeContext | None,
        events: dict[str, str],
    ) -> tuple[str, dict[str, int]]:
        """Layers 1, 2 and 4: the SQL to execute and its bound parameters."""
        if grammar is not None:
            try:
                output = grammar.parse(text)
            except GrammarRejection as exc:
                raise self._reject("grammar", GRAMMAR_RULE, str(exc), text, events) from exc
            if output.kind == "abstain":
                raise ValueError("an abstention is answered by the pipeline, never executed")
        try:
            validate_sql(text, self.visible_schema if allowed is None else allowed, self.validation)
            if self._scoping is None or scope is None:
                return text, {}
            scoped = apply_scope(text, self._scoping, scope, schema=self.full_schema)
        except SafetyError as exc:
            raise self._reject(exc.layer, exc.rule, exc.detail, text, events) from exc
        return scoped.sql, scoped.params

    async def _execute(
        self, sql: str, params: dict[str, int], events: dict[str, str]
    ) -> QueryResult:
        """Layer 3."""
        try:
            return await self._executor.execute_async(sql, params)
        except AccessDenied as exc:
            raise self._reject(
                "executor", f"denied_{exc.action.lower()}", str(exc), sql, events
            ) from exc
        except ExecutionError as exc:
            rule = limit_rule(exc)
            if rule is not None:
                self._record("executor", rule, str(exc), sql, events)
            raise

    def close(self) -> None:
        self._executor.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _event_context(
        self, context: Mapping[str, str], grammar: SqlGrammar | None, scope: ScopeContext | None
    ) -> dict[str, str]:
        events = dict(context)
        events["mode"] = self.mode.value
        events["grammar"] = grammar.fingerprint[:12] if grammar is not None else "off"
        if scope is not None:
            events["tenant_id"] = str(scope.tenant_id)
            if scope.user_id is not None:
                events["user_id"] = str(scope.user_id)
        return events

    def _record(
        self, layer: Layer, rule: str, detail: str, sql: str, context: dict[str, str]
    ) -> None:
        self._event_log.record(
            SafetyEvent(layer, rule, detail[:MAX_DETAIL_CHARS], sql=sql, context=context)
        )

    def _reject(
        self, layer: Layer, rule: str, detail: str, sql: str, context: dict[str, str]
    ) -> GuardRejection:
        self._record(layer, rule, detail, sql, context)
        return GuardRejection(layer, rule, detail[:MAX_DETAIL_CHARS])
