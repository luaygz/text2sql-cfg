# Run 20261016T171127-f5a69a

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / dev, evidence off |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:11:27 UTC |
| Status | complete: 349 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0990 billed, $0.5230 at list price, budget $6.00; 431 calls, 321 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 77.4% (73.1-81.7) [72.7%-81.4%], 270/349 |
| Oracle pass@1 | 77.4% (73.1-81.7) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0015 (total $0.5175) |
| Latency p50 / p95 | 3.5 s / 6.6 s |
| Grammar rejection rate | 0.6% (2 of 354 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 345/349 |
| Gold-suspect failures | 0 of 79 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 81.7% (74.0-88.5) | 81.7% | $0.0013 |
| moderate | 174 | 77.6% (71.3-83.9) | 77.6% | $0.0016 |
| challenging | 71 | 70.4% (59.2-80.3) | 70.4% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 47.6% (28.6-66.7) | 47.6% | $0.0018 |
| card_games | 37 | 75.7% (62.2-89.2) | 75.7% | $0.0012 |
| codebase_community | 34 | 76.5% (61.8-91.2) | 76.5% | $0.0018 |
| debit_card_specializing | 21 | 85.7% (71.4-100.0) | 85.7% | $0.0014 |
| european_football_2 | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0018 |
| financial | 21 | 85.7% (71.4-100.0) | 85.7% | $0.0015 |
| formula_1 | 46 | 78.3% (65.2-89.1) | 78.3% | $0.0014 |
| student_club | 34 | 94.1% (85.3-100.0) | 94.1% | $0.0013 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0011 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0020 |
| toxicology | 28 | 71.4% (53.6-85.7) | 71.4% | $0.0012 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 1 | 1 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 5 |
| extra_or_missing_output_columns | 5 |
| no_sql_produced | 2 |
| wrong_aggregation_or_grouping | 18 |
| wrong_filter_value | 31 |
| wrong_join_path | 4 |
| wrong_table_or_column | 14 |
