from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from text2sql.config import get_settings
from text2sql.safety import (
    SafetyEvent,
    SafetyEventLog,
    ScopeRule,
    ScopeViolation,
    ValidationError,
)


def test_records_append_as_json_lines_and_read_back(tmp_path: Path) -> None:
    log = SafetyEventLog(tmp_path / "nested" / "events.jsonl")
    first = SafetyEvent("grammar", "grammar_rejection", "no tool call", None, {"qid": "q1"})
    second = SafetyEvent.from_error(
        ValidationError("hidden_column", "tenant_id is not visible"),
        sql="SELECT tenant_id FROM deals LIMIT 5",
        context={"tenant": "3"},
    )
    log.record(first)
    log.record(second)

    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["layer"] for line in lines] == ["grammar", "validator"]
    assert log.read() == [first, second]
    assert second.rule == "hidden_column"
    assert second.context == {"tenant": "3"}


def test_event_layer_comes_from_the_error_type() -> None:
    event = SafetyEvent.from_error(
        ScopeViolation(ScopeRule.UNGUARDED_TABLE, "deals is read without a guard"), sql=None
    )
    assert (event.layer, event.rule, event.context) == ("scoping", "unguarded_table", {})


def test_reading_a_missing_log_is_empty(tmp_path: Path) -> None:
    assert SafetyEventLog(tmp_path / "absent.jsonl").read() == []


def test_default_path_is_under_runs_dir() -> None:
    assert SafetyEventLog().path == get_settings().runs_dir / "safety_events.jsonl"


def test_concurrent_records_are_not_interleaved(tmp_path: Path) -> None:
    log = SafetyEventLog(tmp_path / "events.jsonl")
    detail = "x" * 5000

    def write(worker: int) -> None:
        for i in range(50):
            log.record(SafetyEvent("executor", "timeout", detail, None, {"id": f"{worker}-{i}"}))

    threads = [threading.Thread(target=write, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    events = log.read()
    assert len(events) == 400
    assert {e.context["id"] for e in events} == {f"{w}-{i}" for w in range(8) for i in range(50)}


def test_corrupt_lines_fail_loudly(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"layer": "model", "rule": "x", "detail": "y"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="layer"):
        SafetyEventLog(path).read()
