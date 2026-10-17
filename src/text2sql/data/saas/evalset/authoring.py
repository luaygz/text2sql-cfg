"""Stage 2: SQL through the grammar-constrained tool, verified mechanically, repaired once.

Two authors share the same loop. The gold author writes over the full schema in BENCHMARK mode
with sentinel ids for the asking tenant and user (`gold.py` turns them into parameters and proves
the explicit filters). The few-shot author writes over the visible schema with the PRODUCTION
grammar, exactly as the pipeline would, and its SQL is checked through the real scoping layer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from text2sql.catalog.schema import DatabaseSchema
from text2sql.config import ReasoningEffort
from text2sql.data.saas.evalset.drafting import Draft
from text2sql.data.saas.evalset.gold import (
    TENANT_SENTINEL,
    USER_SENTINEL,
    GoldExecutor,
    GoldRejected,
    check_answer_result,
    prove_explicit_scope,
    row_set,
    substitute_sentinels,
)
from text2sql.data.saas.evalset.snapshot import seeded_rng
from text2sql.execution import QueryResult
from text2sql.grammar import SqlGrammar
from text2sql.llm import (
    CallMeta,
    GrammarCallFailed,
    LLMClient,
    Message,
    SqlToolCall,
    tool_output_item,
)
from text2sql.prompts import PromptTemplate, load_prompt
from text2sql.safety import (
    TENANT_PARAM,
    USER_PARAM,
    SafetyError,
    ScopeContext,
    ScopePolicy,
    apply_scope,
)

PROMPT_NAME: Final = "saas_gold_sql"
EXTRA_TENANTS: Final = 2
"""Tenant-bucket items run under the asking tenant plus up to this many others."""
UNREPAIRABLE: Final = frozenset({"same_across_tenants"})
"""Failures caused by the question, which a different query cannot fix."""


@dataclass(frozen=True, slots=True)
class Verified:
    sql: str
    """Gold: parameterised SQL. Few-shot: the production SQL as written (unscoped)."""
    results: tuple[tuple[int, QueryResult], ...]
    """(tenant_id, result) for every tenant the item runs under, the asking tenant first."""


@dataclass(frozen=True, slots=True)
class Attempt:
    """What authoring SQL for one draft produced; exactly one of the first three is set."""

    verified: Verified | None = None
    abstain_reason: str | None = None
    rejection: GoldRejected | None = None
    sql_text: str | None = None
    """The last SQL the model wrote, before substitution (for reports and the probe review)."""
    call: SqlToolCall | None = None
    """The last tool call, which a repair turn continues."""
    metas: tuple[CallMeta, ...] = ()
    repairs: int = 0


type Verifier = Callable[[str, Draft], Awaitable[Verified]]


class SqlAuthor:
    def __init__(
        self,
        llm: LLMClient,
        *,
        model: str,
        grammar: SqlGrammar,
        prompt: PromptTemplate,
        prefix: Message,
        request: Callable[[Draft], str],
        verify: Verifier,
        purpose: str,
    ) -> None:
        self._llm = llm
        self._model = model
        self._grammar = grammar
        self._prompt = prompt
        self._prefix = prefix
        self._request = request
        self._verify = verify
        self._purpose = purpose

    async def author(self, draft: Draft, *, effort: ReasoningEffort, repair: bool) -> Attempt:
        """One call; on a repairable verification failure (if `repair`) one repair turn."""
        attempt = await self._attempt(draft, (), effort, self._purpose)
        rejection = attempt.rejection
        if (
            repair
            and rejection is not None
            and attempt.call is not None
            and rejection.reason not in UNREPAIRABLE
        ):
            return await self.repair(draft, attempt, rejection.detail, effort=effort)
        return attempt

    async def repair(
        self, draft: Draft, previous: Attempt, problem: str, *, effort: ReasoningEffort
    ) -> Attempt:
        """Continue `previous`'s tool call with `problem` as the tool output."""
        if previous.call is None:
            raise ValueError("a repair needs a previous tool call")
        feedback = self._prompt.render("gold_repair", problem=problem)
        history = (*previous.call.history_items, tool_output_item(previous.call.call_id, feedback))
        attempt = await self._attempt(draft, history, effort, f"{self._purpose}.repair")
        return replace(attempt, metas=previous.metas + attempt.metas, repairs=previous.repairs + 1)

    async def _attempt(
        self,
        draft: Draft,
        history: Sequence[dict[str, Any]],
        effort: ReasoningEffort,
        purpose: str,
    ) -> Attempt:
        messages = [self._prefix, Message("user", self._request(draft))]
        try:
            call = await self._llm.sql_call(
                model=self._model,
                messages=messages,
                grammar=self._grammar,
                effort=effort,
                purpose=purpose,
                history=list(history),
            )
        except GrammarCallFailed as exc:
            return Attempt(rejection=GoldRejected("no_sql", str(exc)), metas=(exc.meta,))
        if call.output.kind == "abstain":
            return Attempt(abstain_reason=call.output.text, call=call, metas=(call.meta,))
        try:
            verified = await self._verify(call.output.text, draft)
        except GoldRejected as exc:
            return Attempt(rejection=exc, sql_text=call.output.text, call=call, metas=(call.meta,))
        return Attempt(verified=verified, sql_text=call.output.text, call=call, metas=(call.meta,))


def gold_author(
    llm: LLMClient,
    executor: GoldExecutor,
    policy: ScopePolicy,
    *,
    grammar: SqlGrammar,
    schema_text: str,
    model: str,
    tenant_ids: Sequence[int],
) -> SqlAuthor:
    """The author of gold SQL over the full schema (see the module docstring)."""
    prompt = load_prompt(PROMPT_NAME)
    tenant_tables = ", ".join(sorted(policy.tenant_tables))
    scoping_note = prompt.render(
        "scoping_note", tenant_tables=tenant_tables, tenant_sentinel=str(TENANT_SENTINEL)
    )
    prefix = Message(
        "developer",
        prompt.render(
            "gold_instructions",
            tenant_sentinel=str(TENANT_SENTINEL),
            user_sentinel=str(USER_SENTINEL),
            schema=schema_text,
            scoping_note=scoping_note,
        ),
        cache_breakpoint=True,
    )

    def request(draft: Draft) -> str:
        question = draft.gold_question or draft.question
        section = "gold_request_tenant" if draft.persona is None else "gold_request_user"
        return prompt.render(
            section,
            tenant_sentinel=str(TENANT_SENTINEL),
            user_sentinel=str(USER_SENTINEL),
            question=question,
        )

    async def verify(text: str, draft: Draft) -> Verified:
        user_id = None if draft.persona is None else draft.persona.user_id
        sql = substitute_sentinels(text, user_mode=user_id is not None)
        prove_explicit_scope(sql, policy, user_mode=user_id is not None)
        params = {TENANT_PARAM: draft.tenant_id}
        if user_id is not None:
            params[USER_PARAM] = user_id
        primary = await executor.run(sql, params)
        check_answer_result(primary)
        if draft.planted_text is not None and not _contains(primary, draft.planted_text):
            raise GoldRejected("planted_value_missing", "the planted value is not in the result")
        results = [(draft.tenant_id, primary)]
        if draft.bucket == "tenant":
            results += await _other_tenants(executor, sql, draft, tenant_ids, primary)
        return Verified(sql=sql, results=tuple(results))

    return SqlAuthor(
        llm,
        model=model,
        grammar=grammar,
        prompt=prompt,
        prefix=prefix,
        request=request,
        verify=verify,
        purpose="saas_evalset.gold",
    )


def fewshot_author(
    llm: LLMClient,
    executor: GoldExecutor,
    policy: ScopePolicy,
    *,
    full_schema: DatabaseSchema,
    grammar: SqlGrammar,
    tenant_grammar: SqlGrammar,
    schema_text: str,
    model: str,
) -> SqlAuthor:
    """The author of few-shot SQL: visible schema, production grammar, real scoping layer."""
    prompt = load_prompt(PROMPT_NAME)
    prefix = Message(
        "developer",
        prompt.render("fewshot_instructions", schema=schema_text),
        cache_breakpoint=True,
    )

    def request(draft: Draft) -> str:
        return prompt.render("fewshot_request", question=draft.question)

    async def verify(text: str, draft: Draft) -> Verified:
        if not tenant_grammar.accepts(text):
            raise GoldRejected("not_tenant_grammar", "the query must also parse in tenant mode")
        try:
            scoped = apply_scope(
                text,
                policy,
                ScopeContext(tenant_id=draft.tenant_id, user_id=None),
                schema=full_schema,
            )
        except SafetyError as exc:
            raise GoldRejected("scoping_failed", str(exc)) from exc
        result = await executor.run(scoped.sql, scoped.params)
        check_answer_result(result)
        return Verified(sql=text, results=((draft.tenant_id, result),))

    return SqlAuthor(
        llm,
        model=model,
        grammar=grammar,
        prompt=prompt,
        prefix=prefix,
        request=request,
        verify=verify,
        purpose="saas_evalset.fewshot_sql",
    )


async def _other_tenants(
    executor: GoldExecutor,
    sql: str,
    draft: Draft,
    tenant_ids: Sequence[int],
    primary: QueryResult,
) -> list[tuple[int, QueryResult]]:
    """Up to EXTRA_TENANTS other tenants (seeded order) whose results are usable and differ
    from every result kept so far."""
    others = [t for t in tenant_ids if t != draft.tenant_id]
    seeded_rng("eval_tenants", draft.key).shuffle(others)
    kept: list[tuple[int, QueryResult]] = []
    seen = [row_set(primary)]
    for tenant in others:
        result = await executor.run(sql, {TENANT_PARAM: tenant})
        try:
            check_answer_result(result)
        except GoldRejected:
            continue
        if row_set(result) in seen:
            continue
        kept.append((tenant, result))
        seen.append(row_set(result))
        if len(kept) == EXTRA_TENANTS:
            break
    if not kept:
        raise GoldRejected("same_across_tenants", "no other tenant gets a different answer")
    return kept


def _contains(result: QueryResult, value: str) -> bool:
    return any(cell == value for row in result.rows for cell in row)
