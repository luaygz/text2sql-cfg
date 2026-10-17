"""Candidate selection (ADR-008 stage 8, ADR-013): cluster executed candidates by result, then
pick one by majority vote, a pairwise LLM judge, or LLM-written unit tests."""

from text2sql.selection.clustering import (
    Cluster,
    ExecutedCandidate,
    cluster_candidates,
    has_top_level_order_by,
    result_fingerprint,
    sql_length,
)
from text2sql.selection.judge import PairwiseVerdict, judge_select
from text2sql.selection.unit_tests import UnitTests, UnitTestVerdicts, unit_test_select
from text2sql.selection.vote import Selection, majority_vote

__all__ = [
    "Cluster",
    "ExecutedCandidate",
    "PairwiseVerdict",
    "Selection",
    "UnitTestVerdicts",
    "UnitTests",
    "cluster_candidates",
    "has_top_level_order_by",
    "judge_select",
    "majority_vote",
    "result_fingerprint",
    "sql_length",
    "unit_test_select",
]
