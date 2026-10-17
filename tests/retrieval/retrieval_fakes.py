"""A fake LLM client for retrieval tests: scripted structured answers, controllable embeddings."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence

import numpy as np
from pydantic import BaseModel

from text2sql.config import ReasoningEffort
from text2sql.llm import CallMeta, Message, Structured, Usage
from text2sql.retrieval.types import QuestionAnalysis


def meta(purpose: str = "test", cost: float = 0.0) -> CallMeta:
    return CallMeta(
        purpose=purpose,
        model="fake",
        request_hash="h",
        usage=Usage(0, 0, 0, 0, 0),
        cost_usd=cost,
        latency_s=0.0,
        cache_hit=False,
        priced_usd=cost,
        api_latency_s=0.0,
        service_tier="flex",
    )


def analysis(
    *, literals: Sequence[str] = (), keywords: Sequence[str] = (), skeleton: str = "skeleton"
) -> QuestionAnalysis:
    return QuestionAnalysis(
        literals=list(literals),
        keywords=list(keywords),
        skeleton=skeleton,
        requested_outputs=[],
        complexity="easy",
        may_be_empty=False,
    )


def random_unit(text: str, dims: int = 256) -> list[float]:
    """A fixed pseudo-random direction per text: unrelated texts are nearly orthogonal."""
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
    v = np.random.default_rng(seed).standard_normal(dims)
    return [float(x) for x in v / np.linalg.norm(v)]


type Answer = Callable[[type[BaseModel], Sequence[Message]], BaseModel | Exception]


class FakeLLM:
    """Structured answers from `answer`; embeddings from `vectors`, else a random direction."""

    def __init__(
        self, answer: Answer | None = None, vectors: Mapping[str, Sequence[float]] | None = None
    ) -> None:
        self.answer = answer
        self.vectors = dict(vectors or {})
        self.structured_calls: list[tuple[Sequence[Message], ReasoningEffort, str]] = []
        self.output_caps: list[int | None] = []
        self.embedded: list[list[str]] = []

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
        assert self.answer is not None, "no structured answers configured"
        self.structured_calls.append((messages, effort, purpose))
        self.output_caps.append(max_output_tokens)
        result = self.answer(output, messages)
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, output)
        return Structured(value=result, meta=meta(purpose, 0.001))

    async def embed_with_meta(
        self, texts: Sequence[str], *, purpose: str, dimensions: int | None = None
    ) -> tuple[list[list[float]], CallMeta]:
        assert dimensions == 256
        assert all(texts), "the embeddings API rejects empty strings"
        self.embedded.append(list(texts))
        vectors = [list(self.vectors[t]) if t in self.vectors else random_unit(t) for t in texts]
        return vectors, meta(purpose, 0.0001)
