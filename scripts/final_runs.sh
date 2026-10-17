#!/usr/bin/env bash
# Every run behind RESULTS.md, in the order they were recorded at the final commit.
# Live: needs OPENAI_API_KEY; requests already in the response cache cost nothing.
# Replay: `make eval-offline` re-runs each report's stored configuration from the cache.
#
#   scripts/final_runs.sh dev     # reference runs, ablations and sweeps on the dev split
#   scripts/final_runs.sh test    # the single pass over the held-out test split
set -euo pipefail

EVAL=(uv run --frozen text2sql eval)
# The lifetime cap has been $50 since 2026-10-16 (EXPERIMENTS.md, R12).
export TOTAL_SPEND_CAP_USD=${TOTAL_SPEND_CAP_USD:-50}
ENSEMBLE=(--set question_analysis=true --set schema_linking=true
          --set strategies=divide_conquer,query_plan,direct_linked_fewshot,direct_full,small_linked)

dev() {
  export T2SQL_PHASE=final-dev MAX_SPEND_USD=${MAX_SPEND_USD:-15}
  # best: reference runs on every dataset, then the N-sweep (8 first, so 3 and 5 replay it).
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=8
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=3
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=5
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --no-evidence
  "${EVAL[@]}" --dataset bird_arcwise --split dev --preset best
  "${EVAL[@]}" --dataset bird_arcwise --split dev --preset best --no-evidence
  "${EVAL[@]}" --dataset saas --split dev --preset best
  # Ablations: one component switched off, or one tried-and-dropped component switched on.
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set bird_conventions=false
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set repair=false --set literal_check=false
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best \
    --set grammar=false --set repair=false --set literal_check=false
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best \
    --set question_analysis=true --set value_retrieval=true
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=5 \
    --set selector=judge --set judge_threshold=1.0
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=5 \
    --set selector=unit_test --set judge_threshold=1.0
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=5 "${ENSEMBLE[@]}"
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set n_candidates=5 "${ENSEMBLE[@]}" \
    --set cheap_path=true
  # Reasoning-effort sweep, and the other two presets for the cost table.
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set generator_effort=low
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset best --set generator_effort=high
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset fast
  "${EVAL[@]}" --dataset bird_minidev --split dev --preset baseline
}

test_split() {
  export T2SQL_PHASE=final-test MAX_SPEND_USD=${MAX_SPEND_USD:-6}
  "${EVAL[@]}" --dataset bird_minidev --split test --preset best --allow-test
  "${EVAL[@]}" --dataset bird_minidev --split test --preset best --no-evidence --allow-test
  "${EVAL[@]}" --dataset bird_arcwise --split test --preset best --allow-test
  "${EVAL[@]}" --dataset bird_arcwise --split test --preset best --no-evidence --allow-test
  "${EVAL[@]}" --dataset saas --split test --preset best --allow-test
}

case "${1:-}" in
  dev) dev ;;
  test) test_split ;;
  *) echo "usage: $0 dev|test" >&2; exit 2 ;;
esac
