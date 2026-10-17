from __future__ import annotations

import asyncio
import gzip
import json
import sqlite3
import zlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from llm_fakes import FakeAPI, embeddings_json, response_json, tool_call_item
from typer.testing import CliRunner

from text2sql.config import Settings, get_settings
from text2sql.grammar import SqlGrammar
from text2sql.llm import LLMClient, Message
from text2sql.llm.cache import CachedEmbedding, GrammarVerdict, ResponseCache
from text2sql.llm.cli import app as cache_cli
from text2sql.llm.shards import (
    CACHE_FILENAME,
    export_shards,
    import_shards,
    open_cache,
    shard_dir,
)

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)
MakeClient = Callable[..., LLMClient]


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("text2sql.llm.cache._now", lambda: "2026-10-16T09:00:00+00:00")


def store(directory: Path) -> ResponseCache:
    return ResponseCache(directory / CACHE_FILENAME)


def fill(cache: ResponseCache, *, reverse: bool = False) -> None:
    """One row of every kind, including a float32-only vector and non-ASCII text."""
    steps: list[Callable[[], object]] = [
        lambda: cache.put_response(
            "r1",
            model="gpt-6-luna",
            payload={"output": "SELECT ünïcode", "n": 0.1},
            api_latency_s=1.5,
        ),
        lambda: cache.put_response(
            "r2", model="gpt-6.1-sol", payload={"x": [1, 2]}, api_latency_s=2.0
        ),
        lambda: cache.put_embeddings(
            "text-embedding-3-small",
            {
                "e1": CachedEmbedding([0.5, -0.25], 3, 0.1),
                "e2": CachedEmbedding([0.1, 0.3], 2, 0.2),
            },
        ),
        lambda: cache.put_grammar_verdict("fp-ok", GrammarVerdict(True, None, "gpt-6-luna")),
        lambda: cache.put_grammar_verdict("fp-bad", GrammarVerdict(False, "fuel", "gpt-6-luna")),
        lambda: cache.put_flagged("f1", model="gpt-6.1-sol", message="flagged"),
    ]
    for step in reversed(steps) if reverse else steps:
        step()


def tables(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    """Every cached row, with response payloads decompressed."""
    with sqlite3.connect(path) as db:
        dump = {
            name: sorted(db.execute(f"SELECT * FROM {name}"))
            for name in ("embeddings", "flagged_requests", "grammar_verdicts")
        }
        dump["responses"] = sorted(
            (*row[:4], json.loads(zlib.decompress(row[4])))
            for row in db.execute("SELECT * FROM responses")
        )
    return dump


def shard_lines(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def test_round_trip_preserves_every_table(tmp_path: Path) -> None:
    source = store(tmp_path / "a")
    fill(source)
    written = export_shards(source, tmp_path / "shards", now=NOW)
    assert len(written) == 1
    assert written[0].rows == 7
    assert written[0].path.name.startswith("20261016-120000-")
    kinds = [line["kind"] for line in shard_lines(written[0].path)]
    assert kinds == sorted(kinds)

    copy = store(tmp_path / "b")
    imported = import_shards(copy, tmp_path / "shards")
    assert [(s.rows, s.new_rows) for s in imported] == [(7, 7)]
    assert tables(copy.path) == tables(source.path)
    assert copy.get_embeddings(["e2"])["e2"].vector == source.get_embeddings(["e2"])["e2"].vector
    assert copy.get_grammar_verdict("fp-bad") == GrammarVerdict(False, "fuel", "gpt-6-luna")
    assert copy.get_flagged("f1") == "flagged"


def test_export_and_import_are_idempotent(tmp_path: Path) -> None:
    shards = tmp_path / "shards"
    source = store(tmp_path / "a")
    fill(source)
    export_shards(source, shards, now=NOW)
    assert export_shards(source, shards, now=NOW) == []
    assert import_shards(source, shards) == []

    copy = store(tmp_path / "b")
    assert len(import_shards(copy, shards)) == 1
    assert import_shards(copy, shards) == []
    assert export_shards(copy, shards, now=NOW) == []
    assert len(list(shards.iterdir())) == 1


def test_later_rows_and_a_later_rejection_go_to_a_new_shard(tmp_path: Path) -> None:
    shards = tmp_path / "shards"
    source = store(tmp_path / "a")
    fill(source)
    export_shards(source, shards, now=NOW)
    source.put_response("r3", model="gpt-6-luna", payload={"late": True}, api_latency_s=1.0)
    source.put_grammar_verdict("fp-ok", GrammarVerdict(False, "now rejected", "gpt-6.1-sol"))

    (second,) = export_shards(source, shards, now=datetime(2026, 10, 17, tzinfo=UTC))
    assert sorted((line["kind"], line.get("key")) for line in shard_lines(second.path)) == [
        ("grammar_verdicts", None),
        ("responses", "r3"),
    ]
    copy = store(tmp_path / "b")
    assert [s.rows for s in import_shards(copy, shards)] == [7, 2]
    assert copy.get_grammar_verdict("fp-ok") == GrammarVerdict(False, "now rejected", "gpt-6.1-sol")
    assert tables(copy.path) == tables(source.path)


@pytest.mark.usefixtures("frozen_clock")
def test_shard_bytes_depend_only_on_the_rows(tmp_path: Path) -> None:
    first, second = store(tmp_path / "a"), store(tmp_path / "b")
    fill(first)
    fill(second, reverse=True)
    (one,) = export_shards(first, tmp_path / "s1", now=NOW)
    (two,) = export_shards(second, tmp_path / "s2", now=NOW)
    assert one.path.name == two.path.name
    assert one.path.read_bytes() == two.path.read_bytes()


def test_large_exports_split_into_shards_near_the_size_limit(tmp_path: Path) -> None:
    source = store(tmp_path / "a")
    rng = np.random.default_rng(0)
    source.put_embeddings(
        "text-embedding-3-small",
        {f"k{i:03d}": CachedEmbedding(rng.normal(size=1536).tolist(), 5, 0.1) for i in range(300)},
    )
    limit = 500_000
    written = export_shards(source, tmp_path / "shards", max_bytes=limit, now=NOW)
    assert len(written) >= 3
    assert all(w.size_bytes < limit + 200_000 for w in written)
    assert sum(w.rows for w in written) == 300
    copy = store(tmp_path / "b")
    import_shards(copy, tmp_path / "shards")
    assert tables(copy.path) == tables(source.path)


def test_a_bad_shard_imports_nothing(tmp_path: Path) -> None:
    shards = tmp_path / "shards"
    shards.mkdir()
    good = {"kind": "flagged_requests", "key": "f", "model": "m", "created_at": "t", "message": "x"}
    with gzip.open(shards / "20261016-000000-deadbeef.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(good) + "\n" + json.dumps({"kind": "secrets", "key": "k"}) + "\n")
    cache = store(tmp_path / "a")
    with pytest.raises(ValueError, match="not a cache row"):
        import_shards(cache, shards)
    assert cache.get_flagged("f") is None
    assert cache.shard_names() == set()


async def _ask(client: LLMClient, grammar: SqlGrammar) -> str:
    result = await client.sql_call(
        model="gpt-6-luna",
        messages=[Message("user", "names")],
        grammar=grammar,
        effort="low",
        purpose="test.shards",
    )
    vectors = await client.embed(["alpha"], purpose="test.shards")
    return f"{result.output.text} {vectors[0]}"


def test_offline_replay_works_from_shards_alone(
    make_client: MakeClient, fake_api: FakeAPI, grammar: SqlGrammar, settings: Settings
) -> None:
    fake_api.reply(response_json([tool_call_item("SELECT name FROM singer")]))
    fake_api.reply(embeddings_json([[0.5, 0.25]]))
    live = asyncio.run(_ask(make_client(), grammar))

    cache = store(settings.cache_dir)
    export_shards(cache, shard_dir(settings.cache_dir), now=NOW)
    cache.close()
    (settings.cache_dir / CACHE_FILENAME).unlink()

    replayed = asyncio.run(_ask(make_client(offline=True, openai_api_key=None), grammar))
    assert replayed == live
    assert len(fake_api.requests) == 2
    assert (settings.cache_dir / CACHE_FILENAME).exists()


def test_open_cache_picks_up_shards_added_after_the_store_was_built(tmp_path: Path) -> None:
    shards = shard_dir(tmp_path / "clone")
    origin = store(tmp_path / "origin")
    fill(origin)
    export_shards(origin, shards, now=NOW)
    open_cache(tmp_path / "clone").close()

    origin.put_flagged("f2", model="m", message="later")
    export_shards(origin, shards, now=datetime(2026, 10, 17, tzinfo=UTC))
    clone = open_cache(tmp_path / "clone")
    assert clone.get_flagged("f2") == "later"
    assert clone.shard_names() == {p.name for p in shards.iterdir()}


@pytest.fixture
def cli_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    yield tmp_path / "cache"
    get_settings.cache_clear()


def test_cli_export_then_import(cli_cache_dir: Path) -> None:
    cache = store(cli_cache_dir)
    fill(cache)
    cache.close()
    runner = CliRunner()

    exported = runner.invoke(cache_cli, ["export"])
    assert exported.exit_code == 0, exported.output
    assert "7 rows" in exported.output
    assert "Nothing to export" in runner.invoke(cache_cli, ["export"]).output

    (cli_cache_dir / CACHE_FILENAME).unlink()
    imported = runner.invoke(cache_cli, ["import"])
    assert imported.exit_code == 0, imported.output
    assert "7 rows, 7 new" in imported.output
    assert "Up to date" in runner.invoke(cache_cli, ["import"]).output
