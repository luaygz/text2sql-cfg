# Run 20261016T150252-5782bf

| Field | Value |
|---|---|
| Config | `baseline` (overrides: question_analysis on, value_retrieval on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `075f9935d69eea4eb4da62151cc1a0d732b5c7c3-dirty` |
| Started | 2026-10-16 15:02:52 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4758 billed, $0.4934 at list price, budget $2.00; 7073 calls, 6662 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 68.0% (63.1-72.9) [62.9%-72.7%], 238/350 |
| Oracle pass@1 | 68.0% (63.1-72.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0014 (total $0.4840) |
| Latency p50 / p95 | 8.0 s / 19.0 s |
| Grammar rejection rate | 0.9% (3 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 61 of 112 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 80.8% (73.1-88.5) | 80.8% | $0.0012 |
| moderate | 175 | 65.7% (58.9-72.6) | 65.7% | $0.0013 |
| challenging | 71 | 54.9% (43.7-66.2) | 54.9% | $0.0017 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0016 |
| card_games | 37 | 64.9% (48.6-78.4) | 64.9% | $0.0012 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0011 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0012 |
| european_football_2 | 36 | 72.2% (58.3-86.1) | 72.2% | $0.0015 |
| financial | 22 | 59.1% (36.4-77.3) | 59.1% | $0.0013 |
| formula_1 | 46 | 71.7% (58.7-84.8) | 71.7% | $0.0012 |
| student_club | 34 | 82.4% (67.6-94.1) | 82.4% | $0.0010 |
| superhero | 36 | 86.1% (75.0-97.2) | 86.1% | $0.0010 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0012 |
| toxicology | 28 | 60.7% (42.9-78.6) | 60.7% | $0.0032 |

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
| date_handling | 3 |
| extra_or_missing_output_columns | 13 |
| gold_label_suspect | 34 |
| no_sql_produced | 3 |
| other | 4 |
| wrong_aggregation_or_grouping | 23 |
| wrong_filter_value | 10 |
| wrong_join_path | 7 |
| wrong_table_or_column | 15 |
