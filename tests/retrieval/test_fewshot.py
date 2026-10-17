from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import BaseModel
from retrieval_fakes import FakeLLM, analysis, meta

from text2sql.llm import Message, StructuredCallFailed
from text2sql.retrieval.fewshot import FewShotIndex, PoolPair, load_pool_pairs
from text2sql.retrieval.store import build_command
from text2sql.retrieval.types import FewShotExample, QuestionAnalysis

SKELETONS = {
    "How many cats live in Oslo?": "How many <COLUMN> live in <CITY>?",
    "How many dogs live in Rome?": "How many <COLUMN> live in <CITY>?",
    "List owners of pets older than 3": "List <COLUMN> of <COLUMN> older than <NUMBER>",
    "What is the average age of cats?": "What is the average <COLUMN> of <COLUMN>?",
}
AXES = {
    "How many <COLUMN> live in <CITY>?": 0,
    "List <COLUMN> of <COLUMN> older than <NUMBER>": 1,
    "What is the average <COLUMN> of <COLUMN>?": 2,
}


def _axis(i: int, tilt: float = 0.0) -> list[float]:
    v = [0.0] * 256
    v[i], v[3] = 1.0, tilt
    return v


def _pairs() -> list[PoolPair]:
    sqls = [
        "select count(*) from pets where city = 'Oslo'",
        "SELECT COUNT(*) FROM pets WHERE city = 'Rome'",
        "SELECT owner FROM pets WHERE age > 3",
        "SELECT AVG(age) FROM pets",
    ]
    return [
        PoolPair(id=f"p{i}", question=q, evidence="e" if i == 0 else None, sql=s)
        for i, (q, s) in enumerate(zip(SKELETONS, sqls, strict=True))
    ]


def _question(messages: Sequence[Message]) -> str:
    return messages[1].text.split("\n")[0].removeprefix("Question: ")


def _llm(fail: str | None = None) -> FakeLLM:
    def answer(output: type[BaseModel], messages: Sequence[Message]) -> BaseModel | Exception:
        assert output is QuestionAnalysis
        question = _question(messages)
        if question == fail:
            return StructuredCallFailed("refusal", "no", meta=meta(), raw_text=None)
        return analysis(skeleton=SKELETONS[question])

    vectors = {s: _axis(i) for s, i in AXES.items()}
    vectors["How many <COLUMN> are in <CITY>?"] = _axis(0, 0.1)
    return FakeLLM(answer, vectors)


def _build(llm: FakeLLM, pairs: Sequence[PoolPair] | None = None) -> tuple[FewShotIndex, list[str]]:
    return asyncio.run(
        FewShotIndex.build("bird", llm, model="small", effort="none", pairs=pairs or _pairs())
    )


def test_pool_is_masked_with_the_analysis_call_and_sql_in_grammar_spelling() -> None:
    llm = _llm()
    index, skipped = _build(llm)
    assert skipped == []
    assert [i.skeleton for i in index.items] == list(SKELETONS.values())
    assert index.items[0].sql == "SELECT COUNT(*) FROM pets AS T1 WHERE city = 'Oslo'"
    assert index.items[0].evidence == "e"
    assert len(llm.structured_calls) == 4
    assert all("retrieval.analysis question_analysis@" in p for _, _, p in llm.structured_calls)


def test_unparseable_sql_is_kept_as_written() -> None:
    pair = PoolPair(id="x", question="What is the average age of cats?", sql="SELEC nonsense")
    index, _ = _build(_llm(), [pair])
    assert index.items[0].sql == "SELEC nonsense"


def test_failed_masking_skips_only_that_question() -> None:
    index, skipped = _build(_llm(fail="List owners of pets older than 3"))
    assert skipped == ["p2"]
    assert [i.id for i in index.items] == ["p0", "p1", "p3"]


def test_retrieve_ranks_by_skeleton_and_skips_repeats() -> None:
    llm = _llm()
    index, _ = _build(llm)
    found, calls = asyncio.run(
        index.retrieve(skeleton="How many <COLUMN> are in <CITY>?", k=3, llm=llm)
    )
    assert [e.question for e in found[:2]] == [
        "How many cats live in Oslo?",
        "How many dogs live in Rome?",
    ]
    assert len(found) == 3 and len(calls) == 1
    assert isinstance(found[0], FewShotExample)


def test_retrieve_with_k_zero_or_blank_skeleton_makes_no_call() -> None:
    llm = _llm()
    index, _ = _build(llm)
    embedded = len(llm.embedded)
    assert asyncio.run(index.retrieve(skeleton="x", k=0, llm=llm)) == ([], [])
    assert asyncio.run(index.retrieve(skeleton="  ", k=3, llm=llm)) == ([], [])
    assert len(llm.embedded) == embedded


def test_duplicate_sql_is_not_offered_twice() -> None:
    pairs = _pairs()
    twin = PoolPair(id="dup", question="How many dogs live in Rome?", sql=pairs[0].sql)
    llm = _llm()
    index, _ = _build(llm, [pairs[0], twin, pairs[3]])
    found, _ = asyncio.run(
        index.retrieve(skeleton="How many <COLUMN> live in <CITY>?", k=2, llm=llm)
    )
    assert [e.question for e in found] == [pairs[0].question, pairs[3].question]


def test_round_trip_and_missing_index(data_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match=re.escape(build_command("bird"))):
        FewShotIndex.load("bird")
    llm = _llm()
    index, skipped = _build(llm)
    index.save(model="small", effort="none", skipped=skipped)
    loaded = FewShotIndex.load("bird")
    assert loaded.items == index.items and (loaded.vectors == index.vectors).all()


def test_saas_pool_reads_the_eval_builders_file(data_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"fewshot_pool\.jsonl"):
        load_pool_pairs("saas")
    path = data_dir / "saas" / "fewshot_pool.jsonl"
    path.parent.mkdir(parents=True)
    row = {"id": "s1", "question": "Q?", "sql": "SELECT 1", "difficulty": "easy", "provenance": {}}
    path.write_text(json.dumps(row) + "\n\n", encoding="utf-8")
    assert load_pool_pairs("saas") == [PoolPair(id="s1", question="Q?", sql="SELECT 1")]
