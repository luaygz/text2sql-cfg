"""A scripted stand-in for `LLMClient`, a tiny SQLite database and stubs for the retrieval
indexes, so pipeline tests run the real generation, guard and selection code offline."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from text2sql.catalog import Catalog, build_catalog
from text2sql.config import PRESETS, PipelineConfig, QueryMode, ReasoningEffort, Settings
from text2sql.grammar import GrammarRejection, SqlGrammar
from text2sql.llm import (
    CallMeta,
    GrammarCallFailed,
    LLMClient,
    Message,
    SqlToolCall,
    Structured,
    Usage,
)
from text2sql.pipeline import (
    Answer,
    DatabaseResources,
    Pipeline,
    PipelineEvent,
    PipelineTrace,
    Request,
)
from text2sql.pipeline.events import CollectingEventLog
from text2sql.retrieval import (
    ColumnIndex,
    FewShotExample,
    LinkResult,
    QuestionAnalysis,
    ValueMatches,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_ID = "concerts"
QUESTION = "Which singers are from France?"

SINGERS = [
    (1, "Ada", "France", 31),
    (2, "Bo", "Spain", 25),
    (3, "Cy", "France", 40),
    (4, "Di", "Japan", 22),
]

# Grammar spelling (ADR-005): upper-case keywords, T1.. aliases, single spaces.
ALL_NAMES = "SELECT T1.name FROM singer AS T1"
FRENCH = "SELECT T1.name FROM singer AS T1 WHERE T1.country = 'France'"
OLDEST = "SELECT T1.name FROM singer AS T1 ORDER BY T1.age DESC LIMIT 1"
COUNT = "SELECT COUNT(*) FROM singer AS T1"
NOBODY = "SELECT T1.name FROM singer AS T1 WHERE T1.country = 'Peru'"
UNKNOWN_ALIAS = "SELECT T2.name FROM singer AS T1"
"""Parses under the grammar, rejected by the validator (layer 2): a repair trigger."""
OFF_GRAMMAR = "SELECT nickname FROM singer"
"""No such column: the grammar cannot produce it, so the local re-parse fails."""


def with_limit(sql: str, limit: int = 10) -> str:
    return f"{sql} LIMIT {limit}"


def make_database(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE singer (
                singer_id INTEGER PRIMARY KEY, name TEXT, country TEXT, age INTEGER
            );
            CREATE TABLE concert (
                concert_id INTEGER PRIMARY KEY,
                singer_id INTEGER REFERENCES singer(singer_id),
                year INTEGER
            );
            """
        )
        conn.executemany("INSERT INTO singer VALUES (?, ?, ?, ?)", SINGERS)
        conn.executemany(
            "INSERT INTO concert VALUES (?, ?, ?)", [(1, 1, 2020), (2, 1, 2021), (3, 3, 2022)]
        )
    conn.close()
    return path


def make_resources(
    db_path: Path,
    events_path: Path,
    *,
    mode: QueryMode = QueryMode.BENCHMARK,
    value_index: Any = None,
) -> DatabaseResources:
    catalog = build_catalog(db_path, DB_ID)
    return DatabaseResources(
        db_id=DB_ID,
        dataset="bird",
        mode=mode,
        db_path=db_path,
        catalog=catalog,
        full_schema=catalog.schema(),
        policy=None,
        event_log=CollectingEventLog(events_path),
        value_index=value_index,
        column_index=cast(ColumnIndex, object()),
    )


def linker(keep: Mapping[str, Sequence[str] | None]) -> Callable[..., Any]:
    """A `link_schema` stand-in that links the `keep` columns: one embedding call, then two
    concurrent selection passes, as the real one reports them."""

    async def link_schema(llm: object, catalog: Catalog, **_: object) -> LinkResult:
        schema = catalog.schema().subset(keep)
        return LinkResult(
            schema=schema,
            columns=frozenset((t.name, c.name) for t in schema.tables for c in t.columns),
            calls=(
                call_meta("retrieval.linking.embed", "embedding", latency=0.5),
                call_meta("retrieval.linking", "gpt-6-luna", latency=2.0),
                call_meta("retrieval.linking", "gpt-6-luna", latency=3.0),
            ),
        )

    return link_schema


def call_meta(purpose: str, model: str, *, latency: float = 1.0, cost: float = 0.01) -> CallMeta:
    return CallMeta(
        purpose=purpose,
        model=model,
        request_hash=f"hash-{purpose}",
        usage=Usage(100, 0, 0, 20, 10),
        cost_usd=cost,
        latency_s=latency,
        cache_hit=False,
        priced_usd=cost,
        api_latency_s=latency,
        service_tier="flex",
    )


def analysis(
    *, complexity: str = "easy", may_be_empty: bool = False, skeleton: str = "names of <column>"
) -> QuestionAnalysis:
    return QuestionAnalysis(
        literals=["France"],
        keywords=["singer", "name"],
        skeleton=skeleton,
        requested_outputs=["name"],
        complexity=complexity,  # type: ignore[arg-type]
        may_be_empty=may_be_empty,
    )


type Reply = str | Exception
"""Tool input text (SQL or `ABSTAIN: ...`), or an exception for the call to raise."""


@dataclass
class FakeLLM:
    """Scripted per candidate: `sql[(strategy, sample)]` lists the replies to the first call and
    to each repair in turn. Repair calls are routed to their candidate by the conversation
    history they continue. Structured calls are answered by output type."""

    settings: Settings
    sql: Mapping[tuple[str, int], Sequence[Reply]] = field(default_factory=dict)
    structured_values: dict[type[BaseModel], BaseModel | Exception] = field(default_factory=dict)
    """Reply per output type, or an exception to raise."""
    latencies: Mapping[str, float] = field(default_factory=dict)
    """Per-strategy API latency reported in CallMeta (default 1.0 s)."""
    purposes: list[str] = field(default_factory=list)
    messages: list[list[Message]] = field(default_factory=list)
    """Input messages of every call, in call order."""
    feedback: list[str] = field(default_factory=list)
    """Tool outputs sent with repair calls, in order."""

    async def sql_call(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        grammar: SqlGrammar,
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        history: Sequence[dict[str, Any]] = (),
        tool_description: str | None = None,
        max_output_tokens: int | None = None,
    ) -> SqlToolCall:
        self.purposes.append(purpose)
        self.messages.append(list(messages))
        label = purpose.split("[", 1)[0]
        stage, _, rest = label.partition(".")
        strategy, _, attempt_text = rest.partition("#")
        if history:
            strategy, sample_text, _ = str(history[0]["call_id"]).split("/")
            sample = int(sample_text)
            outputs = [i for i in history if i.get("type") == "custom_tool_call_output"]
            self.feedback.append(str(outputs[-1]["output"]))
        attempt = int(attempt_text) if stage == "repair" else 0
        reply = self.sql[(strategy, sample)][attempt]
        meta = call_meta(purpose, model, latency=self.latencies.get(strategy, 1.0))
        if isinstance(reply, Exception):
            raise reply
        try:
            output = grammar.parse(reply)
        except GrammarRejection as exc:
            raise GrammarCallFailed("local_parse", str(exc), meta=meta, raw_input=reply) from exc
        call_id = f"{strategy}/{sample}/{attempt}"
        item = {"type": "custom_tool_call", "call_id": call_id, "name": "sql_query", "input": reply}
        return SqlToolCall(
            output=output, raw_input=reply, call_id=call_id, history_items=(item,), meta=meta
        )

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        max_output_tokens: int | None = None,
    ) -> Structured[T]:
        self.purposes.append(purpose)
        self.messages.append(list(messages))
        value = self.structured_values[output]
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, output)
        return Structured(value=value, meta=call_meta(purpose, model))

    async def embed(self, texts: Sequence[str], *, purpose: str) -> list[list[float]]:
        raise AssertionError("pipeline tests stub every embedding user")

    def calls_for(self, prefix: str) -> list[str]:
        return [p for p in self.purposes if p.startswith(prefix)]


def grammar_failure(reason: str = "no_tool_call") -> GrammarCallFailed:
    return GrammarCallFailed(
        reason,  # type: ignore[arg-type]
        "scripted failure",
        meta=call_meta("generate.scripted", "gpt-test"),
    )


@dataclass
class StubValueIndex:
    matches: ValueMatches = field(default_factory=dict)

    async def match(
        self, analysis: QuestionAnalysis, *, question: str, llm: object
    ) -> tuple[ValueMatches, list[CallMeta]]:
        return self.matches, [call_meta("retrieval.values", "embedding", latency=0.25)]


@dataclass
class StubFewShotIndex:
    examples: list[FewShotExample] = field(default_factory=list)
    skeletons: list[str] = field(default_factory=list)

    async def retrieve(
        self, *, skeleton: str, k: int, llm: object
    ) -> tuple[list[FewShotExample], list[CallMeta]]:
        self.skeletons.append(skeleton)
        return self.examples[:k], [call_meta("retrieval.fewshot", "embedding", latency=0.25)]


def config(**changes: Any) -> PipelineConfig:
    """The baseline preset with `changes` applied and re-validated."""
    return PipelineConfig.model_validate({**PRESETS["baseline"].model_dump(), **changes})


def request(mode: QueryMode = QueryMode.BENCHMARK, **changes: Any) -> Request:
    fields: dict[str, Any] = {
        "question": QUESTION,
        "evidence": None,
        "db_id": DB_ID,
        "mode": mode,
        "question_id": "q1",
    }
    fields.update(changes)
    return Request(**fields)


def run_pipeline(
    llm: FakeLLM,
    cfg: PipelineConfig,
    resources: DatabaseResources,
    req: Request | None = None,
    on_event: Callable[[PipelineEvent], None] | None = None,
) -> tuple[Answer, PipelineTrace]:
    pipeline = Pipeline(cast(LLMClient, llm), cfg, settings=llm.settings, resources=[resources])
    return asyncio.run(pipeline.run(req or request(resources.mode), on_event=on_event))
