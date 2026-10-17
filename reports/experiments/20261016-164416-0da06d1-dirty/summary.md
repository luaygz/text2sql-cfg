# Run 20261016T164416-d77e55

| Field | Value |
|---|---|
| Config | `baseline` (overrides: effort=high, literal_check on, repair on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `0da06d1ec265d4ad94df94e9f892c1fe43f61254-dirty` |
| Started | 2026-10-16 16:44:16 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / high |
| Spend | $0.7643 billed, $0.7675 at list price, budget $2.00; 411 calls, 39 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 72.3% (67.4-76.9) [67.4%-76.7%], 253/350 |
| Oracle pass@1 | 72.3% (67.4-76.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0022 (total $0.7624) |
| Latency p50 / p95 | 4.3 s / 13.2 s |
| Grammar rejection rate | 2.0% (7 of 351 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 57 of 97 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 83.7% (76.0-90.4) | 83.7% | $0.0016 |
| moderate | 175 | 69.7% (62.9-76.6) | 69.7% | $0.0024 |
| challenging | 71 | 62.0% (50.7-73.2) | 62.0% | $0.0025 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 66.7% (47.6-85.7) | 66.7% | $0.0024 |
| card_games | 37 | 62.2% (45.9-78.4) | 62.2% | $0.0023 |
| codebase_community | 34 | 73.5% (58.8-88.2) | 73.5% | $0.0027 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0029 |
| european_football_2 | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0023 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0022 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0017 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0014 |
| superhero | 36 | 88.9% (77.8-97.2) | 88.9% | $0.0014 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0028 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0024 |

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
| date_handling | 1 |
| extra_or_missing_output_columns | 12 |
| gold_label_suspect | 43 |
| no_sql_produced | 7 |
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 10 |
| wrong_join_path | 4 |
| wrong_table_or_column | 5 |
