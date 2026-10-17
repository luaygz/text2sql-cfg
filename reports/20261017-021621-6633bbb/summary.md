# Run 20261017T021621-142dd8

| Field | Value |
|---|---|
| Config | `best` (overrides: cheap_path on, n_candidates=5, question_analysis on, schema_linking on, strategies=divide_conquer,query_plan,direct_linked_fewshot,direct_full,small_linked) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `6633bbb782a91fa85cce5691fea1f64a203bdabf` |
| Started | 2026-10-17 02:16:21 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.0000 billed, $1.83 at list price, budget $1.00; 5766 calls, 5766 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 73.4% (68.9-78.0) [68.6%-77.8%], 257/350 |
| Oracle pass@5 | 76.0% (71.4-80.3) |
| Selection accuracy (EX / pass@N) | 96.6% |
| Cost / question | $0.0052 (total $1.83) |
| Latency p50 / p95 | 21.1 s / 52.7 s |
| Grammar rejection rate | 0.0% (0 of 1309 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 59 of 93 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 84.6% | $0.0041 |
| moderate | 175 | 71.4% (64.6-78.3) | 75.4% | $0.0057 |
| challenging | 71 | 64.8% (53.5-76.1) | 64.8% | $0.0057 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0063 |
| card_games | 37 | 64.9% (48.6-78.4) | 67.6% | $0.0041 |
| codebase_community | 34 | 76.5% (61.8-91.2) | 79.4% | $0.0065 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0069 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 88.9% | $0.0058 |
| financial | 22 | 63.6% (45.3-81.8) | 68.2% | $0.0072 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 78.3% | $0.0058 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0030 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0052 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 60.0% | $0.0039 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0042 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 5 | 5 |
| executor | 1 | 1 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 44 |
| other | 2 |
| wrong_aggregation_or_grouping | 13 |
| wrong_filter_value | 6 |
| wrong_join_path | 4 |
| wrong_table_or_column | 12 |
