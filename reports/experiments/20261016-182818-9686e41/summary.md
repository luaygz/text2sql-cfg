# Run 20261016T182818-2e0c61

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=3) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9686e41c8770ce71b6781e3ffe88ebe476f0fdc0` |
| Started | 2026-10-16 18:28:18 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 3 / medium |
| Spend | $0.0002 billed, $1.78 at list price, budget $6.00; 1111 calls, 1108 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.0% (69.4-78.6) [69.2%-78.3%], 259/350 |
| Oracle pass@3 | 74.6% (70.0-78.9) |
| Selection accuracy (EX / pass@N) | 99.2% |
| Cost / question | $0.0051 (total $1.78) |
| Latency p50 / p95 | 4.9 s / 13.8 s |
| Grammar rejection rate | 1.0% (11 of 1053 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 91 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0044 |
| moderate | 175 | 69.7% (62.9-76.6) | 70.9% | $0.0053 |
| challenging | 71 | 67.6% (56.3-78.9) | 67.6% | $0.0056 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0070 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0051 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 67.6% | $0.0053 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0044 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0065 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0049 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0052 |
| student_club | 34 | 85.3% (73.5-97.1) | 88.2% | $0.0038 |
| superhero | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0038 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0043 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0060 |

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
| extra_or_missing_output_columns | 12 |
| gold_label_suspect | 43 |
| wrong_aggregation_or_grouping | 16 |
| wrong_filter_value | 7 |
| wrong_join_path | 2 |
| wrong_table_or_column | 10 |
