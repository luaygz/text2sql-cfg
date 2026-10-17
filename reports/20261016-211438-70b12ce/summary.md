# Run 20261016T211438-e69283

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_minidev / test, evidence off |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:14:38 UTC |
| Status | complete: 150 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.1774 billed, $0.1776 at list price, budget $6.00; 196 calls, 3 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 60.0% (52.0-68.0) [52.0%-67.5%], 90/150 |
| Oracle pass@1 | 60.0% (52.0-68.0) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.1739) |
| Latency p50 / p95 | 3.9 s / 7.7 s |
| Grammar rejection rate | 0.0% (0 of 150 calls) |
| Grammar coverage of gold SQL | 98.7% (96.7-100.0), 148/150 |
| Gold-suspect failures | 35 of 60 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 44 | 61.4% (47.7-75.0) | 61.4% | $0.0010 |
| moderate | 75 | 62.7% (52.0-73.3) | 62.7% | $0.0012 |
| challenging | 31 | 51.6% (35.5-67.7) | 51.6% | $0.0014 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 9 | 44.4% (11.1-77.8) | 44.4% | $0.0014 |
| card_games | 15 | 53.3% (26.7-80.0) | 53.3% | $0.0012 |
| codebase_community | 15 | 53.3% (26.7-80.0) | 53.3% | $0.0010 |
| debit_card_specializing | 9 | 44.4% (11.1-77.8) | 44.4% | $0.0013 |
| european_football_2 | 15 | 46.7% (20.0-73.3) | 46.7% | $0.0014 |
| financial | 10 | 70.0% (40.0-100.0) | 70.0% | $0.0011 |
| formula_1 | 20 | 60.0% (40.0-80.0) | 60.0% | $0.0013 |
| student_club | 14 | 85.7% (64.3-100.0) | 85.7% | $0.0009 |
| superhero | 16 | 81.2% (62.5-100.0) | 81.2% | $0.0010 |
| thrombosis_prediction | 15 | 46.7% (20.0-73.3) | 46.7% | $0.0012 |
| toxicology | 12 | 66.7% (41.7-91.7) | 66.7% | $0.0010 |

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
| extra_or_missing_output_columns | 2 |
| gold_label_suspect | 20 |
| wrong_aggregation_or_grouping | 8 |
| wrong_filter_value | 12 |
| wrong_join_path | 2 |
| wrong_table_or_column | 13 |
