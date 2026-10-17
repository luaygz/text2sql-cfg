# Run 20261016T192152-eb92a7

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=8) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `4242e7e89a73a1245ac1e2bfbfbb155f1cc720d7` |
| Started | 2026-10-16 19:21:52 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 8 / medium |
| Spend | $1.41 billed, $3.79 at list price, budget $15.00; 2866 calls, 1811 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.3% (69.7-78.9) [69.5%-78.6%], 260/350 |
| Oracle pass@8 | 75.7% (71.1-80.0) |
| Selection accuracy (EX / pass@N) | 98.1% |
| Cost / question | $0.0108 (total $3.79) |
| Latency p50 / p95 | 4.9 s / 11.7 s |
| Grammar rejection rate | 0.0% (0 of 2808 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 90 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0093 |
| moderate | 175 | 70.9% (64.0-77.7) | 73.1% | $0.0111 |
| challenging | 71 | 66.2% (54.9-77.5) | 67.6% | $0.0125 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0131 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0109 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 73.5% | $0.0101 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 66.7% | $0.0111 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0128 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0122 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0107 |
| student_club | 34 | 85.3% (73.5-97.1) | 88.2% | $0.0094 |
| superhero | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0095 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0106 |
| toxicology | 28 | 75.0% (57.1-89.3) | 78.6% | $0.0098 |

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
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 47 |
| other | 2 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 5 |
| wrong_join_path | 3 |
| wrong_table_or_column | 7 |
