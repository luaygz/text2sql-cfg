# Run 20261016T145044-c99207

| Field | Value |
|---|---|
| Config | `baseline` (overrides: none) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `333f6b837b7b542718f7a064f6a2b50a7dc98aa6-dirty` |
| Started | 2026-10-16 14:50:44 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4961 billed, $0.5481 at list price, budget $2.00; 457 calls, 14 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 68.9% (64.0-73.7) [63.8%-73.5%], 241/350 |
| Oracle pass@1 | 68.9% (64.0-73.7) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0015 (total $0.5391) |
| Latency p50 / p95 | 4.4 s / 10.9 s |
| Grammar rejection rate | 0.6% (2 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 61 of 109 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 83.7% (76.0-90.4) | 83.7% | $0.0016 |
| moderate | 175 | 66.3% (59.4-73.1) | 66.3% | $0.0014 |
| challenging | 71 | 53.5% (42.3-64.8) | 53.5% | $0.0018 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 66.7% (47.6-85.7) | 66.7% | $0.0018 |
| card_games | 37 | 62.2% (45.9-78.4) | 62.2% | $0.0022 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 67.6% | $0.0012 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0015 |
| european_football_2 | 36 | 75.0% (61.1-88.9) | 75.0% | $0.0021 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0012 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 76.1% | $0.0014 |
| student_club | 34 | 76.5% (61.8-91.2) | 76.5% | $0.0011 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0012 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0014 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0020 |

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
| extra_or_missing_output_columns | 13 |
| gold_label_suspect | 34 |
| no_sql_produced | 2 |
| other | 3 |
| wrong_aggregation_or_grouping | 20 |
| wrong_filter_value | 12 |
| wrong_join_path | 8 |
| wrong_table_or_column | 13 |
