# Run 20261016T171955-063cc3

| Field | Value |
|---|---|
| Config | `best` (overrides: grammar off, literal_check off, repair off) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:19:55 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.5288 billed, $0.5321 at list price, budget $6.00; 408 calls, 40 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.3% (69.7-78.9) [69.5%-78.6%], 260/350 |
| Oracle pass@1 | 74.3% (69.7-78.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0015 (total $0.5271) |
| Latency p50 / p95 | 3.8 s / 7.1 s |
| Grammar rejection rate | no grammar calls |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 56 of 90 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 82.7% | $0.0013 |
| moderate | 175 | 72.0% (65.1-78.9) | 72.0% | $0.0016 |
| challenging | 71 | 67.6% (56.3-78.9) | 67.6% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 66.7% (47.6-85.7) | 66.7% | $0.0025 |
| card_games | 37 | 64.9% (48.6-78.4) | 64.9% | $0.0015 |
| codebase_community | 34 | 73.5% (58.8-88.2) | 73.5% | $0.0013 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0015 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0019 |
| financial | 22 | 72.7% (54.5-90.9) | 72.7% | $0.0017 |
| formula_1 | 46 | 78.3% (65.2-89.1) | 78.3% | $0.0015 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0012 |
| superhero | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0012 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0014 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0013 |

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
| gold_label_suspect | 43 |
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 6 |
| wrong_join_path | 3 |
| wrong_table_or_column | 12 |
