from __future__ import annotations

import pytest
from selection_fakes import cand

from text2sql.selection import cluster_candidates, majority_vote

RANK = {"divide_conquer": 0, "query_plan": 1, "direct_full": 2}


def vote(cands, **kw):
    return majority_vote(cands, cluster_candidates(cands), strategy_rank=RANK, **kw)


def test_largest_cluster_wins_and_reports_its_share() -> None:
    cands = [
        cand(0, "SELECT 1", [(1,)]),
        cand(1, "SELECT 2", [(2,)]),
        cand(2, "SELECT 2 + 0", [(2,)]),
        cand(3, "SELECT 4 - 2", [(2,)]),
        cand(4, "SELECT 3", [(3,)]),
    ]
    selection = vote(cands)
    assert selection.index == 1
    assert selection.method == "vote"
    assert selection.vote_share == pytest.approx(3 / 5)
    assert selection.n_clusters == 3
    assert selection.scores == {1: 3.0, 0: 1.0, 4: 1.0}
    assert selection.calls == ()


def test_size_tie_goes_to_the_better_ranked_strategy() -> None:
    cands = [
        cand(0, "SELECT 1", [(1,)], strategy="direct_full"),
        cand(1, "SELECT 1 + 0", [(1,)], strategy="direct_full"),
        cand(2, "SELECT 2 * 1000", [(2,)], strategy="query_plan"),
        cand(3, "SELECT 2 * 1000 + 0", [(2,)], strategy="direct_full"),
    ]
    selection = vote(cands)
    assert selection.index == 2
    assert selection.vote_share == pytest.approx(0.5)


def test_a_cluster_ranks_by_its_best_member_strategy() -> None:
    cands = [
        cand(0, "SELECT 1", [(1,)], strategy="query_plan"),
        cand(1, "SELECT 1 + 0", [(1,)], strategy="query_plan"),
        cand(2, "SELECT 2 * 1000", [(2,)], strategy="direct_full"),
        cand(3, "SELECT 2 * 1000 + 0", [(2,)], strategy="divide_conquer"),
    ]
    assert vote(cands).index == 2


def test_strategies_missing_from_the_ranking_rank_last() -> None:
    cands = [
        cand(0, "SELECT 1", [(1,)], strategy="experimental"),
        cand(1, "SELECT 2 * 1000", [(2,)], strategy="direct_full"),
    ]
    assert vote(cands).index == 1


def test_then_the_shortest_sql_then_the_lowest_index() -> None:
    longer = cand(0, "SELECT 10 + 0", [(10,)])
    shorter = cand(1, "SELECT 20", [(20,)])
    assert vote([longer, shorter]).index == 1
    assert vote([cand(5, "SELECT 1", [(1,)]), cand(2, "SELECT 2", [(2,)])]).index == 2


def test_an_empty_result_loses_to_any_result_with_rows() -> None:
    cands = [
        cand(0, "SELECT a FROM t WHERE 0", []),
        cand(1, "SELECT a FROM t WHERE 1 = 0", []),
        cand(2, "SELECT a FROM t WHERE a = 'x'", []),
        cand(3, "SELECT a FROM t LIMIT 1", [("y",)]),
    ]
    selection = vote(cands)
    assert selection.index == 3
    assert selection.vote_share == pytest.approx(0.25)
    assert vote(cands, prefer_non_empty=False).index == 0


def test_an_empty_result_wins_when_nothing_returned_rows() -> None:
    cands = [cand(0, "SELECT a FROM t WHERE 0", []), cand(1, "SELECT b FROM t WHERE 0", [])]
    selection = vote(cands)
    assert selection.index == 0
    assert selection.vote_share == 1.0


def test_no_executed_candidates_selects_nothing() -> None:
    selection = majority_vote([], [], strategy_rank=RANK)
    assert selection.index is None
    assert selection.vote_share == 0.0
    assert selection.n_clusters == 0
    assert selection.scores == {}
