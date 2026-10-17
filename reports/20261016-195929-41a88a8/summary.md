# Run 20261016T195929-0e2dd6

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 19:59:29 UTC |
| Status | complete: 349 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.1140 billed, $0.4048 at list price, budget $15.00; 402 calls, 289 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 85.1% (81.4-88.8) [81.0%-88.5%], 297/349 |
| Oracle pass@1 | 85.1% (81.4-88.8) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0011 (total $0.4008) |
| Latency p50 / p95 | 3.0 s / 7.5 s |
| Grammar rejection rate | 0.0% (0 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 345/349 |
| Gold-suspect failures | 0 of 52 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 90.4% (84.6-95.2) | 90.4% | $0.0010 |
| moderate | 174 | 86.8% (81.6-91.4) | 86.8% | $0.0012 |
| challenging | 71 | 73.2% (63.3-83.1) | 73.2% | $0.0013 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 66.7% (47.6-85.7) | 66.7% | $0.0013 |
| card_games | 37 | 86.5% (75.7-97.3) | 86.5% | $0.0011 |
| codebase_community | 34 | 82.4% (67.6-94.1) | 82.4% | $0.0010 |
| debit_card_specializing | 21 | 81.0% (61.9-95.2) | 81.0% | $0.0013 |
| european_football_2 | 36 | 88.9% (77.8-97.2) | 88.9% | $0.0014 |
| financial | 21 | 95.2% (85.7-100.0) | 95.2% | $0.0014 |
| formula_1 | 46 | 87.0% (76.1-95.7) | 87.0% | $0.0011 |
| student_club | 34 | 97.1% (91.2-100.0) | 97.1% | $0.0011 |
| superhero | 36 | 83.3% (69.4-94.4) | 83.3% | $0.0010 |
| thrombosis_prediction | 35 | 80.0% (65.7-91.4) | 80.0% | $0.0012 |
| toxicology | 28 | 82.1% (67.9-96.4) | 82.1% | $0.0010 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 0 | 0 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 3 |
| gold_label_suspect | 2 |
| wrong_aggregation_or_grouping | 22 |
| wrong_filter_value | 11 |
| wrong_join_path | 8 |
| wrong_table_or_column | 5 |
