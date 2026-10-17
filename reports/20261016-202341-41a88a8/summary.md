# Run 20261016T202341-d168c9

| Field | Value |
|---|---|
| Config | `best` (overrides: judge_threshold=1.0, n_candidates=5, selector=unit_test) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 20:23:41 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.0628 billed, $2.45 at list price, budget $15.00; 1957 calls, 1814 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.0% (69.4-78.6) [69.2%-78.3%], 259/350 |
| Oracle pass@5 | 75.4% (70.9-79.7) |
| Selection accuracy (EX / pass@N) | 98.1% |
| Cost / question | $0.0070 (total $2.44) |
| Latency p50 / p95 | 4.5 s / 21.1 s |
| Grammar rejection rate | 0.0% (0 of 1755 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 60 of 91 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 85.6% | $0.0059 |
| moderate | 175 | 70.3% (63.4-77.1) | 72.6% | $0.0072 |
| challenging | 71 | 66.2% (54.9-77.5) | 67.6% | $0.0081 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0086 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0070 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 73.5% | $0.0066 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0075 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0082 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0080 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0067 |
| student_club | 34 | 85.3% (73.5-97.1) | 88.2% | $0.0060 |
| superhero | 36 | 88.9% (77.8-97.2) | 94.4% | $0.0061 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0068 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0063 |

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
| extra_or_missing_output_columns | 10 |
| gold_label_suspect | 50 |
| other | 1 |
| wrong_aggregation_or_grouping | 15 |
| wrong_filter_value | 4 |
| wrong_join_path | 3 |
| wrong_table_or_column | 7 |
