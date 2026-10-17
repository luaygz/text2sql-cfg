# Run 20261016T211125-07b428

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_minidev / test, evidence on |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:11:25 UTC |
| Status | complete: 150 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.2061 billed, $0.2061 at list price, budget $6.00; 182 calls, 0 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 68.0% (60.7-75.3) [60.2%-74.9%], 102/150 |
| Oracle pass@1 | 68.0% (60.7-75.3) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0014 (total $0.2033) |
| Latency p50 / p95 | 3.5 s / 7.9 s |
| Grammar rejection rate | 0.0% (0 of 150 calls) |
| Grammar coverage of gold SQL | 98.7% (96.7-100.0), 148/150 |
| Gold-suspect failures | 32 of 48 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 44 | 77.3% (63.6-88.6) | 77.3% | $0.0013 |
| moderate | 75 | 70.7% (60.0-80.0) | 70.7% | $0.0013 |
| challenging | 31 | 48.4% (32.3-64.5) | 48.4% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 9 | 66.7% (33.3-100.0) | 66.7% | $0.0022 |
| card_games | 15 | 60.0% (33.3-86.7) | 60.0% | $0.0019 |
| codebase_community | 15 | 60.0% (33.3-86.7) | 60.0% | $0.0014 |
| debit_card_specializing | 9 | 77.8% (44.4-100.0) | 77.8% | $0.0013 |
| european_football_2 | 15 | 66.7% (40.0-86.7) | 66.7% | $0.0014 |
| financial | 10 | 70.0% (40.0-100.0) | 70.0% | $0.0017 |
| formula_1 | 20 | 60.0% (40.0-80.0) | 60.0% | $0.0012 |
| student_club | 14 | 92.9% (78.6-100.0) | 92.9% | $0.0009 |
| superhero | 16 | 87.5% (68.8-100.0) | 87.5% | $0.0010 |
| thrombosis_prediction | 15 | 46.7% (20.0-73.3) | 46.7% | $0.0011 |
| toxicology | 12 | 66.7% (41.7-91.7) | 66.7% | $0.0013 |

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
| extra_or_missing_output_columns | 6 |
| gold_label_suspect | 26 |
| other | 1 |
| wrong_aggregation_or_grouping | 2 |
| wrong_filter_value | 4 |
| wrong_join_path | 1 |
| wrong_table_or_column | 7 |
