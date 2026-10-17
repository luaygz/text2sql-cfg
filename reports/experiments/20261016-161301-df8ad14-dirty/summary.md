# Run 20261016T161301-918cc9

| Field | Value |
|---|---|
| Config | `best` (overrides: fewshot_k=0, judge_threshold=1.0, literal_check on, selector=unit_test, value_retrieval off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `df8ad146362d397359b208fa2fe4117ab23dc8d1-dirty` |
| Started | 2026-10-16 16:13:01 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.2102 billed, $3.40 at list price, budget $2.00; 6758 calls, 6269 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 71.4% (66.6-76.0) [66.5%-75.9%], 250/350 |
| Oracle pass@5 | 74.9% (70.3-79.1) |
| Selection accuracy (EX / pass@N) | 95.4% |
| Cost / question | $0.0097 (total $3.39) |
| Latency p50 / p95 | 17.2 s / 333.9 s |
| Grammar rejection rate | 1.0% (19 of 1814 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 63 of 100 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 84.6% | $0.0077 |
| moderate | 175 | 68.6% (61.7-75.4) | 73.7% | $0.0100 |
| challenging | 71 | 62.0% (50.7-73.2) | 63.4% | $0.0118 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 61.9% | $0.0117 |
| card_games | 37 | 62.2% (45.9-78.4) | 67.6% | $0.0088 |
| codebase_community | 34 | 73.5% (58.8-88.2) | 76.5% | $0.0095 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0105 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 86.1% | $0.0097 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0096 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 80.4% | $0.0088 |
| student_club | 34 | 82.4% (67.6-94.1) | 85.3% | $0.0075 |
| superhero | 36 | 88.9% (77.8-97.2) | 91.7% | $0.0084 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 57.1% | $0.0099 |
| toxicology | 28 | 75.0% (57.1-89.3) | 78.6% | $0.0143 |

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
| date_handling | 2 |
| extra_or_missing_output_columns | 14 |
| gold_label_suspect | 48 |
| other | 3 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 1 |
| wrong_table_or_column | 13 |
