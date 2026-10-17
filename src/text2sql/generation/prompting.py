"""Messages for candidate generation and repair (ADR-008 stages 6-7, ADR-012).

Layout, chosen for the prompt cache: the `sql_query` tool (grammar) renders first; developer
message 1 holds everything a database and schema view share (task, spelling rules, mode rules,
BIRD conventions in benchmark mode, the schema); developer message 2 holds the strategy's
method; the user message holds everything about the question. Strategies that use the same
grammar on the same model therefore share one cached prefix, across questions on the same
database too.

Developer message 1 carries the cache breakpoint only when its grammar is the request's
full-schema grammar. A cache write costs 1.25x the input price and only pays off when the
prefix is read again; a per-question linked grammar is almost never reused (ADR-012).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from text2sql.config import QueryMode
from text2sql.generation.strategies import SchemaView, StrategySpec
from text2sql.grammar import SqlGrammar
from text2sql.grammar.conventions import (
    AGGREGATES,
    CAST_TYPES,
    SCALAR_FUNCTIONS,
    TRAP_PUNCTUATION,
)
from text2sql.llm import Message, tool_output_item
from text2sql.llm.client import message_item
from text2sql.prompts import PromptTemplate, load_prompt
from text2sql.retrieval import FewShotExample

COMMON_PROMPT = "generate_common"
REPAIR_PROMPT = "repair"

RepairKind = Literal["error", "validator", "empty", "value"]

_CLOSING: Mapping[RepairKind, str] = {
    "error": "fix",
    "validator": "fix",
    "empty": "check",
    "value": "value_check",
}
"""The section that ends the feedback: a fix when something failed, a check when nothing did."""


@dataclass(frozen=True)
class GenerationContext:
    """Everything the strategies of one request see. `schema_text` and `grammars` hold the same
    views; every grammar must be built for `mode`."""

    db_id: str
    question: str
    evidence: str | None
    mode: QueryMode
    schema_text: Mapping[SchemaView, str]
    grammars: Mapping[SchemaView, SqlGrammar]
    matched_values_text: str = ""
    """The `render_matched_values` block, or "" when nothing matched."""
    fewshots: Sequence[FewShotExample] = ()
    requested_outputs: Sequence[str] = ()
    bird_conventions: bool = True
    """Include the BIRD annotation-style block in benchmark mode (off only for its ablation)."""

    def __post_init__(self) -> None:
        if set(self.schema_text) != set(self.grammars):
            raise ValueError(
                f"schema_text views {sorted(self.schema_text)} differ from grammar views "
                f"{sorted(self.grammars)}"
            )
        for view, grammar in self.grammars.items():
            if grammar.options.mode is not self.mode:
                raise ValueError(
                    f"the {view} grammar is built for {grammar.options.mode} mode, "
                    f"the request is in {self.mode} mode"
                )

    def grammar(self, view: SchemaView) -> SqlGrammar:
        try:
            return self.grammars[view]
        except KeyError:
            raise ValueError(
                f"this request has no {view!r} schema view (has {sorted(self.grammars)})"
            ) from None


def build_messages(spec: StrategySpec, ctx: GenerationContext) -> list[Message]:
    """The input messages of one grammar-tool candidate."""
    return _messages(spec, ctx, finish=_common().render("finish_tool"))


def json_messages(spec: StrategySpec, ctx: GenerationContext) -> list[Message]:
    """The same messages for the grammar-off ablation: the tool's spelling rules (its
    description) move into developer message 2, since no tool is sent."""
    rules = ctx.grammar(spec.schema_view).description
    return _messages(spec, ctx, finish=_common().render("finish_json", rules=rules))


def shared_prefix(ctx: GenerationContext, view: SchemaView) -> str:
    """Developer message 1: identical for every strategy on this request's `view`."""
    common = _common()
    options = ctx.grammar(view).options
    limit = "limit_optional" if options.mode is QueryMode.BENCHMARK else "limit_required"
    parts = [
        common.render("task"),
        common.render(
            "spelling",
            functions=", ".join((*AGGREGATES, *SCALAR_FUNCTIONS)),
            cast_types="|".join(CAST_TYPES),
            trap_punctuation=" ".join(TRAP_PUNCTUATION),
        ),
        common.render(limit, max_rows=str(options.max_rows)),
    ]
    if options.mode is QueryMode.TENANT:
        parts.append(common.render("tenant"))
    if options.allow_abstain:
        parts.append(common.render("abstain"))
    if ctx.mode is QueryMode.BENCHMARK and ctx.bird_conventions:
        parts.append(common.render("bird_conventions"))
    parts.append(common.render("schema", schema=ctx.schema_text[view].strip()))
    return "\n\n".join(parts)


def question_message(spec: StrategySpec, ctx: GenerationContext) -> str:
    """The user message: evidence, matched values, few-shots, requested outputs, question."""
    common = _common()
    parts: list[str] = []
    if ctx.evidence and ctx.evidence.strip():
        parts.append(common.render("user_evidence", evidence=ctx.evidence.strip()))
    if ctx.matched_values_text.strip():
        parts.append(common.render("user_matched_values", block=ctx.matched_values_text.strip()))
    if spec.fewshots and ctx.fewshots:
        examples = "\n\n".join(
            common.render(
                "user_fewshot",
                question=shot.question.strip(),
                evidence=(shot.evidence or "").strip() or "none",
                sql=shot.sql.strip(),
            )
            for shot in ctx.fewshots
        )
        parts.append(common.render("user_fewshots", examples=examples))
    outputs = [o.strip() for o in ctx.requested_outputs if o.strip()]
    if outputs:
        listed = "\n".join(f"{i}. {o}" for i, o in enumerate(outputs, start=1))
        parts.append(common.render("user_requested_outputs", outputs=listed))
    parts.append(common.render("user_question", question=ctx.question.strip()))
    return "\n\n".join(parts)


def repair_feedback(*, kind: RepairKind, detail: str, value_hints: Sequence[str] = ()) -> str:
    """Tool output for a repair turn: what was observed, value hints, then what to do.

    `detail` is the SQLite error (`error`), the validator's `rule: detail` (`validator`), an
    optional note for an empty result (`empty`), or one line per compared value the column does
    not hold, with its similar stored values (`value`). Each hint is one line, e.g.
    "`T1.County` = 'alameda': stored values are 'Alameda', 'Alpine'".
    """
    prompt = load_prompt(REPAIR_PROMPT)
    detail = detail.strip()
    if kind == "empty":
        parts = [prompt.render("empty")]
        if detail:
            parts.append(prompt.render("empty_detail", detail=detail))
    elif not detail:
        raise ValueError(f"a {kind} repair needs the observed problem in `detail`")
    else:
        parts = [prompt.render(kind, detail=detail)]
    hints = [h.strip() for h in value_hints if h.strip()]
    if hints:
        parts.append(prompt.render("value_hints", hints="\n".join(f"- {h}" for h in hints)))
    parts.append(prompt.render(_CLOSING[kind]))
    return "\n\n".join(parts)


def repair_turn(call_id: str, feedback: str) -> tuple[dict[str, Any], ...]:
    """Input items that answer tool call `call_id` with `feedback` and ask for the next call.

    The user message is needed: when the input ends at the tool output, gpt-6.1-sol never
    makes the forced call and the response ends incomplete (`max_messages`, ADR-012).
    """
    ask = Message("user", load_prompt(REPAIR_PROMPT).render("continue"))
    return tool_output_item(call_id, feedback), message_item(ask)


def prompt_tags(spec: StrategySpec) -> tuple[str, ...]:
    """`name@version` of every template a candidate of `spec` is built from."""
    return load_prompt(spec.prompt).tag, _common().tag


def purpose(
    stage: Literal["generate", "repair", "generate_json"],
    spec: StrategySpec,
    *,
    attempt: int | None = None,
) -> str:
    """Call label for the ledger and traces, carrying the prompt versions used, e.g.
    `repair.query_plan#1[repair@1.0,generate_query_plan@1.0,generate_common@1.0]`."""
    tags = prompt_tags(spec)
    if stage == "repair":
        tags = (load_prompt(REPAIR_PROMPT).tag, *tags)
    label = f"{stage}.{spec.name}" if attempt is None else f"{stage}.{spec.name}#{attempt}"
    return f"{label}[{','.join(tags)}]"


def reusable_prefix(ctx: GenerationContext, view: SchemaView) -> bool:
    """Whether developer message 1 for `view` is worth a cache write: its grammar is the
    full-schema grammar, which every question on the database shares."""
    full = ctx.grammars.get("full")
    return full is not None and ctx.grammar(view).fingerprint == full.fingerprint


def _messages(spec: StrategySpec, ctx: GenerationContext, *, finish: str) -> list[Message]:
    method = load_prompt(spec.prompt).render("method")
    view = spec.schema_view
    return [
        Message("developer", shared_prefix(ctx, view), cache_breakpoint=reusable_prefix(ctx, view)),
        Message("developer", f"{method}\n\n{finish}"),
        Message("user", question_message(spec, ctx)),
    ]


def _common() -> PromptTemplate:
    return load_prompt(COMMON_PROMPT)
