# Run 20261016T195049-c40bea

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=5) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 19:50:49 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.0000 billed, $2.38 at list price, budget $15.00; 1812 calls, 1812 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.6% (70.0-78.9) [69.8%-78.8%], 261/350 |
| Oracle pass@5 | 75.4% (70.9-79.7) |
| Selection accuracy (EX / pass@N) | 98.9% |
| Cost / question | $0.0068 (total $2.38) |
| Latency p50 / p95 | 4.4 s / 11.4 s |
| Grammar rejection rate | 0.0% (0 of 1755 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 89 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0058 |
| moderate | 175 | 71.4% (64.6-78.3) | 72.6% | $0.0069 |
| challenging | 71 | 66.2% (54.9-77.5) | 67.6% | $0.0079 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0083 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0068 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 73.5% | $0.0064 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0070 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0080 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0077 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0067 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0060 |
| superhero | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0060 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0067 |
| toxicology | 28 | 75.0% (57.1-89.3) | 78.6% | $0.0061 |

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
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 3 |
| wrong_table_or_column | 7 |
