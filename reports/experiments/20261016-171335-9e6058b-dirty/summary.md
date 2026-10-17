# Run 20261016T171335-bd85ed

| Field | Value |
|---|---|
| Config | `best` (overrides: bird_conventions off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:13:35 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4972 billed, $0.4996 at list price, budget $6.00; 428 calls, 30 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 65.7% (60.9-70.6) [60.6%-70.5%], 230/350 |
| Oracle pass@1 | 65.7% (60.9-70.6) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0014 (total $0.4926) |
| Latency p50 / p95 | 3.3 s / 5.7 s |
| Grammar rejection rate | 0.6% (2 of 353 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 72 of 120 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 78.8% (71.2-86.5) | 78.8% | $0.0012 |
| moderate | 175 | 61.7% (54.3-68.6) | 61.7% | $0.0015 |
| challenging | 71 | 56.3% (45.1-67.6) | 56.3% | $0.0013 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0027 |
| card_games | 37 | 56.8% (40.5-73.0) | 56.8% | $0.0014 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0017 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0012 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0016 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0016 |
| formula_1 | 46 | 67.4% (54.3-80.4) | 67.4% | $0.0013 |
| student_club | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0011 |
| superhero | 36 | 83.3% (69.4-94.4) | 83.3% | $0.0010 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 51.4% | $0.0012 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0011 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 0 | 0 |
| executor | 1 | 1 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 19 |
| float_or_rounding | 1 |
| gold_label_suspect | 55 |
| no_sql_produced | 2 |
| other | 3 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 6 |
| wrong_join_path | 4 |
| wrong_table_or_column | 15 |
