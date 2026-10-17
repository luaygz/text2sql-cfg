# Run 20261016T152252-f93a12

| Field | Value |
|---|---|
| Config | `baseline` (overrides: question_analysis on, repair on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `afc9d969d8071241684324fa41f3d965e81c3ca2-dirty` |
| Started | 2026-10-16 15:22:52 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4039 billed, $0.4803 at list price, budget $2.00; 827 calls, 487 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 68.0% (63.1-72.9) [62.9%-72.7%], 238/350 |
| Oracle pass@1 | 68.0% (63.1-72.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0013 (total $0.4707) |
| Latency p50 / p95 | 11.9 s / 27.9 s |
| Grammar rejection rate | 0.5% (2 of 367 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 61 of 112 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 82.7% | $0.0010 |
| moderate | 175 | 65.7% (58.9-72.6) | 65.7% | $0.0015 |
| challenging | 71 | 52.1% (40.8-63.4) | 52.1% | $0.0015 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0015 |
| card_games | 37 | 62.2% (45.9-78.4) | 62.2% | $0.0012 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 67.6% | $0.0012 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0014 |
| european_football_2 | 36 | 72.2% (58.3-86.1) | 72.2% | $0.0020 |
| financial | 22 | 59.1% (36.4-77.3) | 59.1% | $0.0013 |
| formula_1 | 46 | 73.9% (60.9-87.0) | 73.9% | $0.0012 |
| student_club | 34 | 82.4% (67.6-94.1) | 82.4% | $0.0011 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0011 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0017 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0012 |

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
| date_handling | 4 |
| extra_or_missing_output_columns | 14 |
| gold_label_suspect | 32 |
| no_sql_produced | 2 |
| other | 4 |
| wrong_aggregation_or_grouping | 21 |
| wrong_filter_value | 13 |
| wrong_join_path | 8 |
| wrong_table_or_column | 14 |
