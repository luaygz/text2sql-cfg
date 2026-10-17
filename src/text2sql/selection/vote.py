"""The `Selection` result, majority vote, and the tie-break order every selector shares.

Clusters are ranked by score (votes, pairwise wins or unit tests passed, depending on the
selector), then cluster size, then the best rank among the strategies that produced the
cluster's members (lower is better; strategies missing from the mapping rank last), then the
representative's SQL length, then the representative's index. ADR-013 records why.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from text2sql.llm import CallMeta
from text2sql.selection.clustering import Cluster, ExecutedCandidate, sql_length


@dataclass(frozen=True)
class Selection:
    """The chosen candidate (`None` when nothing executed) and how it was chosen.

    `vote_share` is the chosen cluster's size over all executed candidates. `scores` maps each
    cluster representative to its score under `method`. `notes` are human-readable judge
    reasons or unit-test verdicts for the trace.
    """

    index: int | None
    method: str
    vote_share: float
    n_clusters: int
    scores: Mapping[int, float]
    calls: tuple[CallMeta, ...]
    notes: tuple[str, ...] = ()


def majority_vote(
    cands: Sequence[ExecutedCandidate],
    clusters: Sequence[Cluster],
    *,
    strategy_rank: Mapping[str, int],
    prefer_non_empty: bool = True,
) -> Selection:
    """Pick the largest cluster. With `prefer_non_empty`, a cluster of empty results loses to
    any cluster that returned rows, and wins only when every candidate returned nothing."""
    scores = {c.representative: float(len(c.members)) for c in clusters}
    return choose(
        cands,
        clusters,
        scores,
        method="vote",
        strategy_rank=strategy_rank,
        demote_empty=prefer_non_empty,
    )


def choose(
    cands: Sequence[ExecutedCandidate],
    clusters: Sequence[Cluster],
    scores: Mapping[int, float],
    *,
    method: str,
    strategy_rank: Mapping[str, int] | None = None,
    calls: Sequence[CallMeta] = (),
    notes: Sequence[str] = (),
    demote_empty: bool = False,
) -> Selection:
    """The best cluster's representative under `scores` (keyed by representative) and the
    shared tie-break order."""
    by_index = {c.index: c for c in cands}
    ranks = strategy_rank or {}

    def key(cluster: Cluster) -> tuple[bool, float, int, float, int, int]:
        rep = by_index[cluster.representative]
        empty = demote_empty and not rep.rows
        best_rank = min(
            (ranks.get(by_index[m].strategy, math.inf) for m in cluster.members),
            default=math.inf,
        )
        return (
            empty,
            -scores[cluster.representative],
            -len(cluster.members),
            best_rank,
            sql_length(rep.sql),
            rep.index,
        )

    best = min(clusters, key=key, default=None)
    return Selection(
        index=None if best is None else best.representative,
        method=method,
        vote_share=0.0 if best is None else len(best.members) / len(cands),
        n_clusters=len(clusters),
        scores=dict(scores),
        calls=tuple(calls),
        notes=tuple(notes),
    )
