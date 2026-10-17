"""Test doubles for the selection tests: candidate builders and a scripted structured-output
client. Nothing here touches the network."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from text2sql.llm import CallMeta, Message, Structured, StructuredCallFailed, Usage
from text2sql.selection import ExecutedCandidate


def cand(
    index: int,
    sql: str,
    rows: Iterable[Sequence[object]] = (),
    *,
    strategy: str = "direct_full",
    ordered: bool = False,
    truncated: bool = False,
    columns: tuple[str, ...] = ("c1",),
) -> ExecutedCandidate:
    return ExecutedCandidate(
        index=index,
        strategy=strategy,
        sql=sql,
        columns=columns,
        rows=tuple(tuple(r) for r in rows),
        ordered=ordered,
        truncated=truncated,
    )


def meta(purpose: str, n: int) -> CallMeta:
    return CallMeta(
        purpose=purpose,
        model="fake",
        request_hash=f"{n:064d}",
        usage=Usage(
            input_tokens=100,
            cached_tokens=0,
            cache_write_tokens=0,
            output_tokens=10,
            reasoning_tokens=0,
        ),
        cost_usd=0.001,
        latency_s=0.0,
        cache_hit=False,
        priced_usd=0.001,
        api_latency_s=0.0,
        service_tier="flex",
    )


@dataclass(frozen=True)
class Call:
    model: str
    messages: tuple[Message, ...]
    output: type[BaseModel]
    effort: str
    purpose: str

    @property
    def user(self) -> str:
        return self.messages[-1].text

    @property
    def developer(self) -> str:
        return self.messages[0].text


REFUSE = object()
"""Reply sentinel: the call fails with StructuredCallFailed carrying that call's CallMeta."""

Reply = Callable[[Call], object]


@dataclass
class FakeLLM:
    """Answers `structured` with `reply(call)` (a model instance, or REFUSE). Each call gets a
    distinct CallMeta so tests can check that every call's cost is returned."""

    reply: Reply
    calls: list[Call] = field(default_factory=list)
    metas: list[CallMeta] = field(default_factory=list)

    async def structured(self, *, model, messages, output, effort, purpose, sample=0) -> Any:
        call = Call(model, tuple(messages), output, effort, purpose)
        self.calls.append(call)
        call_meta = meta(purpose, len(self.calls))
        self.metas.append(call_meta)
        value = self.reply(call)
        if value is REFUSE:
            raise StructuredCallFailed("refusal", "refused", meta=call_meta, raw_text=None)
        return Structured(value=value, meta=call_meta)


def judge_pair(call: Call) -> tuple[str, str]:
    """The (A, B) SQL strings shown in a judge prompt."""
    a = re.search(r"<candidate_a>\n<sql>\n(.*?)\n</sql>", call.user, re.S)
    b = re.search(r"<candidate_b>\n<sql>\n(.*?)\n</sql>", call.user, re.S)
    assert a and b
    return a.group(1), b.group(1)


def checker_candidates(call: Call) -> dict[int, str]:
    """Candidate number -> SQL as shown in a unit-test checker prompt."""
    found = re.findall(r'<candidate number="(\d+)">\n<sql>\n(.*?)\n</sql>', call.user, re.S)
    return {int(n): sql for n, sql in found}


def checker_test(call: Call) -> str:
    found = re.search(r"<unit_test>\n(.*?)\n</unit_test>", call.user, re.S)
    assert found
    return found.group(1)
