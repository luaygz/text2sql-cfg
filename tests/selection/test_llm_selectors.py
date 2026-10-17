from __future__ import annotations

import asyncio
from collections import Counter

import pytest
from selection_fakes import (
    REFUSE,
    Call,
    FakeLLM,
    cand,
    checker_candidates,
    checker_test,
    judge_pair,
)

from text2sql.catalog import Catalog, CatalogColumn, CatalogTable
from text2sql.catalog.schema import ForeignKey
from text2sql.prompts import load_prompt
from text2sql.selection import (
    PairwiseVerdict,
    UnitTests,
    UnitTestVerdicts,
    cluster_candidates,
    judge_select,
    unit_test_select,
)
from text2sql.selection.unit_tests import CandidateVerdict

SCHEMA_TEXT = "FULL SCHEMA TEXT"
QUESTION = "Which customers spent the most?"
EVIDENCE = "most refers to MAX(total)"

GOLD = "SELECT name FROM customers ORDER BY spent DESC LIMIT 1"
# Three clusters: a big wrong one (3 votes), a middle wrong one (2), and gold alone.
CANDS = [
    cand(0, "SELECT name FROM customers", [("ann",), ("bob",)], strategy="direct_full"),
    cand(1, "SELECT name FROM customers WHERE 1", [("bob",), ("ann",)], strategy="query_plan"),
    cand(2, "SELECT name FROM customers WHERE 2", [("ann",), ("bob",)], strategy="direct_full"),
    cand(3, "SELECT name FROM customers LIMIT 1", [("ann",)], strategy="direct_full"),
    cand(4, "SELECT name FROM customers LIMIT 1 OFFSET 0", [("ann",)], strategy="direct_full"),
    cand(5, GOLD, [("bob",)], strategy="divide_conquer", ordered=True),
]
CLUSTERS = cluster_candidates(CANDS)
REPS = {c.representative: CANDS[c.representative].sql for c in CLUSTERS}


def run_judge(llm: FakeLLM, cands=CANDS, clusters=CLUSTERS, **kw):
    args = {
        "question": QUESTION,
        "evidence": EVIDENCE,
        "schema_text": SCHEMA_TEXT,
        "model": "gen-model",
        "effort": "low",
    } | kw
    return asyncio.run(judge_select(llm, cands, clusters, **args))


def run_unit_tests(llm: FakeLLM, cands=CANDS, clusters=CLUSTERS, **kw):
    args = {
        "question": QUESTION,
        "evidence": EVIDENCE,
        "schema_text": SCHEMA_TEXT,
        "writer_model": "gen-model",
        "checker_model": "small-model",
        "effort": "low",
    } | kw
    return asyncio.run(unit_test_select(llm, cands, clusters, **args))


def prefer_gold(call: Call) -> PairwiseVerdict:
    a, b = judge_pair(call)
    if GOLD in (a, b):
        return PairwiseVerdict(reason="gold", winner="A" if a == GOLD else "B")
    return PairwiseVerdict(reason="shorter", winner="A" if len(a) < len(b) else "B")


def shop_catalog() -> Catalog:
    def table(name: str, *cols: str) -> CatalogTable:
        columns = tuple(CatalogColumn(name=c, primary_key=c == "id") for c in cols)
        return CatalogTable(name=name, row_count=1, profiled_rows=1, columns=columns)

    return Catalog(
        db_id="shop",
        tables=(
            table("customers", "id", "name", "spent"),
            table("orders", "id", "customer_id", "total"),
            table("suppliers", "id", "rating"),
        ),
        foreign_keys=(ForeignKey("orders", "customer_id", "customers", "id"),),
    )


class TestJudge:
    def test_fewer_than_two_clusters_make_no_calls(self) -> None:
        llm = FakeLLM(prefer_gold)
        one = [cand(7, "SELECT 1", [(1,)]), cand(8, "SELECT 1 + 0", [(1,)])]
        selection = run_judge(llm, one, cluster_candidates(one))
        assert (selection.index, selection.method, selection.calls) == (7, "judge", ())
        assert selection.vote_share == 1.0
        nothing = run_judge(llm, [], [])
        assert nothing.index is None and nothing.n_clusters == 0
        assert llm.calls == []

    def test_every_pair_is_asked_once_in_each_order(self) -> None:
        llm = FakeLLM(prefer_gold)
        selection = run_judge(llm)
        shown = Counter(judge_pair(call) for call in llm.calls)
        expected = {(a, b) for a in REPS.values() for b in REPS.values() if a != b}
        assert set(shown) == expected and set(shown.values()) == {1}
        assert len(llm.calls) == 6  # m(m-1) for m = 3
        assert selection.calls == tuple(llm.metas)
        assert len(selection.notes) == 6

    def test_most_pairwise_wins_beats_the_biggest_cluster(self) -> None:
        selection = run_judge(FakeLLM(prefer_gold))
        assert selection.index == 5
        assert selection.method == "judge"
        assert selection.n_clusters == 3
        # Gold wins all 4 of its comparisons; the shorter of the other two wins its 2 against
        # the third and none against gold.
        assert selection.scores == {5: 4.0, 0: 2.0, 3: 0.0}
        assert selection.vote_share == pytest.approx(1 / 6)

    def test_position_bias_cancels_and_the_tie_goes_to_the_larger_cluster(self) -> None:
        llm = FakeLLM(lambda call: PairwiseVerdict(reason="first", winner="A"))
        selection = run_judge(llm)
        assert set(selection.scores.values()) == {2.0}
        assert selection.index == 0  # the 3-member cluster

    def test_a_failed_comparison_awards_nothing_but_its_cost_is_kept(self) -> None:
        def reply(call: Call):
            a, b = judge_pair(call)
            if (a, b) == (REPS[5], REPS[0]):
                return REFUSE
            return prefer_gold(call)

        llm = FakeLLM(reply)
        selection = run_judge(llm)
        assert selection.scores == {5: 3.0, 0: 2.0, 3: 0.0}
        assert selection.index == 5
        assert selection.calls == tuple(llm.metas)
        assert sum("no verdict" in note for note in selection.notes) == 1

    def test_prompt_shows_question_evidence_both_queries_and_ten_rows(self) -> None:
        many = [(f"name{i:02d}",) for i in range(12)]
        cands = [
            cand(0, "SELECT name FROM customers", many, columns=("name",)),
            cand(1, "SELECT name FROM customers WHERE spent > 0", many[:2], columns=("name",)),
        ]
        llm = FakeLLM(prefer_gold)
        run_judge(llm, cands, cluster_candidates(cands), evidence=None, effort="medium")
        call = llm.calls[0]
        assert (call.model, call.effort, call.output) == ("gen-model", "medium", PairwiseVerdict)
        assert call.purpose.startswith("selection.judge/judge_pairwise@")
        assert [m.role for m in call.messages] == ["developer", "user"]
        assert QUESTION in call.user
        assert "<evidence>\n(none)\n</evidence>" in call.user
        assert SCHEMA_TEXT in call.user
        assert "total rows: 12" in call.user and "total rows: 2" in call.user
        assert '["name09"]' in call.user and '["name10"]' not in call.user

    def test_prompt_schema_is_the_union_of_what_the_pair_reads(self) -> None:
        cands = [
            cand(
                0,
                "SELECT T1.name FROM customers AS T1 JOIN orders AS T2 "
                "ON T1.id = T2.customer_id WHERE T2.total > 5",
                [("a",)],
            ),
            cand(1, "SELECT COUNT(*) FROM orders", [(3,)]),
        ]
        llm = FakeLLM(prefer_gold)
        run_judge(llm, cands, cluster_candidates(cands), catalog=shop_catalog())
        for call in llm.calls:
            assert "# Table: customers" in call.user and "# Table: orders" in call.user
            assert "suppliers" not in call.user and "(spent" not in call.user
            assert SCHEMA_TEXT not in call.user

    def test_schema_falls_back_to_the_given_text_when_extraction_fails(self) -> None:
        cands = [cand(0, "SELECT name FROM customers", [("a",)]), cand(1, "SELECT (((", [(1,)])]
        llm = FakeLLM(prefer_gold)
        run_judge(llm, cands, cluster_candidates(cands), catalog=shop_catalog())
        assert all(SCHEMA_TEXT in call.user for call in llm.calls)


GOOD_TEST = "The answer SQL query should order by spent descending."
BAD_TEST = "The answer SQL query should return two rows."
BEST_TEST = load_prompt("unit_tests_check").render("best_answer_test")


def scripted_checker(passes: dict[str, set[str]]):
    """Checker reply: for each test text, the set of SQL strings that pass it."""

    def reply(call: Call):
        if call.output is UnitTests:
            return UnitTests(tests=[GOOD_TEST, BAD_TEST])
        shown = checker_candidates(call)
        winners = passes.get(checker_test(call), set())
        return UnitTestVerdicts(
            verdicts=[
                CandidateVerdict(candidate=n, passed=sql in winners) for n, sql in shown.items()
            ]
        )

    return reply


class TestUnitTests:
    def test_fewer_than_two_clusters_make_no_calls(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        one = [cand(2, "SELECT 1", [(1,)])]
        selection = run_unit_tests(llm, one, cluster_candidates(one))
        assert (selection.index, selection.method, selection.calls) == (2, "unit_test", ())
        assert llm.calls == []

    def test_one_writer_call_then_one_checker_call_per_test_plus_the_fixed_one(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        selection = run_unit_tests(llm, n_tests=2)
        writer, *checkers = llm.calls
        assert (writer.model, writer.output) == ("gen-model", UnitTests)
        assert writer.purpose.startswith("selection.unit_test.write/unit_tests_write@")
        assert "Write 2 unit tests" in writer.developer
        assert len(checkers) == 3
        assert {c.model for c in checkers} == {"small-model"}
        assert all(
            c.purpose.startswith("selection.unit_test.check/unit_tests_check@") for c in checkers
        )
        assert [checker_test(c) for c in checkers][:2] == [GOOD_TEST, BAD_TEST]
        assert checker_test(checkers[2]).startswith("Only the best answer")
        assert selection.calls == tuple(llm.metas)

    def test_writer_sees_each_cluster_once_with_its_size(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        run_unit_tests(llm)
        writer = llm.calls[0]
        assert writer.user.count("<cluster ") == 3
        assert '<cluster number="1" candidates="3">' in writer.user
        assert all(sql in writer.user for sql in REPS.values())
        assert CANDS[1].sql not in writer.user  # not a representative

    def test_extra_tests_are_cut_to_n_tests(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        run_unit_tests(llm, n_tests=1)
        assert [checker_test(c) for c in llm.calls[1:]][:-1] == [GOOD_TEST]
        assert len(llm.calls) == 3

    def test_score_is_tests_passed(self) -> None:
        passes = {GOOD_TEST: {GOLD}, BAD_TEST: {REPS[0]}, BEST_TEST: {GOLD}}
        llm = FakeLLM(scripted_checker(passes))
        selection = run_unit_tests(llm)
        assert selection.scores == {5: 2.0, 0: 1.0, 3: 0.0}
        assert selection.index == 5
        assert selection.vote_share == pytest.approx(1 / 6)

    def test_score_ties_go_to_the_larger_cluster(self) -> None:
        passes = {GOOD_TEST: {GOLD}, BAD_TEST: {REPS[0]}}
        selection = run_unit_tests(FakeLLM(scripted_checker(passes)))
        assert selection.scores == {5: 1.0, 0: 1.0, 3: 0.0}
        assert selection.index == 0

    def test_verdicts_are_matched_by_candidate_number(self) -> None:
        def reply(call: Call):
            if call.output is UnitTests:
                return UnitTests(tests=[GOOD_TEST])
            gold = next(n for n, sql in checker_candidates(call).items() if sql == GOLD)
            return UnitTestVerdicts(
                verdicts=[
                    CandidateVerdict(candidate=99, passed=True),  # not shown: ignored
                    CandidateVerdict(candidate=gold, passed=True),
                    CandidateVerdict(candidate=gold, passed=False),  # duplicate: first counts
                ]  # the other two candidates get no verdict and fail
            )

        selection = run_unit_tests(FakeLLM(reply))
        assert selection.scores == {5: 2.0, 0: 0.0, 3: 0.0}

    def test_a_failed_writer_leaves_only_the_fixed_test(self) -> None:
        def reply(call: Call):
            if call.output is UnitTests:
                return REFUSE
            return scripted_checker({})(call)

        llm = FakeLLM(reply)
        selection = run_unit_tests(llm)
        assert len(llm.calls) == 2
        assert checker_test(llm.calls[1]).startswith("Only the best answer")
        assert selection.calls == tuple(llm.metas)

    def test_a_failed_checker_passes_nobody(self) -> None:
        passes = {GOOD_TEST: {GOLD}, BAD_TEST: {REPS[0]}}

        def reply(call: Call):
            if call.output is UnitTestVerdicts and checker_test(call) == GOOD_TEST:
                return REFUSE
            return scripted_checker(passes)(call)

        selection = run_unit_tests(FakeLLM(reply))
        assert selection.scores == {5: 0.0, 0: 1.0, 3: 0.0}
        assert selection.index == 0
        assert len(selection.calls) == 4

    def test_zero_tests_skips_the_writer(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        run_unit_tests(llm, n_tests=0)
        assert [c.output for c in llm.calls] == [UnitTestVerdicts]

    def test_negative_test_count_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="n_tests"):
            run_unit_tests(FakeLLM(scripted_checker({})), n_tests=-1)

    def test_prompts_use_the_schema_union_of_all_representatives(self) -> None:
        llm = FakeLLM(scripted_checker({}))
        run_unit_tests(llm, catalog=shop_catalog())
        for call in llm.calls:
            assert "# Table: customers" in call.user
            assert "orders" not in call.user and SCHEMA_TEXT not in call.user
