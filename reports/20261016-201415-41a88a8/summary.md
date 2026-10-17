# Run 20261016T201415-1b1f91

| Field | Value |
|---|---|
| Config | `best` (overrides: question_analysis on, value_retrieval on) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 20:14:15 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.4220 billed, $0.4399 at list price, budget $15.00; 7031 calls, 6667 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 71.7% (66.9-76.3) [66.8%-76.2%], 251/350 |
| Oracle pass@1 | 71.7% (66.9-76.3) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.4344) |
| Latency p50 / p95 | 8.3 s / 19.8 s |
| Grammar rejection rate | 0.0% (0 of 354 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 61 of 99 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 82.7% | $0.0010 |
| moderate | 175 | 68.6% (61.7-75.4) | 68.6% | $0.0013 |
| challenging | 71 | 63.4% (52.1-74.6) | 63.4% | $0.0015 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0015 |
| card_games | 37 | 64.9% (48.6-78.4) | 64.9% | $0.0013 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0011 |
| debit_card_specializing | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0015 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0015 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0014 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 76.1% | $0.0012 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0011 |
| superhero | 36 | 88.9% (77.8-97.2) | 88.9% | $0.0010 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0012 |
| toxicology | 28 | 75.0% (57.1-89.3) | 75.0% | $0.0011 |

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
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 49 |
| other | 2 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 3 |
| wrong_table_or_column | 15 |
