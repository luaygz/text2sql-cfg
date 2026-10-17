# Run 20261016T183709-44ec7d

| Field | Value |
|---|---|
| Config | `fast` (overrides: none) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9686e41c8770ce71b6781e3ffe88ebe476f0fdc0` |
| Started | 2026-10-16 18:37:09 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / low |
| Spend | $0.0000 billed, $0.5124 at list price, budget $6.00; 416 calls, 416 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 70.6% (65.7-75.1) [65.6%-75.1%], 247/350 |
| Oracle pass@1 | 70.6% (65.7-75.1) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0014 (total $0.5067) |
| Latency p50 / p95 | 2.8 s / 8.2 s |
| Grammar rejection rate | 1.1% (4 of 352 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 61 of 103 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 80.8% (73.1-88.5) | 80.8% | $0.0014 |
| moderate | 175 | 68.6% (61.7-75.4) | 68.6% | $0.0014 |
| challenging | 71 | 60.6% (49.3-71.8) | 60.6% | $0.0017 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0016 |
| card_games | 37 | 64.9% (48.6-78.4) | 64.9% | $0.0013 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0017 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0012 |
| european_football_2 | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0016 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0013 |
| formula_1 | 46 | 73.9% (60.9-87.0) | 73.9% | $0.0016 |
| student_club | 34 | 79.4% (64.7-91.2) | 79.4% | $0.0022 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0010 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 51.4% | $0.0012 |
| toxicology | 28 | 71.4% (53.6-85.7) | 71.4% | $0.0010 |

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
| date_handling | 2 |
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 48 |
| no_sql_produced | 4 |
| other | 1 |
| wrong_aggregation_or_grouping | 12 |
| wrong_filter_value | 12 |
| wrong_join_path | 3 |
| wrong_table_or_column | 10 |
