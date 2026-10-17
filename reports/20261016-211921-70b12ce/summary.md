# Run 20261016T211921-decc79

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / test, evidence off |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:19:21 UTC |
| Status | complete: 149 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0329 billed, $0.1759 at list price, budget $6.00; 187 calls, 142 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 75.2% (67.8-81.9) [67.7%-81.4%], 112/149 |
| Oracle pass@1 | 75.2% (67.8-81.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.1731) |
| Latency p50 / p95 | 3.8 s / 7.6 s |
| Grammar rejection rate | 0.0% (0 of 150 calls) |
| Grammar coverage of gold SQL | 98.7% (96.6-100.0), 147/149 |
| Gold-suspect failures | 0 of 37 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 44 | 75.0% (61.4-86.4) | 75.0% | $0.0010 |
| moderate | 74 | 74.3% (63.5-83.8) | 74.3% | $0.0012 |
| challenging | 31 | 77.4% (61.3-90.3) | 77.4% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 9 | 55.6% (22.2-88.9) | 55.6% | $0.0013 |
| card_games | 15 | 73.3% (46.7-93.3) | 73.3% | $0.0012 |
| codebase_community | 15 | 73.3% (46.7-93.3) | 73.3% | $0.0010 |
| debit_card_specializing | 9 | 44.4% (11.1-77.8) | 44.4% | $0.0013 |
| european_football_2 | 15 | 66.7% (40.0-86.7) | 66.7% | $0.0014 |
| financial | 9 | 88.9% (66.7-100.0) | 88.9% | $0.0012 |
| formula_1 | 20 | 85.0% (70.0-100.0) | 85.0% | $0.0012 |
| student_club | 14 | 92.9% (78.6-100.0) | 92.9% | $0.0009 |
| superhero | 16 | 87.5% (68.8-100.0) | 87.5% | $0.0010 |
| thrombosis_prediction | 15 | 53.3% (26.7-80.0) | 53.3% | $0.0013 |
| toxicology | 12 | 91.7% (75.0-100.0) | 91.7% | $0.0010 |

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
| date_handling | 3 |
| gold_label_suspect | 3 |
| wrong_aggregation_or_grouping | 7 |
| wrong_filter_value | 13 |
| wrong_table_or_column | 11 |
