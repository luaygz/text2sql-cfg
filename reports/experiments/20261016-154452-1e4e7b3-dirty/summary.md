# Run 20261016T154452-63a5ea

| Field | Value |
|---|---|
| Config | `baseline` (overrides: literal_check on, repair on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `1e4e7b368e16e549e3c5573c5f154dc992960cd1-dirty` |
| Started | 2026-10-16 15:44:52 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0012 billed, $0.5089 at list price, budget $2.00; 413 calls, 412 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 72.3% (67.4-76.9) [67.4%-76.7%], 253/350 |
| Oracle pass@1 | 72.3% (67.4-76.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0014 (total $0.5034) |
| Latency p50 / p95 | 4.1 s / 9.4 s |
| Grammar rejection rate | 0.6% (2 of 351 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 59 of 97 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 83.7% (76.0-90.4) | 83.7% | $0.0013 |
| moderate | 175 | 69.1% (62.3-76.0) | 69.1% | $0.0016 |
| challenging | 71 | 63.4% (52.1-74.6) | 63.4% | $0.0013 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0018 |
| card_games | 37 | 64.9% (48.6-78.4) | 64.9% | $0.0014 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 67.6% | $0.0018 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0013 |
| european_football_2 | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0017 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0015 |
| formula_1 | 46 | 78.3% (65.2-89.1) | 78.3% | $0.0013 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0011 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0011 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 51.4% | $0.0013 |
| toxicology | 28 | 71.4% (53.6-85.7) | 71.4% | $0.0018 |

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
| extra_or_missing_output_columns | 10 |
| gold_label_suspect | 43 |
| no_sql_produced | 2 |
| wrong_aggregation_or_grouping | 16 |
| wrong_filter_value | 10 |
| wrong_join_path | 3 |
| wrong_table_or_column | 11 |
