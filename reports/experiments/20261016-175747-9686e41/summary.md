# Run 20261016T175747-33174d

| Field | Value |
|---|---|
| Config | `best` (overrides: n_candidates=8) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9686e41c8770ce71b6781e3ffe88ebe476f0fdc0` |
| Started | 2026-10-16 17:57:47 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 8 / medium |
| Spend | $4.14 billed, $4.65 at list price, budget $6.00; 2865 calls, 397 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 74.6% (70.0-78.9) [69.8%-78.8%], 261/350 |
| Oracle pass@8 | 76.0% (71.4-80.3) |
| Selection accuracy (EX / pass@N) | 98.1% |
| Cost / question | $0.0133 (total $4.65) |
| Latency p50 / p95 | 5.6 s / 39.5 s |
| Grammar rejection rate | 1.2% (35 of 2809 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 89 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 85.6% (78.8-92.3) | 86.5% | $0.0114 |
| moderate | 175 | 70.9% (64.0-77.7) | 73.1% | $0.0136 |
| challenging | 71 | 67.6% (56.3-78.9) | 67.6% | $0.0153 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0174 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0142 |
| codebase_community | 34 | 67.6% (52.9-82.4) | 73.5% | $0.0131 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0124 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0146 |
| financial | 22 | 68.2% (50.0-86.4) | 72.7% | $0.0124 |
| formula_1 | 46 | 80.4% (67.4-91.3) | 80.4% | $0.0120 |
| student_club | 34 | 88.2% (76.5-97.1) | 91.2% | $0.0115 |
| superhero | 36 | 91.7% (80.6-100.0) | 94.4% | $0.0102 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0144 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0158 |

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
| gold_label_suspect | 43 |
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 7 |
| wrong_join_path | 2 |
| wrong_table_or_column | 10 |
