# Run 20261016T170442-a76f45

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_minidev / dev, evidence off |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:04:42 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.5196 billed, $0.5234 at list price, budget $6.00; 441 calls, 28 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 64.0% (58.9-68.9) [58.8%-68.9%], 224/350 |
| Oracle pass@1 | 64.0% (58.9-68.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0015 (total $0.5164) |
| Latency p50 / p95 | 3.5 s / 6.5 s |
| Grammar rejection rate | 0.3% (1 of 355 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 73 of 126 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 73.1% (64.4-81.7) | 73.1% | $0.0014 |
| moderate | 175 | 62.9% (55.4-69.7) | 62.9% | $0.0015 |
| challenging | 71 | 53.5% (42.3-64.8) | 53.5% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 47.6% (28.6-66.7) | 47.6% | $0.0019 |
| card_games | 37 | 56.8% (40.5-73.0) | 56.8% | $0.0014 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 67.6% | $0.0013 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0014 |
| european_football_2 | 36 | 69.4% (52.8-83.3) | 69.4% | $0.0018 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0015 |
| formula_1 | 46 | 60.9% (45.7-73.9) | 60.9% | $0.0014 |
| student_club | 34 | 82.4% (67.6-94.1) | 82.4% | $0.0013 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0011 |
| thrombosis_prediction | 35 | 34.3% (20.0-51.4) | 34.3% | $0.0021 |
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
| date_handling | 3 |
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 47 |
| no_sql_produced | 1 |
| other | 1 |
| wrong_aggregation_or_grouping | 19 |
| wrong_filter_value | 22 |
| wrong_join_path | 2 |
| wrong_table_or_column | 20 |
