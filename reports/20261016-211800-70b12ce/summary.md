# Run 20261016T211800-83698a

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / test, evidence on |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:18:00 UTC |
| Status | complete: 149 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0447 billed, $0.1999 at list price, budget $6.00; 172 calls, 123 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 85.2% (79.2-90.6) [78.7%-90.0%], 127/149 |
| Oracle pass@1 | 85.2% (79.2-90.6) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0013 (total $0.1982) |
| Latency p50 / p95 | 3.4 s / 7.4 s |
| Grammar rejection rate | 0.0% (0 of 150 calls) |
| Grammar coverage of gold SQL | 98.7% (96.6-100.0), 147/149 |
| Gold-suspect failures | 0 of 22 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 44 | 95.5% (88.6-100.0) | 95.5% | $0.0013 |
| moderate | 74 | 79.7% (70.3-87.8) | 79.7% | $0.0013 |
| challenging | 31 | 83.9% (71.0-96.8) | 83.9% | $0.0015 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 9 | 77.8% (44.4-100.0) | 77.8% | $0.0023 |
| card_games | 15 | 66.7% (40.0-86.7) | 66.7% | $0.0018 |
| codebase_community | 15 | 86.7% (66.7-100.0) | 86.7% | $0.0013 |
| debit_card_specializing | 9 | 88.9% (66.7-100.0) | 88.9% | $0.0013 |
| european_football_2 | 15 | 80.0% (60.0-100.0) | 80.0% | $0.0014 |
| financial | 9 | 100.0% (100.0-100.0) | 100.0% | $0.0018 |
| formula_1 | 20 | 90.0% (75.0-100.0) | 90.0% | $0.0012 |
| student_club | 14 | 92.9% (78.6-100.0) | 92.9% | $0.0009 |
| superhero | 16 | 87.5% (68.8-100.0) | 87.5% | $0.0010 |
| thrombosis_prediction | 15 | 80.0% (60.0-100.0) | 80.0% | $0.0012 |
| toxicology | 12 | 91.7% (75.0-100.0) | 91.7% | $0.0009 |

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
| extra_or_missing_output_columns | 1 |
| gold_label_suspect | 6 |
| other | 1 |
| wrong_aggregation_or_grouping | 5 |
| wrong_filter_value | 5 |
| wrong_table_or_column | 4 |
