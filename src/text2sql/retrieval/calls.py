"""The parts of `LLMClient` retrieval uses: capped structured calls and unit-length embeddings.

Structured calls carry an output cap. With effort `none` and a strict JSON schema, gpt-6-luna
once wrote a complete JSON object and then about 25,000 tokens of newlines and braces until the
global output limit, at 100 times the normal price of the call. A cap bounds that, and since
the object itself was complete, it is recovered from the raw text of the cut-off response.

Every retrieval embedding is requested at `EMBEDDING_DIMENSIONS`: text-embedding-3 models accept a
`dimensions` parameter that shortens the vector "without the embedding losing its
concept-representing properties" (OpenAI embeddings guide), and the response cache, which is
committed, stores every vector. Vectors are re-normalized locally so a dot product is the cosine.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ValidationError

from text2sql.config import ReasoningEffort
from text2sql.llm import CallMeta, Message, Structured, StructuredCallFailed

EMBEDDING_DIMENSIONS = 256

type Matrix = npt.NDArray[np.float32]


class StructuredLLM(Protocol):
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
    ) -> Structured[T]: ...


class EmbeddingLLM(Protocol):
    async def embed_with_meta(
        self, texts: Sequence[str], *, purpose: str, dimensions: int | None = None
    ) -> tuple[list[list[float]], CallMeta]: ...


class RetrievalLLM(StructuredLLM, EmbeddingLLM, Protocol):
    """Structured calls and embeddings: what schema linking and pool building need."""


async def structured_call[T: BaseModel](
    llm: StructuredLLM,
    *,
    model: str,
    messages: Sequence[Message],
    output: type[T],
    effort: ReasoningEffort,
    purpose: str,
    max_output_tokens: int,
) -> Structured[T]:
    """`llm.structured` with an output cap; a response cut off after a complete JSON object
    still yields that object. Other failures raise StructuredCallFailed."""
    try:
        return await llm.structured(
            model=model,
            messages=messages,
            output=output,
            effort=effort,
            purpose=purpose,
            max_output_tokens=max_output_tokens,
        )
    except StructuredCallFailed as exc:
        value = _leading_object(exc, output)
        if value is None:
            raise
        return Structured(value=value, meta=exc.meta)


def _leading_object[T: BaseModel](exc: StructuredCallFailed, output: type[T]) -> T | None:
    if exc.reason != "incomplete" or not exc.raw_text:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(exc.raw_text.lstrip())
        return output.model_validate(obj)
    except (json.JSONDecodeError, ValidationError):
        return None


def unit_rows(vectors: Sequence[Sequence[float]]) -> Matrix:
    m = np.asarray(vectors, dtype=np.float32).reshape(len(vectors), -1)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(norms == 0, 1, norms)).astype(np.float32)


async def embed(
    llm: EmbeddingLLM, texts: Sequence[str], *, purpose: str
) -> tuple[Matrix, CallMeta]:
    """Unit-length embeddings of `texts` (one row each, same order)."""
    vectors, meta = await llm.embed_with_meta(
        list(texts), purpose=purpose, dimensions=EMBEDDING_DIMENSIONS
    )
    return unit_rows(vectors), meta
