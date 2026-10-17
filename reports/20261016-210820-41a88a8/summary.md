# Run 20261016T210820-2c8ad5

| Field | Value |
|---|---|
| Config | `baseline` (overrides: none) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 21:08:20 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0000 billed, $0.4204 at list price, budget $15.00; 408 calls, 408 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.3% (69.7-78.9) [69.5%-78.6%], 260/350 |
| Oracle pass@1 | 74.3% (69.7-78.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.4151) |
| Latency p50 / p95 | 3.0 s / 9.1 s |
| Grammar rejection rate | 0.0% (0 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 90 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0010 |
| moderate | 175 | 70.9% (64.0-77.7) | 70.9% | $0.0012 |
| challenging | 71 | 66.2% (54.9-77.5) | 66.2% | $0.0013 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0017 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0012 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0010 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0013 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0014 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0015 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0011 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0011 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0010 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0013 |
| toxicology | 28 | 75.0% (57.1-89.3) | 75.0% | $0.0010 |

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
| extra_or_missing_output_columns | 10 |
| gold_label_suspect | 46 |
| other | 2 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 4 |
| wrong_table_or_column | 8 |
