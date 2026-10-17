"""Draft, verify, review and select the SaaS evaluation set and few-shot pool.

Stages per candidate: question (generator model, structured output) -> SQL through the grammar
tool (generator model) -> mechanical checks (sentinels, explicit scope, execution, tenant
difference), one repair turn on failure -> review (small model, structured verdict), one repair
turn when the reviewer finds the SQL wrong -> seeded selection to the bucket quotas -> seeded
70/30 split. Every model call goes through `LLMClient`, so a second run replays the response
cache and writes byte-identical files without spending anything.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel

from text2sql.catalog import load_catalog, render_schema
from text2sql.config import QueryMode, ReasoningEffort, Settings, get_settings
from text2sql.data.saas import (
    DEFAULT_DB_PATH,
    SAAS_DB_ID,
    SAAS_SEED,
    load_saas_schema,
    planted_injections,
    saas_scope_policy,
)
from text2sql.data.saas.evalset.authoring import PROMPT_NAME as GOLD_PROMPT
from text2sql.data.saas.evalset.authoring import (
    Attempt,
    SqlAuthor,
    fewshot_author,
    gold_author,
)
from text2sql.data.saas.evalset.drafting import (
    UNICODE_TRICKS,
    Draft,
    DraftedBatch,
    QuestionDrafter,
    planted_drafts,
)
from text2sql.data.saas.evalset.gold import GoldExecutor, authoring_grammar, authoring_schema
from text2sql.data.saas.evalset.models import (
    EVAL_PATH,
    EXPECTED_BY_BUCKET,
    FEWSHOT_PATH,
    Difficulty,
    FewShotItem,
    Provenance,
    SaasEvalItem,
    Split,
    write_jsonl,
)
from text2sql.data.saas.evalset.plan import QUOTAS, TENANT_IDS, Batch, drafting_plan
from text2sql.data.saas.evalset.review import AttackVerdict, Reviewer, Verdict
from text2sql.data.saas.evalset.snapshot import Snapshots, seeded_rng
from text2sql.grammar import GrammarOptions, build_grammar
from text2sql.llm import CallMeta, LLMClient, RunBudget, SpendLedger
from text2sql.observability import current_run_id
from text2sql.prompts import load_prompt

PHASE: Final = "saas-evalset"
PHASE_CAP_USD: Final = 3.00
"""Spend cap of this phase across all runs, read back from the spend ledger."""
DRAFT_MODEL: Final = "gpt-6.1-sol"
REVIEW_MODEL: Final = "gpt-6-luna"
QUESTION_EFFORT: Final[ReasoningEffort] = "low"
REVIEW_EFFORT: Final[ReasoningEffort] = "medium"
MAX_OUTPUT_TOKENS: Final = 16_000
"""Part of every request, hence of every cache key: pinned so replays hit the cache."""
MAX_CONCURRENCY: Final = 12
"""Concurrent API calls (not part of any request). Each reserves its worst-case cost, so with
the 16k output cap about $1 of the phase budget is held while the build runs."""
FEWSHOT_MAX_ROWS: Final = 200
TEST_SHARE: Final = 0.3
DUPLICATE_JACCARD: Final = 0.75
"""Word-set similarity at which two eval questions count as the same question."""
FEWSHOT_OVERLAP_JACCARD: Final = 0.6
"""Stricter bound between the few-shot pool and the eval set: the pool must not leak items."""
REPORT_PATH: Final = EVAL_PATH.with_name("evalset_build.json")
SCHEMA_SNAPSHOT_PATH: Final = EVAL_PATH.with_name("evalset_schema_snapshot.txt")
"""The rendered catalog every drafting, gold and review prompt was built from. It is frozen
because the catalog text is part of every request: an edited column note would otherwise turn
the whole replay into cache misses. `write_schema_snapshot` refreshes it, which re-drafts."""

Stage = Literal["drafting", "sql", "review"]


@dataclass(frozen=True, slots=True)
class Outcome:
    draft: Draft
    accepted: bool
    stage: Stage | None = None
    """Where a rejected candidate was dropped."""
    reason: str | None = None
    difficulty: Difficulty | None = None
    """Final label (the reviewer's when it disagreed)."""
    attempt: Attempt | None = None
    first_review_passed: bool | None = None
    review_fixed: bool = False
    relabelled: bool = False
    review_notes: str = ""
    gold_note: str | None = None
    """Adversarial items: why the legitimate part has no gold, if it has none."""
    probe_abstained: bool | None = None
    metas: tuple[CallMeta, ...] = ()


class Rejection(BaseModel):
    key: str
    bucket: str
    stage: Stage
    reason: str
    question: str
    notes: str
    """The reviewer's problems, for rejections at review."""


class BucketStats(BaseModel):
    drafted: int = 0
    dropped_drafting: int = 0
    sql_failed: dict[str, int] = {}
    reviewed: int = 0
    review_passed_first: int = 0
    review_passed_after_fix: int = 0
    review_failed: int = 0
    relabelled: int = 0
    sql_repaired: int = 0
    accepted: int = 0
    selected: int = 0


class BuildReport(BaseModel):
    seed: int
    draft_model: str
    review_model: str
    prompts: list[str]
    gold_grammar_fingerprint: str
    """sha256 of the BENCHMARK-mode, full-schema grammar every gold query was written under."""
    fewshot_grammar_fingerprint: str
    """sha256 of the PRODUCTION-mode, visible-schema grammar of the few-shot SQL."""
    buckets: dict[str, BucketStats]
    difficulty: dict[str, dict[str, int]]
    splits: dict[str, dict[str, int]]
    attacks: dict[str, int]
    user_mode_items: int
    tenant_eval_tenants: dict[str, int]
    """How many tenant-bucket items run under 2 and under 3 tenants."""
    unanswerable_probe_abstained: int
    unanswerable_probe_wrote_sql: int
    calls: int
    priced_usd: float
    """List price of every response used, cached or not (identical on replay)."""
    rejections: list[Rejection]


@dataclass(slots=True)
class _Stages:
    drafter: QuestionDrafter
    gold: SqlAuthor
    fewshot: SqlAuthor
    reviewer: Reviewer
    prompts: set[str] = field(default_factory=set)

    async def process(self, draft: Draft) -> Outcome:
        if draft.bucket in ("answerable", "tenant"):
            return await self._answer(draft, self.gold, production=False)
        if draft.bucket == "fewshot":
            return await self._answer(draft, self.fewshot, production=True)
        if draft.bucket == "unanswerable":
            return await self._unanswerable(draft)
        return await self._adversarial(draft)

    async def _answer(self, draft: Draft, author: SqlAuthor, *, production: bool) -> Outcome:
        attempt = await author.author(draft, effort=_sql_effort(draft), repair=True)
        if attempt.verified is None:
            reason = "drafter_abstained" if attempt.abstain_reason else _rejection(attempt)
            return Outcome(draft, False, "sql", reason, attempt=attempt, metas=attempt.metas)
        review = await self.reviewer.gold(
            draft,
            sql=attempt.verified.sql,
            results=attempt.verified.results,
            production=production,
        )
        metas = (*attempt.metas, review.meta)
        verdict, first = review.value, review.value.passed
        if not first and verdict.question_unambiguous:
            fixed = await author.repair(
                draft,
                attempt,
                f"A reviewer found these problems: {verdict.problems}",
                effort=_sql_effort(draft),
            )
            metas += fixed.metas[len(attempt.metas) :]
            if fixed.verified is not None:
                second = await self.reviewer.gold(
                    draft,
                    sql=fixed.verified.sql,
                    results=fixed.verified.results,
                    production=production,
                    sample=1,
                )
                metas += (second.meta,)
                if second.value.passed:
                    attempt, verdict = fixed, second.value
        if not verdict.passed:
            return Outcome(
                draft,
                False,
                "review",
                _review_reason(verdict),
                attempt=attempt,
                first_review_passed=first,
                review_notes=verdict.problems,
                metas=metas,
            )
        return _accepted(draft, verdict, attempt=attempt, first=first, metas=metas)

    async def _unanswerable(self, draft: Draft) -> Outcome:
        probe = await self.gold.author(draft, effort="low", repair=False)
        if probe.abstain_reason is not None:
            probe_text = f"ABSTAIN: {probe.abstain_reason}"
        elif probe.sql_text is not None:
            ran = (
                f"it ran and returned {len(probe.verified.results[0][1].rows)} rows"
                if probe.verified is not None
                else f"it failed the checks ({_rejection(probe)})"
            )
            probe_text = f"SQL: {probe.sql_text} ({ran})"
        else:
            probe_text = f"no output ({_rejection(probe)})"
        review = await self.reviewer.unanswerable(draft, probe=probe_text)
        metas = (*probe.metas, review.meta)
        abstained = probe.abstain_reason is not None
        if not review.value.passed:
            return Outcome(
                draft,
                False,
                "review",
                _review_reason(review.value),
                first_review_passed=False,
                review_notes=review.value.problems,
                probe_abstained=abstained,
                metas=metas,
            )
        out = _accepted(draft, review.value, attempt=None, first=True, metas=metas)
        return replace(out, probe_abstained=abstained)

    async def _adversarial(self, draft: Draft) -> Outcome:
        """Attack review first, then gold for the legitimate part, if any. The item's difficulty
        is how hard the attack is to spot, so only the attack review relabels it. A planted item
        has no attack in its text: its gold, which must return the planted value, is the item."""
        if draft.planted_text is not None:
            return await self._answer(draft, self.gold, production=False)
        review = await self.reviewer.attack(draft)
        verdict = review.value
        if not verdict.passed and not _only_legit_part_failed(verdict):
            return Outcome(
                draft,
                False,
                "review",
                _review_reason(verdict),
                first_review_passed=False,
                review_notes=verdict.problems,
                metas=(review.meta,),
            )
        attack = _accepted(draft, verdict, attempt=None, first=verdict.passed, metas=(review.meta,))
        if not verdict.passed:
            # The attack is sound but its "legitimate part" was not: keep it as a pure refusal.
            note = f"legitimate part removed after review: {verdict.problems}"
            return replace(attack, review_notes="", gold_note=note)
        if draft.gold_question is None:
            return attack
        legit = await self._answer(draft, self.gold, production=False)
        metas = attack.metas + legit.metas
        if not legit.accepted:
            note = f"legitimate part dropped at {legit.stage}: {legit.reason}"
            return replace(attack, metas=metas, gold_note=note)
        notes = attack.review_notes
        if legit.review_fixed:
            notes = "; ".join(n for n in (notes, f"legitimate part: {legit.review_notes}") if n)
        return replace(
            attack,
            attempt=legit.attempt,
            metas=metas,
            review_fixed=legit.review_fixed,
            review_notes=notes,
        )


async def build_evalset(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    offline: bool = False,
    only_batches: Sequence[str] | None = None,
) -> tuple[BuildReport, list[SaasEvalItem], list[FewShotItem], str]:
    """Run every stage; returns the report, the items, the pool and a spend summary.
    `only_batches` restricts drafting to those plan keys (for a pilot; no planted items)."""
    settings = _settings(offline)
    full = load_saas_schema(db_path)
    policy = saas_scope_policy()
    schema_text = read_schema_snapshot()
    gold_schema = authoring_schema(full, policy)
    visible = policy.visible_schema(full)
    gold_grammar = authoring_grammar(gold_schema)
    fewshot_grammar = build_grammar(visible, GrammarOptions(QueryMode.PRODUCTION, FEWSHOT_MAX_ROWS))
    plan = [b for b in drafting_plan() if only_batches is None or b.key in only_batches]
    eval_plan = [b for b in plan if b.bucket != "fewshot"]
    pool_plan = [b for b in plan if b.bucket == "fewshot"]
    snapshots = Snapshots.open(db_path)
    executor = GoldExecutor(db_path, gold_schema)
    try:
        async with LLMClient(settings, budget=_budget(settings)) as llm:
            stages = _Stages(
                drafter=QuestionDrafter(
                    llm,
                    snapshots,
                    schema_text=schema_text,
                    model=DRAFT_MODEL,
                    effort=QUESTION_EFFORT,
                ),
                gold=gold_author(
                    llm,
                    executor,
                    policy,
                    grammar=gold_grammar,
                    schema_text=schema_text,
                    model=DRAFT_MODEL,
                    tenant_ids=TENANT_IDS,
                ),
                fewshot=fewshot_author(
                    llm,
                    executor,
                    policy,
                    full_schema=full,
                    grammar=fewshot_grammar,
                    tenant_grammar=build_grammar(
                        visible, GrammarOptions(QueryMode.TENANT, FEWSHOT_MAX_ROWS)
                    ),
                    schema_text=schema_text,
                    model=DRAFT_MODEL,
                ),
                reviewer=Reviewer(
                    llm, schema_text=schema_text, model=REVIEW_MODEL, effort=REVIEW_EFFORT
                ),
            )
            first = {plan[0].key} if plan else set()
            drafted = await _run_all(stages.drafter.draft, eval_plan, warm=lambda b: b.key in first)
            # The pool is drafted second, told every answer-type eval question to stay away from.
            avoid = [
                d.question
                for batch in drafted
                for d in batch.drafts
                if d.bucket in ("answerable", "tenant")
            ]

            async def draft_pool(batch: Batch) -> DraftedBatch:
                return await stages.drafter.draft(batch, avoid=avoid)

            drafted += await _run_all(draft_pool, pool_plan, warm=lambda b: False)
            drafts, dropped = _collect(drafted, planted=only_batches is None)
            outcomes = await _run_all(stages.process, drafts, warm=_first_of_each_kind(drafts))
            spend = llm.budget.summary().render()
    finally:
        executor.close()
        snapshots.close()
    prompts = {stages.drafter.prompt.tag, stages.reviewer.prompt.tag, load_prompt(GOLD_PROMPT).tag}
    selected = {bucket: _select(outcomes, bucket) for bucket in QUOTAS}
    items = _eval_items(selected, prompts)
    pool = _pool_items(selected["fewshot"], prompts)
    report = _report(
        drafted=drafted,
        dropped=dropped,
        outcomes=outcomes,
        selected=selected,
        items=items,
        prompts=sorted(prompts),
        fingerprints=(gold_grammar.fingerprint, fewshot_grammar.fingerprint),
    )
    return report, items, pool, spend


def write_outputs(
    report: BuildReport,
    items: Sequence[SaasEvalItem],
    pool: Sequence[FewShotItem],
    *,
    eval_path: Path = EVAL_PATH,
    fewshot_path: Path = FEWSHOT_PATH,
    report_path: Path = REPORT_PATH,
) -> None:
    write_jsonl(eval_path, items)
    write_jsonl(fewshot_path, pool)
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def phase_spend_usd(settings: Settings | None = None) -> float:
    """Money this phase has spent so far, over every run in the ledger."""
    s = settings or get_settings()
    return sum(e.cost_usd for e in SpendLedger(s.ledger_path).entries() if e.phase == PHASE)


def read_schema_snapshot(path: Path = SCHEMA_SNAPSHOT_PATH) -> str:
    """The schema text of every prompt, exactly as rendered when the set was drafted."""
    return path.read_text(encoding="utf-8").removesuffix("\n")


def write_schema_snapshot(path: Path = SCHEMA_SNAPSHOT_PATH) -> None:
    """Freeze the current catalog rendering. Every request changes, so the next build drafts
    the whole set again through the API."""
    path.write_text(render_schema(load_catalog(SAAS_DB_ID)) + "\n", encoding="utf-8")


def _settings(offline: bool) -> Settings:
    base = get_settings()
    return base.model_copy(
        update={
            "phase": PHASE,
            "offline": offline or base.offline,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "service_tier": "flex",
            "max_concurrency": MAX_CONCURRENCY,
        }
    )


def _budget(settings: Settings) -> RunBudget:
    remaining = max(0.0, PHASE_CAP_USD - phase_spend_usd(settings))
    return RunBudget(
        run_cap_usd=min(settings.max_spend_usd, remaining),
        lifetime_cap_usd=settings.total_spend_cap_usd,
        ledger=SpendLedger(settings.ledger_path),
        run_id=current_run_id(),
        phase=PHASE,
    )


async def _run_all[I, O](
    fn: Callable[[I], Coroutine[Any, Any, O]], inputs: Sequence[I], *, warm: Callable[[I], bool]
) -> list[O]:
    """`fn` over `inputs` in order. Inputs marked `warm` run first, one at a time, so that the
    shared prompt prefix is written to the API's prompt cache once rather than by every
    concurrent first call."""
    results: dict[int, O] = {}
    for i, item in enumerate(inputs):
        if warm(item):
            results[i] = await fn(item)
    try:
        async with asyncio.TaskGroup() as group:
            tasks = {i: group.create_task(fn(x)) for i, x in enumerate(inputs) if i not in results}
    except ExceptionGroup as errors:
        raise errors.exceptions[0] from errors
    results |= {i: t.result() for i, t in tasks.items()}
    return [results[i] for i in range(len(inputs))]


def _first_of_each_kind(drafts: Sequence[Draft]) -> Callable[[Draft], bool]:
    firsts: dict[str, str] = {}
    for d in drafts:
        firsts.setdefault(d.bucket, d.key)
    keys = set(firsts.values())
    return lambda d: d.key in keys


def _collect(
    drafted: Sequence[DraftedBatch], *, planted: bool
) -> tuple[list[Draft], list[Outcome]]:
    """All drafts in plan order minus near-duplicates; the dropped ones become outcomes."""
    drafts: list[Draft] = []
    dropped: list[Outcome] = []
    for batch in drafted:
        drafts.extend(batch.drafts)
        dropped.extend(
            Outcome(_stub(batch.batch, key), False, "drafting", reason)
            for key, reason in batch.rejected
        )
    if planted:
        drafts.extend(planted_drafts(planted_injections()))
    kept: list[Draft] = []
    eval_words: list[frozenset[str]] = []
    for draft in [d for d in drafts if d.bucket != "fewshot"]:
        words = _words(draft.question)
        if any(_jaccard(words, w) >= DUPLICATE_JACCARD for w in eval_words):
            dropped.append(Outcome(draft, False, "drafting", "near_duplicate"))
            continue
        eval_words.append(words)
        kept.append(draft)
    pool_words: list[frozenset[str]] = []
    for draft in [d for d in drafts if d.bucket == "fewshot"]:
        words = _words(draft.question)
        if any(_jaccard(words, w) >= FEWSHOT_OVERLAP_JACCARD for w in eval_words) or any(
            _jaccard(words, w) >= DUPLICATE_JACCARD for w in pool_words
        ):
            dropped.append(Outcome(draft, False, "drafting", "overlaps_eval_or_pool"))
            continue
        pool_words.append(words)
        kept.append(draft)
    return kept, dropped


def _stub(batch: Batch, key: str) -> Draft:
    return Draft(
        key=key,
        bucket=batch.bucket,
        question="",
        difficulty="easy",
        tenant_id=batch.tenant_id,
        drafted_by=DRAFT_MODEL,
        prompt_tag="",
    )


def _words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def _sql_effort(draft: Draft) -> ReasoningEffort:
    return "medium" if draft.difficulty == "hard" else "low"


def _rejection(attempt: Attempt) -> str:
    return attempt.rejection.reason if attempt.rejection is not None else "unknown"


def _only_legit_part_failed(verdict: AttackVerdict) -> bool:
    return verdict.attack_present and verdict.realistic and not verdict.legit_question_faithful


def _review_reason(verdict: Verdict) -> str:
    failed = [
        name
        for name, value in verdict.model_dump().items()
        if isinstance(value, bool) and not value and name != "difficulty_label_correct"
    ]
    return "review:" + ",".join(failed)


def _relabel(draft: Draft, verdict: Verdict) -> Difficulty | None:
    if verdict.difficulty_label_correct or verdict.suggested_difficulty == draft.difficulty:
        return None
    return verdict.suggested_difficulty


def _accepted(
    draft: Draft,
    verdict: Verdict,
    *,
    attempt: Attempt | None,
    first: bool,
    metas: tuple[CallMeta, ...],
) -> Outcome:
    relabel = _relabel(draft, verdict)
    return Outcome(
        draft,
        True,
        difficulty=relabel or draft.difficulty,
        attempt=attempt,
        first_review_passed=first,
        review_fixed=not first,
        relabelled=relabel is not None,
        review_notes=verdict.problems,
        metas=metas,
    )


def _stratum(outcome: Outcome) -> str:
    draft = outcome.draft
    if draft.bucket == "answerable":
        return "user" if draft.persona is not None else str(outcome.difficulty)
    if draft.bucket == "adversarial":
        assert draft.attack is not None
        if draft.attack.category == "comment_unicode":
            kind = "unicode" if draft.attack.technique in UNICODE_TRICKS else "comment"
            return f"comment_unicode:{kind}"
        return draft.attack.category
    return "all"


def _select(outcomes: Sequence[Outcome], bucket: str) -> list[Outcome]:
    """Seeded choice of the bucket's quota per stratum; a short stratum is filled from the
    leftovers of the others."""
    accepted = sorted(
        (o for o in outcomes if o.accepted and o.draft.bucket == bucket), key=lambda o: o.draft.key
    )
    rng = seeded_rng("select", bucket)
    pools: dict[str, list[Outcome]] = defaultdict(list)
    for o in accepted:
        pools[_stratum(o)].append(o)
    for stratum in sorted(pools):
        rng.shuffle(pools[stratum])
    quotas = QUOTAS[bucket]
    chosen = [o for stratum, n in quotas.items() for o in pools.get(stratum, [])[:n]]
    leftovers = [o for stratum in sorted(pools) for o in pools[stratum][quotas.get(stratum, 0) :]]
    rng.shuffle(leftovers)
    chosen += leftovers[: max(0, sum(quotas.values()) - len(chosen))]
    return sorted(chosen, key=lambda o: o.draft.key)


def _splits(outcomes: Sequence[Outcome]) -> dict[str, Split]:
    """Seeded 70/30 dev/test split, stratified by bucket and difficulty."""
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for o in outcomes:
        strata[(o.draft.bucket, str(o.difficulty))].append(o.draft.key)
    out: dict[str, Split] = {}
    for stratum in sorted(strata):
        keys = sorted(strata[stratum])
        seeded_rng("split", *stratum).shuffle(keys)
        n_test = round(TEST_SHARE * len(keys))
        out |= {k: ("test" if i < n_test else "dev") for i, k in enumerate(keys)}
    return out


def _provenance(outcome: Outcome, prompts: set[str], *, gold: bool) -> Provenance:
    draft = outcome.draft
    used = {draft.prompt_tag} if draft.prompt_tag else set()
    used.add(next(p for p in prompts if p.startswith("saas_review@")))
    has_gold_call = gold or draft.bucket == "unanswerable"
    if has_gold_call:
        used.add(next(p for p in prompts if p.startswith("saas_gold_sql@")))
    notes = outcome.review_notes
    if outcome.gold_note:
        notes = "; ".join(n for n in (notes, outcome.gold_note) if n)
    return Provenance(
        drafted_by=draft.drafted_by,
        gold_by=DRAFT_MODEL if gold else None,
        reviewed_by=REVIEW_MODEL,
        review_verdict="fixed" if outcome.review_fixed or outcome.relabelled else "pass",
        review_notes=notes,
        prompts=sorted(used),
    )


def _eval_items(selected: dict[str, list[Outcome]], prompts: set[str]) -> list[SaasEvalItem]:
    chosen = [
        o
        for bucket in ("answerable", "tenant", "unanswerable", "adversarial")
        for o in selected[bucket]
    ]
    splits = _splits(chosen)
    items: list[SaasEvalItem] = []
    numbers: Counter[str] = Counter()
    for o in chosen:
        draft = o.draft
        numbers[draft.bucket] += 1
        verified = None if o.attempt is None else o.attempt.verified
        gold = verified is not None and draft.bucket != "unanswerable"
        assert draft.bucket != "fewshot" and o.difficulty is not None
        items.append(
            SaasEvalItem(
                id=f"saas-{draft.bucket}-{numbers[draft.bucket]:03d}",
                bucket=draft.bucket,
                split=splits[draft.key],
                difficulty=o.difficulty,
                question=draft.question,
                tenant_id=draft.tenant_id,
                user_id=None if draft.persona is None else draft.persona.user_id,
                gold_sql=verified.sql if gold and verified is not None else None,
                eval_tenants=(
                    [t for t, _ in verified.results]
                    if draft.bucket == "tenant" and verified is not None
                    else []
                ),
                expected=EXPECTED_BY_BUCKET[draft.bucket],
                explanation=draft.explanation,
                attack=draft.attack,
                provenance=_provenance(o, prompts, gold=gold),
            )
        )
    return items


def _pool_items(selected: Sequence[Outcome], prompts: set[str]) -> list[FewShotItem]:
    items: list[FewShotItem] = []
    for n, o in enumerate(selected, start=1):
        assert o.attempt is not None and o.attempt.verified is not None
        assert o.difficulty is not None
        items.append(
            FewShotItem(
                id=f"saas-fewshot-{n:03d}",
                question=o.draft.question,
                sql=o.attempt.verified.sql,
                difficulty=o.difficulty,
                provenance=_provenance(o, prompts, gold=True),
            )
        )
    return items


def _report(
    *,
    drafted: Sequence[DraftedBatch],
    dropped: Sequence[Outcome],
    outcomes: Sequence[Outcome],
    selected: dict[str, list[Outcome]],
    items: Sequence[SaasEvalItem],
    prompts: list[str],
    fingerprints: tuple[str, str],
) -> BuildReport:
    stats: dict[str, BucketStats] = {b: BucketStats() for b in QUOTAS}
    rejections: list[Rejection] = []
    for o in [*dropped, *outcomes]:
        s = stats[o.draft.bucket]
        s.drafted += 1
        if o.stage == "drafting":
            s.dropped_drafting += 1
        elif o.stage == "sql":
            s.sql_failed[o.reason or "unknown"] = s.sql_failed.get(o.reason or "unknown", 0) + 1
        if o.first_review_passed is not None or o.stage == "review":
            s.reviewed += 1
            if o.accepted and o.first_review_passed:
                s.review_passed_first += 1
            elif o.accepted:
                s.review_passed_after_fix += 1
            else:
                s.review_failed += 1
        s.relabelled += o.relabelled
        s.sql_repaired += bool(o.accepted and o.attempt is not None and o.attempt.repairs)
        s.accepted += o.accepted
        if not o.accepted and o.stage is not None:
            rejections.append(
                Rejection(
                    key=o.draft.key,
                    bucket=o.draft.bucket,
                    stage=o.stage,
                    reason=o.reason or "unknown",
                    question=o.draft.question,
                    notes=o.review_notes if o.stage == "review" else "",
                )
            )
    for bucket, chosen in selected.items():
        stats[bucket].selected = len(chosen)
    difficulty: dict[str, dict[str, int]] = defaultdict(dict)
    splits: dict[str, dict[str, int]] = defaultdict(dict)
    for item in items:
        d, sp = difficulty[item.bucket], splits[item.bucket]
        d[item.difficulty] = d.get(item.difficulty, 0) + 1
        sp[item.split] = sp.get(item.split, 0) + 1
    unanswerable = [o for o in outcomes if o.draft.bucket == "unanswerable"]
    metas = [m for o in outcomes for m in o.metas]
    metas += [b.meta for b in drafted]
    return BuildReport(
        seed=SAAS_SEED,
        draft_model=DRAFT_MODEL,
        review_model=REVIEW_MODEL,
        prompts=prompts,
        gold_grammar_fingerprint=fingerprints[0],
        fewshot_grammar_fingerprint=fingerprints[1],
        buckets=stats,
        difficulty={b: dict(sorted(v.items())) for b, v in sorted(difficulty.items())},
        splits={b: dict(sorted(v.items())) for b, v in sorted(splits.items())},
        attacks=dict(sorted(Counter(i.attack.category for i in items if i.attack).items())),
        user_mode_items=sum(i.user_id is not None for i in items),
        tenant_eval_tenants={
            str(n): c
            for n, c in sorted(
                Counter(len(i.eval_tenants) for i in items if i.bucket == "tenant").items()
            )
        },
        unanswerable_probe_abstained=sum(o.probe_abstained is True for o in unanswerable),
        unanswerable_probe_wrote_sql=sum(o.probe_abstained is False for o in unanswerable),
        calls=len(metas),
        priced_usd=round(sum(m.priced_usd for m in metas), 4),
        rejections=sorted(rejections, key=lambda r: r.key),
    )
