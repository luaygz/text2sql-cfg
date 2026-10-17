from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from selection_fakes import cand

from text2sql.evals.bird_metric import results_match
from text2sql.execution import QueryResult
from text2sql.selection import (
    ExecutedCandidate,
    cluster_candidates,
    has_top_level_order_by,
    result_fingerprint,
)


def same(
    a: list[tuple[object, ...]], b: list[tuple[object, ...]], *, ordered: bool = False
) -> bool:
    return result_fingerprint(a, ordered=ordered) == result_fingerprint(b, ordered=ordered)


class TestFingerprint:
    def test_row_order_is_ignored_for_unordered_results(self) -> None:
        assert same([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])

    def test_row_order_counts_when_the_query_orders_its_rows(self) -> None:
        assert not same([(1,), (2,)], [(2,), (1,)], ordered=True)
        assert same([(1,), (2,)], [(1,), (2,)], ordered=True)

    def test_order_by_limit_1_matches_an_unordered_single_row(self) -> None:
        # e.g. ORDER BY x DESC LIMIT 1 against WHERE x = (SELECT MAX(x) ...)
        assert result_fingerprint([("x", 3)], ordered=True) == result_fingerprint(
            [("x", 3)], ordered=False
        )
        assert result_fingerprint([], ordered=True) == result_fingerprint([], ordered=False)

    def test_duplicate_rows_collapse_as_in_bird_ex(self) -> None:
        assert same([(1,), (1,), (2,)], [(2,), (1,)])
        assert results_match([(1,), (1,), (2,)], [(2,), (1,)])

    def test_ordered_results_keep_duplicates_and_sequence(self) -> None:
        assert not same([(1,), (1,), (2,)], [(1,), (2,)], ordered=True)
        assert not same([(1,), (2,), (1,)], [(1,), (1,), (2,)], ordered=True)
        # A repeated single row has only one possible order.
        assert result_fingerprint([(1,), (1,)], ordered=True) == result_fingerprint(
            [(1,)], ordered=False
        )

    def test_int_and_integral_float_match(self) -> None:
        assert same([(1, 2.0)], [(1.0, 2)])
        assert same([(-0.0,)], [(0,)])
        assert same([(10**20,)], [(1e20,)])

    def test_floats_have_no_tolerance_as_in_bird_ex(self) -> None:
        assert not same([(0.1 + 0.2,)], [(0.3,)])
        assert not results_match([(0.1 + 0.2,)], [(0.3,)])
        # 2**53 + 1 is not representable as a float, and Python equality is exact.
        assert not same([(2**53 + 1,)], [(float(2**53 + 1),)])

    def test_null_matches_only_null(self) -> None:
        assert same([(None, 1)], [(None, 1)])
        assert not same([(None,)], [(0,)])
        assert not same([(None,)], [("",)])
        assert not same([(None,)], [("None",)])

    def test_text_never_matches_a_number_or_blob(self) -> None:
        assert not same([("1",)], [(1,)])
        assert not same([("ab",)], [(b"ab",)])

    def test_values_cannot_bleed_across_columns_or_rows(self) -> None:
        assert not same([("x|y", "z")], [("x", "y|z")])
        assert not same([('a", "b',)], [("a", "b")])
        assert not same([("a",), ("b",)], [("a\nb",)])

    def test_column_count_matters_but_column_names_do_not(self) -> None:
        assert not same([(1,)], [(1, None)])
        a = cand(0, "SELECT x AS a FROM t", [(1,)], columns=("a",))
        b = cand(1, "SELECT x AS b FROM t", [(1,)], columns=("b",))
        assert len(cluster_candidates([a, b])) == 1

    def test_truncated_result_never_matches_a_complete_one(self) -> None:
        rows = [(1,), (2,)]
        assert result_fingerprint(rows, ordered=False, truncated=True) != result_fingerprint(
            rows, ordered=False
        )


VALUES = st.one_of(
    st.none(),
    st.integers(-2, 2),
    st.sampled_from([0.0, 1.0, -1.0, 0.5, 0.1 + 0.2, 0.3, 1e20]),
    st.sampled_from(["", "a", "1", "None"]),
    st.sampled_from([b"", b"a"]),
)
ROWS = st.lists(st.tuples(VALUES), max_size=3)


@given(ROWS, ROWS)
def test_unordered_fingerprints_agree_exactly_with_bird_ex(a, b) -> None:
    """A cluster is an EX equivalence class: same fingerprint iff `results_match` says equal."""
    assert same(a, b) == results_match(a, b)


@given(ROWS, st.randoms(use_true_random=False))
def test_reordering_duplicating_and_retyping_rows_keeps_the_fingerprint(a, rnd) -> None:
    def retype(v: object) -> object:
        if isinstance(v, int):
            return float(v)
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    b = [tuple(retype(v) for v in row) for row in a] + a[:1]
    rnd.shuffle(b)
    assert same(a, b)
    assert results_match(a, b)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT a FROM t ORDER BY a", True),
        ("SELECT a FROM t ORDER BY a DESC LIMIT 3", True),
        ("WITH c AS (SELECT a FROM t) SELECT a FROM c ORDER BY a", True),
        ("SELECT a FROM t UNION SELECT b FROM u ORDER BY 1", True),
        ("(SELECT a FROM t ORDER BY a)", True),
        ("SELECT a FROM t", False),
        ("WITH c AS (SELECT a FROM t ORDER BY a) SELECT a FROM c", False),
        ("SELECT * FROM (SELECT a FROM t ORDER BY a)", False),
        ("SELECT a FROM t WHERE a IN (SELECT a FROM t ORDER BY a LIMIT 3)", False),
        ("SELECT ROW_NUMBER() OVER (ORDER BY a) FROM t", False),
        ("SELECT GROUP_CONCAT(a ORDER BY a) FROM t", False),
        ("SELECT ((( FROM", False),
    ],
)
def test_has_top_level_order_by(sql: str, expected: bool) -> None:
    assert has_top_level_order_by(sql) is expected


def test_from_result_reads_ordering_from_the_sql() -> None:
    result = QueryResult(columns=("a",), rows=((2,), (1,)), truncated=True, elapsed_s=0.01)
    built = ExecutedCandidate.from_result(
        index=4, strategy="query_plan", sql="SELECT a FROM t ORDER BY a DESC", result=result
    )
    assert built == ExecutedCandidate(
        index=4,
        strategy="query_plan",
        sql="SELECT a FROM t ORDER BY a DESC",
        columns=("a",),
        rows=((2,), (1,)),
        ordered=True,
        truncated=True,
    )


class TestClusterCandidates:
    def test_groups_by_result_largest_first_with_shortest_sql_representative(self) -> None:
        cands = [
            cand(0, "SELECT name FROM t WHERE x = 1", [("b",)]),
            cand(1, "SELECT   name\n  FROM t   WHERE    y = 2", [("a",), ("c",)]),
            cand(2, "SELECT name FROM t WHERE x=1 AND 1=1", [("b",)]),
            cand(3, "SELECT name FROM t WHERE y = 2 OR 0", [("c",), ("a",)]),
            cand(4, "SELECT name FROM t WHERE y > 2", [("c",), ("a",)]),
            cand(5, "SELECT 'z'", [("z",)]),
        ]
        clusters = cluster_candidates(cands)
        assert [c.members for c in clusters] == [(1, 3, 4), (0, 2), (5,)]
        # Whitespace does not count towards length: #1 and #4 are both 30 characters collapsed,
        # and the lower index wins the tie.
        assert [c.representative for c in clusters] == [1, 0, 5]
        assert len({c.fingerprint for c in clusters}) == 3

    def test_equal_size_clusters_keep_candidate_order(self) -> None:
        clusters = cluster_candidates(
            [cand(3, "SELECT 1", [(1,)]), cand(1, "SELECT 2", [(2,)]), cand(2, "SELECT 3", [(3,)])]
        )
        assert [c.members for c in clusters] == [(1,), (2,), (3,)]

    def test_empty_results_cluster_together_whatever_their_columns(self) -> None:
        clusters = cluster_candidates(
            [
                cand(0, "SELECT a FROM t WHERE 0", [], columns=("a",)),
                cand(1, "SELECT a, b FROM t WHERE 0", [], columns=("a", "b")),
                cand(2, "SELECT a FROM t", [(1,)]),
            ]
        )
        assert [c.members for c in clusters] == [(0, 1), (2,)]

    def test_ordered_candidates_split_from_unordered_ones_with_the_same_rows(self) -> None:
        clusters = cluster_candidates(
            [
                cand(0, "SELECT a FROM t ORDER BY a", [(1,), (2,)], ordered=True),
                cand(1, "SELECT a FROM t ORDER BY a DESC", [(2,), (1,)], ordered=True),
                cand(2, "SELECT a FROM t", [(2,), (1,)]),
                cand(3, "SELECT a FROM t ORDER BY -a", [(2,), (1,)], ordered=True),
            ]
        )
        assert sorted(c.members for c in clusters) == [(0,), (1, 3), (2,)]

    def test_duplicate_candidate_indexes_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate candidate index 1"):
            cluster_candidates([cand(1, "SELECT 1", [(1,)]), cand(1, "SELECT 2", [(2,)])])

    def test_no_candidates_no_clusters(self) -> None:
        assert cluster_candidates([]) == []
