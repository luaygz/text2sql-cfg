# Run 20261016T160723-743c52

| Field | Value |
|---|---|
| Config | `best` (overrides: fewshot_k=0, judge_threshold=1.0, literal_check on, selector=judge, value_retrieval off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `df8ad146362d397359b208fa2fe4117ab23dc8d1-dirty` |
| Started | 2026-10-16 16:07:23 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.3306 billed, $3.52 at list price, budget $2.00; 6528 calls, 6265 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 70.9% (66.0-75.4) [65.9%-75.4%], 248/350 |
| Oracle pass@5 | 74.9% (70.3-79.1) |
| Selection accuracy (EX / pass@N) | 94.7% |
| Cost / question | $0.0100 (total $3.51) |
| Latency p50 / p95 | 15.5 s / 65.8 s |
| Grammar rejection rate | 1.0% (19 of 1814 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 64 of 102 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 84.6% | $0.0080 |
| moderate | 175 | 67.4% (60.6-74.3) | 73.7% | $0.0105 |
| challenging | 71 | 62.0% (50.7-73.2) | 63.4% | $0.0120 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 61.9% | $0.0132 |
| card_games | 37 | 59.5% (43.2-75.7) | 67.6% | $0.0094 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 76.5% | $0.0098 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 57.1% | $0.0110 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 86.1% | $0.0100 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0103 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 80.4% | $0.0090 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0075 |
| superhero | 36 | 88.9% (77.8-97.2) | 91.7% | $0.0085 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 57.1% | $0.0101 |
| toxicology | 28 | 75.0% (57.1-89.3) | 78.6% | $0.0144 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 9 | 7 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 13 |
| gold_label_suspect | 50 |
| other | 3 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 1 |
| wrong_table_or_column | 15 |
