from __future__ import annotations

import pytest
from eval_builders import candidate, question

from text2sql.evals.metrics import (
    CoverageCase,
    compare_paired,
    evidence_pairing,
    grammar_coverage,
    summarize_run,
)
from text2sql.evals.records import ErrorLabel, FailureLabel, SafetyEventRecord
from text2sql.evals.stats import mcnemar_exact


def _saas(qid: str, bucket: str, *, correct: bool, abstained: bool, should: bool, **kw):
    return question(
        qid,
        correct,
        dataset="saas",
        bucket=bucket,
        with_evidence=False,
        evidence=None,
        db_id="saas_crm",
        difficulty="easy",
        abstained=abstained,
        should_abstain=should,
        final_sql=None if abstained else "SELECT 1",
        gold_sql=None if should else "SELECT 1",
        **kw,
    )


def test_headline_rates_and_selection_accuracy():
    questions = [
        question(1, True, candidates=[True, False]),
        question(2, False, candidates=[False, True]),  # selector picked the wrong one
        question(3, False, candidates=[False, False]),
        question(4, True, candidates=[True, True]),
    ]
    o = summarize_run(questions).overall
    assert (o.ex.k, o.ex.n, o.ex.value) == (2, 4, 0.5)
    assert (o.pass_at_n.k, o.pass_at_n.value) == (3, 0.75)
    assert o.selection_accuracy == pytest.approx(0.5 / 0.75)
    assert o.ex.ci_low <= o.ex.value <= o.ex.ci_high
    assert o.ex.wilson_low < o.ex.value < o.ex.wilson_high


def test_selection_accuracy_undefined_without_any_correct_candidate():
    o = summarize_run([question(1, False), question(2, False)]).overall
    assert o.pass_at_n.value == 0.0
    assert o.selection_accuracy is None


def test_unscored_candidates_do_not_count_toward_pass_at_n():
    assert not question(1, False, candidates=[None, None]).pass_at_n


def test_cost_and_latency_percentiles():
    questions = [question(i, True, cost_usd=0.01 * i, latency_s=float(i)) for i in range(1, 21)]
    o = summarize_run(questions).overall
    assert o.cost_per_question_usd == pytest.approx(0.105)
    assert o.latency_p50_s == pytest.approx(10.5)
    assert o.latency_p95_s == pytest.approx(19.05)
    assert summarize_run(questions).cost_total_usd == pytest.approx(2.1)


def test_breakdowns_use_bird_difficulty_order_then_alphabetical_databases():
    questions = [
        question(1, True, difficulty="challenging", db_id="toxicology"),
        question(2, False, difficulty="simple", db_id="card_games"),
        question(3, True, difficulty="moderate", db_id="toxicology"),
        question(4, True, difficulty=None, db_id="card_games"),
        question(5, False, difficulty="simple", db_id="codebase_community"),
    ]
    s = summarize_run(questions)
    assert list(s.by_difficulty) == ["simple", "moderate", "challenging", "unknown"]
    assert s.by_difficulty["simple"].ex.k == 0
    assert s.by_difficulty["simple"].n == 2
    assert list(s.by_db) == ["card_games", "codebase_community", "toxicology"]
    assert s.by_db["toxicology"].ex.value == 1.0
    assert s.by_bucket == {}


def test_linking_recall_strict_subset_and_case_insensitive():
    gold = [("frpm", "CDSCode"), ("schools", "City")]
    questions = [
        question(
            1, True, gold_columns=gold, linked_columns=[("FRPM", "cdscode"), ("schools", "city")]
        ),
        question(2, True, gold_columns=gold, linked_columns=[("frpm", "CDSCode")]),
        question(3, True, gold_columns=gold, linked_columns=None),  # linking off
        question(4, True, gold_columns=None, linked_columns=[("frpm", "CDSCode")]),
    ]
    assert [q.linking_recall for q in questions] == [1.0, 0.5, None, None]
    link = summarize_run(questions).linking
    assert link is not None
    assert link.n == 2
    assert (link.full_recall.k, link.full_recall.n) == (1, 2)
    assert link.mean_column_recall == pytest.approx(0.75)


def test_linking_summary_absent_when_linking_never_ran():
    assert summarize_run([question(1, True)]).linking is None


def test_grammar_rejection_rate_over_calls_not_questions():
    questions = [
        question(1, True, grammar_calls=5, grammar_rejections=1),
        question(2, True, grammar_calls=7, grammar_rejections=0),
    ]
    r = summarize_run(questions).grammar_rejections
    assert (r.calls, r.rejections) == (12, 1)
    assert r.rate == pytest.approx(1 / 12)
    assert summarize_run([question(3, True)]).grammar_rejections.rate is None


def test_grammar_coverage_from_cases_and_from_records():
    cases = [
        CoverageCase(db_id="b", question_id="1", parsed=True),
        CoverageCase(db_id="a", question_id="2", parsed=False, error="unexpected token 'GLOB'"),
        CoverageCase(db_id="a", question_id="3", parsed=True),
    ]
    cov = grammar_coverage(cases)
    assert cov is not None
    assert (cov.overall.k, cov.overall.n) == (2, 3)
    assert list(cov.by_db) == ["a", "b"]
    assert cov.by_db["a"].value == 0.5
    assert [c.question_id for c in cov.failures] == ["2"]
    assert grammar_coverage([]) is None

    from_records = summarize_run(
        [
            question(1, True, gold_in_grammar=True),
            question(2, True, gold_in_grammar=False),
            question(3, True),
        ]
    ).grammar_coverage
    assert from_records is not None
    assert (from_records.overall.k, from_records.overall.n) == (1, 2)


def test_safety_counts_by_layer_and_database_violations():
    events = [
        SafetyEventRecord(layer="validator", rule="table_not_allowed", detail="sqlite_master"),
        SafetyEventRecord(layer="validator", rule="function", detail="load_extension"),
        SafetyEventRecord(layer="executor", rule="authorizer", detail="denied"),
    ]
    questions = [
        _saas(
            "a1", "adversarial", correct=True, abstained=False, should=False, safety_events=events
        ),
        _saas(
            "a2", "adversarial", correct=False, abstained=False, should=False, safety_violation=True
        ),
        _saas("t1", "tenant", correct=True, abstained=False, should=False),
    ]
    s = summarize_run(questions).safety
    assert s.events_by_layer == {"grammar": 0, "validator": 2, "executor": 1, "scoping": 0}
    assert s.questions_stopped_by_layer == {
        "grammar": 0,
        "validator": 1,
        "executor": 1,
        "scoping": 0,
    }
    assert (s.adversarial_questions, s.database_violations) == (2, 1)


def test_abstention_precision_and_recall():
    questions = [
        _saas("u1", "unanswerable", correct=True, abstained=True, should=True),
        _saas("u2", "unanswerable", correct=True, abstained=True, should=True),
        _saas("u3", "unanswerable", correct=False, abstained=False, should=True),
        _saas("q1", "answerable", correct=False, abstained=True, should=False),
        _saas("q2", "answerable", correct=True, abstained=False, should=False),
    ]
    s = summarize_run(questions)
    a = s.abstention
    assert a is not None
    assert (a.abstained, a.should_abstain) == (3, 3)
    assert a.precision is not None and a.recall is not None
    assert (a.precision.k, a.precision.n) == (2, 3)
    assert (a.recall.k, a.recall.n) == (2, 3)
    assert list(s.by_bucket) == ["answerable", "unanswerable"]


def test_refusing_an_attack_does_not_count_against_abstention_precision():
    questions = [
        _saas("u1", "unanswerable", correct=True, abstained=True, should=True),
        _saas("a1", "adversarial", correct=True, abstained=True, should=False),
        _saas("a2", "adversarial", correct=True, abstained=False, should=False),
    ]
    a = summarize_run(questions).abstention
    assert a is not None and a.precision is not None
    assert (a.abstained, a.precision.k, a.precision.n) == (1, 1, 1)


def test_no_abstention_summary_for_bird():
    assert summarize_run([question(1, True)]).abstention is None


def test_failure_labels_and_gold_suspect_counts():
    label = FailureLabel(
        label=ErrorLabel.WRONG_JOIN_PATH, rationale="joins on City", source="classifier"
    )
    questions = [
        question(1, False, failure_label=label),
        question(2, False, failure_label=label, gold_suspect=True),
        question(3, False),
        question(4, True, gold_suspect=True),
    ]
    s = summarize_run(questions)
    assert s.failures == 3
    assert s.failure_labels == {"unlabelled": 1, "wrong_join_path": 2}
    assert s.gold_suspect_failures == 1


def test_rves_only_when_every_question_has_a_reward():
    full = [question(1, True, rves_reward=1.0), question(2, False, rves_reward=0.0)]
    assert summarize_run(full).rves == pytest.approx(50.0)
    assert summarize_run([*full, question(3, True)]).rves is None


def test_paired_comparison_matches_by_question_and_uses_intersection():
    reference = [question(i, i % 2 == 0) for i in range(10)]
    variant = [question(i, i % 3 != 1) for i in reversed(range(2, 12))]
    c = compare_paired(reference, variant)
    keys = range(2, 10)
    ref = [i % 2 == 0 for i in keys]
    var = [i % 3 != 1 for i in keys]
    assert c.n == 8
    assert c.reference_ex == pytest.approx(sum(ref) / 8)
    assert c.variant_ex == pytest.approx(sum(var) / 8)
    assert c.delta == pytest.approx(c.variant_ex - c.reference_ex)
    assert c.delta_ci_low <= c.delta <= c.delta_ci_high
    assert c.mcnemar_p == mcnemar_exact(ref, var).p_value


def test_paired_comparison_rejects_duplicates_and_disjoint_runs():
    with pytest.raises(ValueError, match="twice"):
        compare_paired([question(1, True), question(1, False)], [question(1, True)])
    with pytest.raises(ValueError, match="share no questions"):
        compare_paired([question(1, True)], [question(2, True)])


def test_evidence_pairing_is_with_minus_without():
    with_ = [question(i, True) for i in range(6)]
    without = [question(i, i < 2, with_evidence=False, evidence=None) for i in range(6)]
    c = evidence_pairing(with_ + without)
    assert c is not None
    assert c.delta == pytest.approx(4 / 6)
    assert (c.reference_only, c.variant_only) == (0, 4)
    assert evidence_pairing(with_) is None


def test_candidate_cannot_both_answer_and_abstain():
    with pytest.raises(ValueError, match="either has SQL or abstains"):
        candidate(sql="SELECT 1", abstain_reason="out of schema")
