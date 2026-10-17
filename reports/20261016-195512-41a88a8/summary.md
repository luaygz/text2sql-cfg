# Run 20261016T195512-2e437b

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_minidev / dev, evidence off |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 19:55:12 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4180 billed, $0.4395 at list price, budget $15.00; 433 calls, 61 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 65.4% (60.6-70.3) [60.3%-70.2%], 229/350 |
| Oracle pass@1 | 65.4% (60.6-70.3) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.4326) |
| Latency p50 / p95 | 3.7 s / 7.2 s |
| Grammar rejection rate | 0.0% (0 of 352 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 71 of 121 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 76.0% (67.3-83.7) | 76.0% | $0.0012 |
| moderate | 175 | 64.0% (56.6-70.9) | 64.0% | $0.0012 |
| challenging | 71 | 53.5% (42.3-64.8) | 53.5% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0014 |
| card_games | 37 | 59.5% (43.2-75.7) | 59.5% | $0.0014 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0012 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0012 |
| european_football_2 | 36 | 72.2% (58.3-86.1) | 72.2% | $0.0014 |
| financial | 22 | 72.7% (54.5-90.9) | 72.7% | $0.0015 |
| formula_1 | 46 | 60.9% (45.7-73.9) | 60.9% | $0.0013 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0010 |
| superhero | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0010 |
| thrombosis_prediction | 35 | 31.4% (17.1-48.6) | 31.4% | $0.0012 |
| toxicology | 28 | 71.4% (53.6-85.7) | 71.4% | $0.0011 |

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
| date_handling | 2 |
| extra_or_missing_output_columns | 8 |
| gold_label_suspect | 52 |
| other | 2 |
| wrong_aggregation_or_grouping | 19 |
| wrong_filter_value | 18 |
| wrong_join_path | 3 |
| wrong_table_or_column | 17 |
