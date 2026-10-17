# Run 20261016T183134-927729

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=5) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9686e41c8770ce71b6781e3ffe88ebe476f0fdc0` |
| Started | 2026-10-16 18:31:34 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.0000 billed, $2.91 at list price, budget $6.00; 1812 calls, 1811 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.3% (69.7-78.9) [69.5%-78.6%], 260/350 |
| Oracle pass@5 | 75.7% (71.1-80.0) |
| Selection accuracy (EX / pass@N) | 98.1% |
| Cost / question | $0.0083 (total $2.91) |
| Latency p50 / p95 | 5.3 s / 34.9 s |
| Grammar rejection rate | 1.1% (20 of 1756 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 59 of 90 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 86.5% | $0.0069 |
| moderate | 175 | 70.3% (63.4-77.1) | 72.6% | $0.0085 |
| challenging | 71 | 67.6% (56.3-78.9) | 67.6% | $0.0099 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0112 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0089 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 70.6% | $0.0085 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0082 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0097 |
| financial | 22 | 68.2% (50.0-86.4) | 72.7% | $0.0080 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0079 |
| student_club | 34 | 88.2% (76.5-97.1) | 91.2% | $0.0068 |
| superhero | 36 | 94.4% (86.1-100.0) | 94.4% | $0.0061 |
| thrombosis_prediction | 35 | 51.4% (34.3-68.6) | 57.1% | $0.0081 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0092 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 1 | 1 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 44 |
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 7 |
| wrong_join_path | 2 |
| wrong_table_or_column | 10 |
