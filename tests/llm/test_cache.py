from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from text2sql.llm.cache import (
    CachedEmbedding,
    GrammarVerdict,
    ResponseCache,
    pack_vector,
    request_key,
    unpack_vector,
)


def base_request() -> dict[str, Any]:
    return {
        "model": "gpt-6.1-sol",
        "input": [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": "schema ...",
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": "How many singers?"}]},
        ],
        "tools": [
            {
                "type": "custom",
                "name": "sql_query",
                "description": "d",
                "format": {"type": "grammar", "syntax": "lark", "definition": 'start: "a"'},
            }
        ],
        "tool_choice": {"type": "custom", "name": "sql_query"},
        "parallel_tool_calls": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 2000,
        "service_tier": "flex",
        "prompt_cache_options": {"mode": "explicit"},
        "store": False,
    }


def test_key_ignores_dict_order() -> None:
    request = base_request()
    reordered = dict(reversed(list(request.items())))
    reordered["tools"] = [dict(reversed(list(request["tools"][0].items())))]
    assert request_key("responses", reordered) == request_key("responses", request)


def _set(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    request = copy.deepcopy(base_request())
    target: Any = request
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return request


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("model",), "gpt-6-luna"),
        (("input", 1, "content", 0, "text"), "How many songs?"),
        (("tools", 0, "format", "definition"), 'start: "b"'),
        (("tools", 0, "description"), "other"),
        (("tool_choice",), "auto"),
        (("reasoning", "effort"), "high"),
        (("max_output_tokens",), 4000),
        (("text",), {"format": {"type": "text"}}),
    ],
)
def test_key_changes_with_anything_the_model_sees(
    path: tuple[str | int, ...], value: object
) -> None:
    assert request_key("responses", _set(path, value)) != request_key("responses", base_request())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("service_tier",), "default"),
        (("prompt_cache_options",), {"mode": "implicit"}),
        (("store",), True),
        (("input", 0, "content", 0), {"type": "input_text", "text": "schema ..."}),
    ],
)
def test_key_ignores_serving_options(path: tuple[str | int, ...], value: object) -> None:
    assert request_key("responses", _set(path, value)) == request_key("responses", base_request())


def test_key_separates_samples_and_endpoints() -> None:
    request = base_request()
    keys = {
        request_key("responses", request, 0),
        request_key("responses", request, 1),
        request_key("embeddings", request, 0),
    }
    assert len(keys) == 3


def test_first_writer_wins_and_rows_persist(tmp_path: Path) -> None:
    path = tmp_path / "responses.sqlite"
    cache = ResponseCache(path)
    first = cache.put_response("k", model="m", payload={"answer": 1}, api_latency_s=2.5)
    second = cache.put_response("k", model="m", payload={"answer": 2}, api_latency_s=9.0)
    assert first.payload == second.payload == {"answer": 1}
    cache.close()

    reopened = ResponseCache(path)
    stored = reopened.get_response("k")
    assert stored is not None
    assert stored.payload == {"answer": 1}
    assert stored.api_latency_s == 2.5
    assert reopened.get_response("other") is None
    reopened.close()


def test_embeddings_round_trip_and_first_writer_wins(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite")
    stored = cache.put_embeddings(
        "emb",
        {"a": CachedEmbedding([0.1, -2.5, 3.0], 4, 0.2), "b": CachedEmbedding([1.0], 1, 0.05)},
    )
    assert set(stored) == {"a", "b"}
    again = cache.put_embeddings("emb", {"a": CachedEmbedding([9.0], 99, 9.0)})
    assert again["a"].tokens == 4
    found = cache.get_embeddings(["a", "b", "missing", "a"])
    assert set(found) == {"a", "b"}
    assert found["a"].vector == [float(np.float32(x)) for x in (0.1, -2.5, 3.0)]
    assert (found["a"].tokens, found["a"].api_latency_s) == (4, 0.2)
    assert found["b"] == CachedEmbedding([1.0], 1, 0.05)
    cache.close()


@pytest.mark.parametrize(
    ("vector", "dtype", "size"),
    [
        ([0.5, -0.125, 0.0009765625, 0.0], "f2", 8),  # exact in float16
        ([0.1, -0.3, 0.7, 0.2], "f4", 16),  # needs float32's mantissa
        ([70000.0, 0.5, 0.5, 0.5], "f4", 16),  # out of float16 range
        ([1e-7, 0.5, 0.5, 0.5], "f4", 16),  # below float16 precision
    ],
)
def test_vectors_use_float16_only_when_lossless(vector: list[float], dtype: str, size: int) -> None:
    packed_dtype, blob = pack_vector(vector)
    assert (packed_dtype, len(blob)) == (dtype, size)
    assert unpack_vector(packed_dtype, blob) == [float(np.float32(x)) for x in vector]


def test_grammar_rejection_overrides_acceptance_but_not_vice_versa(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "responses.sqlite")
    cache.put_grammar_verdict("fp", GrammarVerdict(accepted=True, message=None, model="luna"))
    rejected = GrammarVerdict(accepted=False, message="fuel exhausted", model="sol")
    cache.put_grammar_verdict("fp", rejected)
    cache.put_grammar_verdict("fp", GrammarVerdict(accepted=True, message=None, model="luna"))
    assert cache.get_grammar_verdict("fp") == rejected
    assert cache.get_grammar_verdict("unknown") is None
    cache.close()
