# Run 20261016T200529-57843f

| Field | Value |
|---|---|
| Config | `best` (overrides: bird_conventions off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 20:05:29 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4582 billed, $0.4624 at list price, budget $15.00; 429 calls, 47 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 66.0% (61.1-70.9) [60.9%-70.8%], 231/350 |
| Oracle pass@1 | 66.0% (61.1-70.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0013 (total $0.4553) |
| Latency p50 / p95 | 3.4 s / 5.9 s |
| Grammar rejection rate | 0.0% (0 of 352 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 71 of 119 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 78.8% (71.2-86.5) | 78.8% | $0.0012 |
| moderate | 175 | 62.9% (55.4-69.7) | 62.9% | $0.0013 |
| challenging | 71 | 54.9% (43.7-66.2) | 54.9% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 47.6% (28.6-66.7) | 47.6% | $0.0018 |
| card_games | 37 | 56.8% (40.5-73.0) | 56.8% | $0.0014 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0012 |
| debit_card_specializing | 21 | 47.6% (28.6-66.7) | 47.6% | $0.0012 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0017 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0015 |
| formula_1 | 46 | 71.7% (58.7-84.8) | 71.7% | $0.0013 |
| student_club | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0011 |
| superhero | 36 | 86.1% (75.0-97.2) | 86.1% | $0.0011 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 51.4% | $0.0012 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0011 |

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
| extra_or_missing_output_columns | 21 |
| float_or_rounding | 1 |
| gold_label_suspect | 55 |
| other | 2 |
| wrong_aggregation_or_grouping | 13 |
| wrong_filter_value | 8 |
| wrong_join_path | 5 |
| wrong_table_or_column | 13 |
