"""The executor/worker wire format, and the worker loop run in-process over a socket pair."""

from __future__ import annotations

import math
import socket
import threading
from multiprocessing.connection import Connection

import pytest
from hypothesis import given
from hypothesis import strategies as st

from text2sql.execution import (
    DEFAULT_FUNCTIONS,
    AccessDenied,
    AccessPolicy,
    ExecutionError,
    ExecutionLimits,
    QueryFailed,
    QueryResult,
    QueryTimeout,
    ResultTooLarge,
)
from text2sql.execution import worker as worker_module
from text2sql.execution.protocol import (
    READY,
    check_ready,
    decode_reply,
    decode_request,
    decode_setup,
    encode_error,
    encode_request,
    encode_result,
    encode_setup,
    max_reply_bytes,
)
from text2sql.execution.sandbox import cell_bytes
from text2sql.execution.worker import serve

CELLS = st.one_of(
    st.text(),  # no lone surrogates: SQLite text always decodes as UTF-8
    st.text(alphabet=st.characters(min_codepoint=0x10000)),  # escaped as surrogate pairs
    st.text(alphabet=st.characters(max_codepoint=0x1F)),  # control characters, \u00XX
    st.binary(),
    st.integers(min_value=-(2**63), max_value=2**63 - 1),
    st.floats(allow_nan=False),
    st.none(),
)


def test_result_round_trip_preserves_every_cell_type():
    result = QueryResult(
        columns=("i", "f", "s", "b", "n"),
        rows=(
            (1, 0.1, "naïve '\" ☃", b"\x00\xff", None),
            (-(2**63), math.inf, "", b"", None),
        ),
        truncated=True,
        elapsed_s=0.25,
    )
    assert decode_reply(encode_result(result)) == result


@pytest.mark.parametrize(
    "error",
    [
        QueryTimeout(1.5),
        AccessDenied("READ", "customers.password_hash"),
        QueryFailed("no such x"),
        ResultTooLarge("result exceeds 10 bytes"),
    ],
)
def test_errors_round_trip(error):
    decoded = decode_reply(encode_error(error))
    assert type(decoded) is type(error)
    assert str(decoded) == str(error)
    assert vars(decoded) == vars(error)


@given(
    st.integers(min_value=1, max_value=4).flatmap(
        lambda width: st.tuples(
            st.lists(st.text(), min_size=width, max_size=width),
            st.lists(st.lists(CELLS, min_size=width, max_size=width).map(tuple), max_size=8),
        )
    )
)
def test_an_honest_reply_never_exceeds_the_reply_bound(columns_and_rows):
    columns, rows = columns_and_rows
    counted = sum(map(cell_bytes, columns)) + sum(cell_bytes(c) for row in rows for c in row)
    limits = ExecutionLimits(max_result_bytes=counted)
    result = QueryResult(tuple(columns), tuple(rows), truncated=True, elapsed_s=1e-300)
    assert len(encode_result(result)) <= max_reply_bytes(0, limits)


@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"])))
def test_an_error_quoting_the_sql_never_exceeds_the_reply_bound(sql):
    request = encode_request(sql, None, ExecutionLimits())
    reply = encode_error(QueryFailed(f'near "{sql}": syntax error'))
    assert len(reply) <= max_reply_bytes(len(request), ExecutionLimits(max_result_bytes=1))


@pytest.mark.parametrize(
    "reply",
    [
        b"not json",
        b"[]",
        b"null",
        b'{"error": "boom"}',
        b'{"error": "timeout", "timeout_s": "soon"}',
        b'{"columns": ["a"], "rows": [[1, 2]], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [[[1]]], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [[true]], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [1], "truncated": false, "elapsed_s": 0}',
        b'{"columns": [1], "rows": [], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [[{"b": "!!"}]], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [[{"x": 1}]], "truncated": false, "elapsed_s": 0}',
        b'{"columns": ["a"], "rows": [], "truncated": "no", "elapsed_s": 0}',
        b"[" * 100_000 + b"]" * 100_000,
    ],
)
def test_malformed_worker_replies_are_rejected(reply):
    with pytest.raises(ExecutionError, match="malformed") as caught:
        decode_reply(reply)
    assert type(caught.value) is ExecutionError


def test_check_ready():
    check_ready(READY)
    with pytest.raises(QueryFailed, match="unable to open"):
        check_ready(encode_error(QueryFailed("unable to open database file")))
    with pytest.raises(ExecutionError, match="malformed"):
        check_ready(encode_result(QueryResult((), (), truncated=False, elapsed_s=0.0)))


@pytest.mark.parametrize(
    ("access", "clock"),
    [
        (AccessPolicy(), None),
        (
            AccessPolicy(
                readable={"Orders": frozenset({"id", "tenant_id"})},
                functions=frozenset({"count"}),
                allow_recursive=True,
            ),
            "2026-10-16 12:00:00",
        ),
    ],
)
def test_setup_round_trip(tmp_path, access, clock):
    decoded = decode_setup(encode_setup(tmp_path / "x.db", access, clock))
    assert decoded == (tmp_path / "x.db", access, clock)
    assert decode_setup(encode_setup(tmp_path, AccessPolicy(), None))[1].functions == (
        DEFAULT_FUNCTIONS
    )


def test_request_round_trip():
    limits = ExecutionLimits(
        timeout_s=30.0,
        wall_clock=False,
        clock="2026-10-16 12:00:00",
        max_rows=5,
        max_value_bytes=7,
        max_result_bytes=11,
        max_memory_bytes=13,
    )
    sql, params, decoded = decode_request(encode_request("SELECT :a", {"a": "x'y"}, limits))
    assert (sql, params, decoded) == ("SELECT :a", {"a": "x'y"}, limits)
    assert decode_request(encode_request("SELECT 1", None, limits))[1] == {}


@pytest.fixture
def served():
    """A worker loop on a thread, talking over a real socket pair; records memory-cap calls."""
    ours, theirs = socket.socketpair()
    parent = Connection(ours.detach())
    child = Connection(theirs.detach())
    caps: list[int] = []
    thread = threading.Thread(
        target=serve, args=(child,), kwargs={"cap_memory": caps.append}, daemon=True
    )
    thread.start()
    yield parent, thread, caps
    parent.close()
    thread.join(timeout=5)
    child.close()


def test_worker_loop_answers_until_the_socket_closes(served, db):
    parent, thread, caps = served
    parent.send_bytes(encode_setup(db, AccessPolicy(), None))
    assert parent.recv_bytes() == READY

    limits = ExecutionLimits()
    parent.send_bytes(encode_request("SELECT COUNT(*) FROM customers", None, limits))
    result = decode_reply(parent.recv_bytes())
    assert isinstance(result, QueryResult)
    assert result.rows == ((10,),)

    parent.send_bytes(encode_request("SELECT * FROM sqlite_master", None, limits))
    denied = decode_reply(parent.recv_bytes())
    assert isinstance(denied, AccessDenied)
    assert caps == [limits.max_memory_bytes] * 2  # capped before every query

    parent.close()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_reply_that_does_not_fit_in_memory_is_reported(served, db, monkeypatch):
    parent, _, _ = served
    parent.send_bytes(encode_setup(db, AccessPolicy(), None))
    assert parent.recv_bytes() == READY
    real_encode = worker_module.encode_result

    def exhausted(result: QueryResult) -> bytes:
        raise MemoryError

    monkeypatch.setattr(worker_module, "encode_result", exhausted)
    parent.send_bytes(encode_request("SELECT 1", None, ExecutionLimits()))
    failed = decode_reply(parent.recv_bytes())
    assert isinstance(failed, ResultTooLarge)
    assert str(failed) == "query ran out of memory"

    monkeypatch.setattr(worker_module, "encode_result", real_encode)
    parent.send_bytes(encode_request("SELECT 2", None, ExecutionLimits()))
    recovered = decode_reply(parent.recv_bytes())
    assert isinstance(recovered, QueryResult)
    assert recovered.rows == ((2,),)


def test_worker_reports_a_database_it_cannot_open(served, tmp_path):
    parent, thread, _ = served
    parent.send_bytes(encode_setup(tmp_path / "missing.db", AccessPolicy(), None))
    with pytest.raises(QueryFailed, match="unable to open"):
        check_ready(parent.recv_bytes())
    thread.join(timeout=5)
    assert not thread.is_alive()
