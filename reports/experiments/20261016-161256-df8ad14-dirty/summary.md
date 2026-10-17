# Run 20261016T161256-daa0e4

| Field | Value |
|---|---|
| Config | `best` (overrides: fewshot_k=3, literal_check on, selector=vote, value_retrieval off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `df8ad146362d397359b208fa2fe4117ab23dc8d1-dirty` |
| Started | 2026-10-16 16:12:56 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $1.47 billed, $3.33 at list price, budget $2.00; 6621 calls, 5917 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 73.4% (68.9-78.0) [68.6%-77.8%], 257/350 |
| Oracle pass@5 | 75.1% (70.6-79.4) |
| Selection accuracy (EX / pass@N) | 97.7% |
| Cost / question | $0.0095 (total $3.32) |
| Latency p50 / p95 | 14.9 s / 72.1 s |
| Grammar rejection rate | 1.1% (20 of 1816 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 59 of 93 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 84.6% | $0.0075 |
| moderate | 175 | 71.4% (64.6-78.3) | 73.7% | $0.0096 |
| challenging | 71 | 64.8% (53.5-76.1) | 64.8% | $0.0120 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 61.9% | $0.0107 |
| card_games | 37 | 64.9% (48.6-78.4) | 67.6% | $0.0088 |
| codebase_community | 34 | 76.5% (61.8-91.2) | 76.5% | $0.0098 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0096 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 86.1% | $0.0095 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0091 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 80.4% | $0.0086 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0075 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0085 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0091 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0148 |

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
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 46 |
| other | 3 |
| wrong_aggregation_or_grouping | 11 |
| wrong_filter_value | 7 |
| wrong_join_path | 2 |
| wrong_table_or_column | 12 |
