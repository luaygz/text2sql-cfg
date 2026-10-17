# Run 20261016T170921-e6ec4a

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / dev, evidence on |
| Git SHA | `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty` |
| Started | 2026-10-16 17:09:21 UTC |
| Status | complete: 349 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.2222 billed, $0.5673 at list price, budget $6.00; 403 calls, 267 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 84.0% (79.9-87.7) [79.7%-87.4%], 293/349 |
| Oracle pass@1 | 84.0% (79.9-87.7) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0016 (total $0.5631) |
| Latency p50 / p95 | 3.9 s / 8.7 s |
| Grammar rejection rate | 0.9% (3 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 345/349 |
| Gold-suspect failures | 0 of 56 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 89.4% (83.7-95.2) | 89.4% | $0.0015 |
| moderate | 174 | 86.8% (81.6-91.4) | 86.8% | $0.0017 |
| challenging | 71 | 69.0% (57.7-78.9) | 69.0% | $0.0015 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0027 |
| card_games | 37 | 86.5% (75.7-97.3) | 86.5% | $0.0013 |
| codebase_community | 34 | 82.4% (67.6-94.1) | 82.4% | $0.0019 |
| debit_card_specializing | 21 | 76.2% (57.1-90.5) | 76.2% | $0.0012 |
| european_football_2 | 36 | 86.1% (75.0-97.2) | 86.1% | $0.0021 |
| financial | 21 | 95.2% (85.7-100.0) | 95.2% | $0.0016 |
| formula_1 | 46 | 87.0% (76.1-95.7) | 87.0% | $0.0014 |
| student_club | 34 | 97.1% (91.2-100.0) | 97.1% | $0.0011 |
| superhero | 36 | 77.8% (63.9-91.7) | 77.8% | $0.0012 |
| thrombosis_prediction | 35 | 82.9% (68.6-94.3) | 82.9% | $0.0016 |
| toxicology | 28 | 82.1% (67.9-96.4) | 82.1% | $0.0020 |

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
| extra_or_missing_output_columns | 2 |
| gold_label_suspect | 2 |
| no_sql_produced | 3 |
| other | 1 |
| wrong_aggregation_or_grouping | 21 |
| wrong_filter_value | 14 |
| wrong_join_path | 8 |
| wrong_table_or_column | 4 |
