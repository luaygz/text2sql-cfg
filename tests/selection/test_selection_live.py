"""Live smoke for the LLM selectors on two real BIRD dev disagreements.

Each case runs the gold SQL and a plausible wrong query (twice, in two spellings, so the wrong
answer wins the vote 2 to 1) and checks that the pairwise judge and the unit tester both pick
gold. Costs about $0.007 on flex (ADR-013); responses go to the normal response cache, so a
rerun replays for free. Runs only with T2SQL_LIVE_TESTS=1, an API key and the BIRD data; run it
with `-s` to see the per-call cost table.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import pytest

from text2sql.catalog import load_catalog, render_schema
from text2sql.config import Settings
from text2sql.data.bird import bird_db_path, bird_dir, load_split
from text2sql.execution import SandboxedExecutor
from text2sql.llm import LLMClient, RunBudget
from text2sql.selection import (
    ExecutedCandidate,
    Selection,
    cluster_candidates,
    judge_select,
    majority_vote,
    unit_test_select,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.bird,
    pytest.mark.skipif(
        os.environ.get("T2SQL_LIVE_TESTS") != "1", reason="set T2SQL_LIVE_TESTS=1 to call OpenAI"
    ),
    pytest.mark.skipif(
        not (bird_dir() / "mini_dev_sqlite.json").is_file(), reason="BIRD data absent"
    ),
]

SMOKE_CAP_USD = 0.20


@dataclass(frozen=True)
class Case:
    question_id: int
    wrong: tuple[str, str]
    """Two spellings of the same wrong answer."""


CASES = [
    # The evidence redefines "highest longitude" as the largest absolute value.
    Case(
        82,
        (
            "SELECT GSoffered FROM schools ORDER BY Longitude DESC LIMIT 1",
            "SELECT T1.GSoffered FROM schools AS T1 ORDER BY T1.Longitude DESC LIMIT 1",
        ),
    ),
    # Integer division truncates the percentage to 0.
    Case(
        368,
        (
            "SELECT SUM(CASE WHEN borderColor = 'borderless' THEN 1 ELSE 0 END) * 100 / COUNT(id) "
            "FROM cards",
            "SELECT COUNT(CASE WHEN borderColor = 'borderless' THEN id END) * 100 / COUNT(id) "
            "FROM cards",
        ),
    ),
]


def _settings() -> Settings:
    real = Settings()
    if real.openai_api_key is None:
        pytest.skip("no OPENAI_API_KEY")
    # The budget reserves max_output_tokens at full price per call in flight; 8,000 leaves
    # room for low-effort reasoning while two concurrent judge calls fit under the cap.
    return real.model_copy(
        update={
            "max_spend_usd": min(real.max_spend_usd, SMOKE_CAP_USD),
            "max_output_tokens": 8000,
            "offline": False,
        }
    )


def _print_costs(label: str, selection: Selection) -> None:
    for meta in selection.calls:
        u = meta.usage
        print(
            f"{label:<14} {meta.purpose:<50} {meta.model:<12} in={u.input_tokens:>5} "
            f"out={u.output_tokens:>5} (reasoning {u.reasoning_tokens:>4}) "
            f"priced=${meta.priced_usd:.5f} billed=${meta.cost_usd:.5f} hit={meta.cache_hit}"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"q{c.question_id}")
def test_judge_and_unit_tests_pick_gold_over_the_majority(case: Case) -> None:
    example = next(e for e in load_split("dev") if int(e.question_id) == case.question_id)
    settings = _settings()
    catalog = load_catalog(example.db_id)
    with SandboxedExecutor(bird_db_path(example.db_id)) as executor:
        sqls = [*case.wrong, example.gold_sql]
        strategies = ["direct_full", "query_plan", "divide_conquer"]
        cands = [
            ExecutedCandidate.from_result(
                index=i, strategy=strategy, sql=sql, result=executor.execute(sql)
            )
            for i, (strategy, sql) in enumerate(zip(strategies, sqls, strict=True))
        ]
    gold = 2
    clusters = cluster_candidates(cands)
    assert [c.members for c in clusters] == [(0, 1), (2,)]
    assert majority_vote(cands, clusters, strategy_rank={}).index == clusters[0].representative

    common = {
        "question": example.question,
        "evidence": example.evidence,
        "schema_text": render_schema(catalog),
        "catalog": catalog,
        "effort": settings.generator_effort,
    }

    async def run() -> tuple[Selection, Selection]:
        async with LLMClient(settings, budget=RunBudget.from_settings(settings)) as llm:
            judged = await judge_select(
                llm, cands, clusters, model=settings.generator_model, **common
            )
            tested = await unit_test_select(
                llm,
                cands,
                clusters,
                writer_model=settings.generator_model,
                checker_model=settings.small_model,
                **common,
            )
            return judged, tested

    judged, tested = asyncio.run(run())
    _print_costs(f"q{case.question_id} judge", judged)
    _print_costs(f"q{case.question_id} unit_test", tested)
    for note in (*judged.notes, *tested.notes):
        print(f"  {note}")
    assert len(judged.calls) == 2
    assert len(tested.calls) == 5
    assert judged.index == gold, judged.notes
    assert tested.index == gold, tested.notes
    assert sum(m.cost_usd for m in (*judged.calls, *tested.calls)) < SMOKE_CAP_USD
