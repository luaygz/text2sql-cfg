from __future__ import annotations

from datetime import datetime

import pytest
from eval_builders import candidate, question, run
from pydantic import ValidationError

from text2sql.evals.records import QuestionRecord, RunRecord


def test_question_round_trips_through_json_with_derived_fields():
    q = question(
        7,
        True,
        candidates=[False, True],
        gold_columns=[("schools", "City")],
        linked_columns=[("schools", "City")],
        selected_index=1,
    )
    dumped = q.model_dump_json()
    assert '"pass_at_n":true' in dumped
    assert '"linking_recall":1.0' in dumped
    assert QuestionRecord.model_validate_json(dumped) == q


def test_run_round_trips_through_json():
    r = run(overrides={"grammar": False})
    assert RunRecord.model_validate_json(r.model_dump_json()) == r


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"selected_index": 3}, "out of range"),
        ({"abstained": True}, "no final SQL"),
        ({"grammar_calls": 1, "grammar_rejections": 2}, "more grammar rejections"),
        ({"bucket": "tenant"}, "bucket is set exactly for SaaS"),
    ],
)
def test_inconsistent_question_records_are_rejected(overrides, message):
    with pytest.raises(ValidationError, match=message):
        question(1, True, **overrides)


def test_saas_question_needs_a_bucket_and_has_no_evidence():
    saas = {"dataset": "saas", "evidence": None, "with_evidence": False}
    with pytest.raises(ValidationError, match="bucket"):
        question(1, True, **saas)
    with pytest.raises(ValidationError, match="no evidence"):
        question(1, True, **{**saas, "bucket": "answerable", "with_evidence": True})


def test_partial_runs_must_say_why_and_complete_runs_must_not():
    with pytest.raises(ValidationError, match="partial_reason"):
        run(partial=True)
    with pytest.raises(ValidationError, match="partial_reason"):
        run(partial_reason="budget exceeded")
    assert run(partial=True, partial_reason="budget exceeded").partial


def test_sweep_overrides_must_agree_with_run_fields():
    with pytest.raises(ValidationError, match="n_candidates"):
        run(overrides={"n_candidates": 3}, n_candidates=5)
    with pytest.raises(ValidationError, match="effort"):
        run(overrides={"effort": "high"}, effort="low")
    assert run(overrides={"n_candidates": 3}, n_candidates=3).n_candidates == 3


def test_run_timestamp_must_be_timezone_aware():
    with pytest.raises(ValidationError, match="timezone"):
        run(timestamp=datetime(2026, 10, 16, 12, 0, 0))


def test_candidate_errors_describe_the_selected_candidate_only():
    q = question(
        1,
        False,
        candidates=[False, False],
        selected_index=1,
    ).model_copy(
        update={
            "candidates": [
                candidate(False, strategy="plan", exec_error="no such function: GLOB2"),
                candidate(False, strategy="direct", validator_error="LIMIT above cap"),
            ]
        }
    )
    assert q.candidate_errors() == ["direct: validator: LIMIT above cap"]
    unselected = q.model_copy(update={"selected_index": None})
    assert unselected.candidate_errors() == [
        "plan: execution: no such function: GLOB2",
        "direct: validator: LIMIT above cap",
    ]
