# Run 20261016T172344-781d92

| Field | Value |
|---|---|
| Config | `best` (overrides: question_analysis on, value_retrieval on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:23:44 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.5052 billed, $0.5853 at list price, budget $6.00; 7035 calls, 6716 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 70.3% (65.4-74.9) [65.3%-74.8%], 246/350 |
| Oracle pass@1 | 70.3% (65.4-74.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0017 (total $0.5801) |
| Latency p50 / p95 | 10.3 s / 25.5 s |
| Grammar rejection rate | 1.9% (7 of 359 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 63 of 104 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 81.7% (74.0-88.5) | 81.7% | $0.0014 |
| moderate | 175 | 68.0% (61.1-74.9) | 68.0% | $0.0015 |
| challenging | 71 | 59.2% (47.9-70.4) | 59.2% | $0.0023 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0044 |
| card_games | 37 | 59.5% (43.2-75.7) | 59.5% | $0.0013 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0012 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0015 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0015 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0013 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 76.1% | $0.0017 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0010 |
| superhero | 36 | 88.9% (77.8-97.2) | 88.9% | $0.0010 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0012 |
| toxicology | 28 | 67.9% (50.0-85.7) | 67.9% | $0.0033 |

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
| extra_or_missing_output_columns | 14 |
| gold_label_suspect | 46 |
| no_sql_produced | 7 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 8 |
| wrong_join_path | 2 |
| wrong_table_or_column | 13 |
