"""Prompt layout: what goes where, and what must stay identical so the prompt cache is shared."""

from __future__ import annotations

from dataclasses import replace

import pytest
from generation_fakes import FULL_TEXT, LINKED_TEXT, context, grammars

from text2sql.config import QueryMode
from text2sql.generation import STRATEGIES, GenerationContext, build_messages
from text2sql.generation.prompting import json_messages
from text2sql.grammar.conventions import TRAP_PUNCTUATION
from text2sql.prompts import load_prompt
from text2sql.retrieval import FewShotExample

COMMON = load_prompt("generate_common")
CONVENTIONS = COMMON.render("bird_conventions")
TENANT_RULES = COMMON.render("tenant")
FULL_VIEW = [s for s in STRATEGIES.values() if s.schema_view == "full"]


def test_layout_is_prefix_then_method_then_question() -> None:
    ctx = context()
    for spec in STRATEGIES.values():
        dev1, dev2, user = build_messages(spec, ctx)
        assert [m.role for m in (dev1, dev2, user)] == ["developer", "developer", "user"]
        assert (dev2.cache_breakpoint, user.cache_breakpoint) == (False, False)
        # Only the full-schema prefix is reused by later calls, so only it is written.
        assert dev1.cache_breakpoint == (spec.schema_view == "full")
        assert dev1.text.endswith(FULL_TEXT if spec.schema_view == "full" else LINKED_TEXT)
        assert load_prompt(spec.prompt).render("method") in dev2.text
        assert "`sql_query`" in dev2.text
        assert user.text.endswith(ctx.question)
        for message in (dev1, dev2):
            assert ctx.question not in message.text
            assert "MAX(total)" not in message.text


def test_strategies_on_one_view_share_the_cached_prefix_across_questions() -> None:
    first = context()
    other = context(
        question="Which city orders most?",
        evidence=None,
        matched="",
        fewshots=(),
        requested_outputs=(),
    )
    built = [build_messages(spec, ctx)[0] for spec in FULL_VIEW for ctx in (first, other)]
    assert len(FULL_VIEW) >= 3
    assert len({m.text for m in built}) == 1
    assert all(m.cache_breakpoint for m in built)


def test_linked_view_equal_to_the_full_schema_shares_its_cached_prefix() -> None:
    ctx = context()
    full = ctx.grammars["full"]
    unlinked = replace(
        ctx,
        schema_text={"full": FULL_TEXT, "linked": FULL_TEXT},
        grammars={"full": full, "linked": full},
    )
    linked_dev1 = build_messages(STRATEGIES["direct_linked_fewshot"], unlinked)[0]
    assert linked_dev1 == build_messages(STRATEGIES["direct_full"], unlinked)[0]
    assert linked_dev1.cache_breakpoint


def test_linked_strategies_see_the_linked_schema_only() -> None:
    dev1 = build_messages(STRATEGIES["direct_linked_fewshot"], context())[0]
    assert LINKED_TEXT in dev1.text
    assert FULL_TEXT not in dev1.text


def test_user_message_order_and_contents() -> None:
    ctx = context()
    user = build_messages(STRATEGIES["direct_linked_fewshot"], ctx)[2].text
    markers = [
        "MAX(total)",
        "customers.city: 'Paris'",
        "SELECT COUNT(*) FROM singer AS T1",
        "1. order total",
        ctx.question,
    ]
    positions = [user.index(m) for m in markers]
    assert positions == sorted(positions)
    assert "Evidence: none" in user  # the few-shot had no evidence


def test_fewshots_only_for_strategies_that_use_them() -> None:
    ctx = context()
    for spec in STRATEGIES.values():
        user = build_messages(spec, ctx)[2].text
        assert ("FROM singer" in user) == spec.fewshots


@pytest.mark.parametrize("evidence", [None, "", "   "])
def test_missing_evidence_leaves_no_empty_section(evidence: str | None) -> None:
    user = build_messages(STRATEGIES["direct_full"], context(evidence=evidence))[2].text
    assert "【Evidence】" not in user


def test_empty_optional_parts_are_omitted() -> None:
    ctx = context(evidence=None, matched=" ", fewshots=(), requested_outputs=("", " "))
    user = build_messages(STRATEGIES["direct_linked_fewshot"], ctx)[2].text
    assert user == COMMON.render("user_question", question=ctx.question)


BENCHMARK_ONLY_RULES = (
    "CAST(x AS REAL) * 100 / y",  # percentages multiply before dividing, as BIRD's golds do
    "a plain ratio as CAST(x AS REAL) / y",
    "Add LIMIT only when the question asks for a fixed number of rows",
    "no id, name, description or other helper column",
    "with the spelling, case and format of the stored values shown in the schema's example",
)


@pytest.mark.parametrize("mode", list(QueryMode))
def test_bird_conventions_only_in_benchmark_mode(mode: QueryMode) -> None:
    benchmark = mode is QueryMode.BENCHMARK
    dev1 = build_messages(STRATEGIES["divide_conquer"], context(mode))[0].text
    assert (CONVENTIONS in dev1) == benchmark
    for rule in BENCHMARK_ONLY_RULES:
        assert (rule in dev1) == benchmark, rule
    # Copying evidence literals verbatim broke case- and date-format matches in round 0.
    assert "evidence literally" not in dev1


def test_conventions_ablation_drops_only_the_conventions_block() -> None:
    spec = STRATEGIES["direct_full"]
    on = build_messages(spec, context(QueryMode.BENCHMARK))
    off = build_messages(spec, replace(context(QueryMode.BENCHMARK), bird_conventions=False))
    assert CONVENTIONS in on[0].text
    assert CONVENTIONS not in off[0].text
    assert on[0].text.replace("\n\n" + CONVENTIONS, "") == off[0].text
    assert [m.text for m in on[1:]] == [m.text for m in off[1:]]


def test_recommended_percentage_and_ratio_formulas_parse() -> None:
    grammar = context(QueryMode.BENCHMARK).grammars["full"]
    share = "CAST(SUM(CASE WHEN T1.total > 100 THEN 1 ELSE 0 END) AS REAL)"
    assert grammar.accepts(f"SELECT {share} * 100 / COUNT(T1.id) FROM orders AS T1")
    assert grammar.accepts(f"SELECT {share} / COUNT(T1.id) FROM orders AS T1")


def test_limit_and_tenant_rules_follow_the_mode() -> None:
    spec = STRATEGIES["query_plan"]
    bench = build_messages(spec, context(QueryMode.BENCHMARK))[0].text
    prod = build_messages(spec, context(QueryMode.PRODUCTION, max_rows=200))[0].text
    tenant = build_messages(spec, context(QueryMode.TENANT, max_rows=200))[0].text
    assert "LIMIT is optional" in bench
    assert "Every query ends with LIMIT n, n at most 200." in prod
    assert "Every query ends with LIMIT n, n at most 200." in tenant
    assert TENANT_RULES in tenant
    assert TENANT_RULES not in prod
    assert TENANT_RULES not in bench


def test_spelling_rules_are_explained_in_every_mode() -> None:
    for mode in QueryMode:
        dev1 = build_messages(STRATEGIES["direct_full"], context(mode))[0].text
        for rule in ("T1, T2, ... T9", "cte1 ... cte5", "c1 ... c9", "backticks", "'O''Brien'"):
            assert rule in dev1


def test_punctuation_literal_rule_agrees_with_the_grammar() -> None:
    ctx = context(QueryMode.TENANT, max_rows=200)
    dev1 = build_messages(STRATEGIES["direct_full"], ctx)[0].text
    assert " ".join(TRAP_PUNCTUATION) in dev1
    grammar = ctx.grammars["full"]
    query = "SELECT T1.id FROM customers AS T1 WHERE T1.city = {} LIMIT 5"
    # The spellings the prompt tells the model to use parse; the one it forbids does not.
    for literal in ("'+'", "'-1 day'", "'(' || 'none)'"):
        assert literal in dev1
        assert grammar.accepts(query.format(literal))
    assert not grammar.accepts(query.format("'(none)'"))


def test_abstain_is_described_only_when_the_grammar_allows_it() -> None:
    spec = STRATEGIES["direct_full"]
    allowed = build_messages(spec, context(QueryMode.TENANT, allow_abstain=True))[0].text
    forbidden = build_messages(spec, context(QueryMode.TENANT, allow_abstain=False))[0].text
    assert "ABSTAIN: " in allowed
    assert "ABSTAIN" not in forbidden
    assert "ABSTAIN" not in build_messages(spec, context(QueryMode.BENCHMARK))[0].text


def test_context_rejects_grammars_built_for_another_mode() -> None:
    with pytest.raises(ValueError, match="built for production mode"):
        replace(context(QueryMode.BENCHMARK), grammars=grammars(QueryMode.PRODUCTION))


def test_context_rejects_mismatched_views() -> None:
    ctx = context()
    with pytest.raises(ValueError, match="differ"):
        replace(ctx, schema_text={"full": FULL_TEXT})


def test_strategy_needing_a_missing_view_fails_clearly() -> None:
    ctx = context()
    full_only = GenerationContext(
        db_id=ctx.db_id,
        question=ctx.question,
        evidence=ctx.evidence,
        mode=ctx.mode,
        schema_text={"full": FULL_TEXT},
        grammars={"full": ctx.grammars["full"]},
    )
    with pytest.raises(ValueError, match="no 'linked' schema view"):
        build_messages(STRATEGIES["small_linked"], full_only)


def test_json_ablation_keeps_the_prompt_and_moves_tool_rules_into_the_method() -> None:
    ctx = context()
    spec = STRATEGIES["divide_conquer"]
    tool_dev1, tool_dev2, tool_user = build_messages(spec, ctx)
    dev1, dev2, user = json_messages(spec, ctx)
    assert (dev1, user) == (tool_dev1, tool_user)
    assert ctx.grammars["full"].description in dev2.text
    assert "`sql` field" in dev2.text
    assert "`sql_query`" not in dev2.text
    assert dev2.text.startswith(tool_dev2.text.split("\n\n")[0])


def test_fewshot_text_is_rendered_verbatim() -> None:
    shot = FewShotExample(
        "Q with $dollar?", "cost is $5", "SELECT T1.a FROM t AS T1 WHERE T1.b = '$x'"
    )
    user = build_messages(STRATEGIES["direct_linked_fewshot"], context(fewshots=(shot,)))[2].text
    assert "Question: Q with $dollar?\nEvidence: cost is $5\nSQL: " + shot.sql in user
