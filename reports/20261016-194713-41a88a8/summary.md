# Run 20261016T194713-559e25

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=3) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 19:47:13 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 3 / medium |
| Spend | $0.0000 billed, $1.44 at list price, budget $15.00; 1110 calls, 1110 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.3% (69.7-78.9) [69.5%-78.6%], 260/350 |
| Oracle pass@3 | 74.9% (70.3-79.1) |
| Selection accuracy (EX / pass@N) | 99.2% |
| Cost / question | $0.0041 (total $1.43) |
| Latency p50 / p95 | 4.1 s / 11.0 s |
| Grammar rejection rate | 0.0% (0 of 1053 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 59 of 90 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0035 |
| moderate | 175 | 70.9% (64.0-77.7) | 72.0% | $0.0042 |
| challenging | 71 | 66.2% (54.9-77.5) | 66.2% | $0.0047 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0051 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0041 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0038 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0042 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0048 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0047 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0040 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0036 |
| superhero | 36 | 91.7% (80.6-100.0) | 94.4% | $0.0036 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 54.3% | $0.0041 |
| toxicology | 28 | 75.0% (57.1-89.3) | 75.0% | $0.0036 |

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
| gold_label_suspect | 48 |
| other | 2 |
| wrong_aggregation_or_grouping | 13 |
| wrong_filter_value | 6 |
| wrong_join_path | 2 |
| wrong_table_or_column | 8 |
