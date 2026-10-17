# Run 20261016T210103-68ba1c

| Field | Value |
|---|---|
| Config | `best` (overrides: effort=high) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 21:01:03 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / high |
| Spend | $0.6185 billed, $0.6224 at list price, budget $15.00; 408 calls, 46 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.6% (70.0-78.9) [69.8%-78.8%], 261/350 |
| Oracle pass@1 | 74.6% (70.0-78.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0018 (total $0.6175) |
| Latency p50 / p95 | 4.7 s / 10.2 s |
| Grammar rejection rate | 0.0% (0 of 351 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 89 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 86.5% (79.8-92.3) | 86.5% | $0.0016 |
| moderate | 175 | 72.0% (65.1-78.9) | 72.0% | $0.0018 |
| challenging | 71 | 63.4% (52.1-74.6) | 63.4% | $0.0020 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0024 |
| card_games | 37 | 70.3% (54.1-83.8) | 70.3% | $0.0018 |
| codebase_community | 34 | 73.5% (58.8-88.2) | 73.5% | $0.0017 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0019 |
| european_football_2 | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0022 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0022 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0016 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0014 |
| superhero | 36 | 88.9% (77.8-97.2) | 88.9% | $0.0014 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0017 |
| toxicology | 28 | 75.0% (57.1-89.3) | 75.0% | $0.0016 |

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
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 44 |
| other | 2 |
| wrong_aggregation_or_grouping | 13 |
| wrong_filter_value | 4 |
| wrong_join_path | 4 |
| wrong_table_or_column | 10 |
