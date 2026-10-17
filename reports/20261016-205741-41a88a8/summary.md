# Run 20261016T205741-3a69fa

| Field | Value |
|---|---|
| Config | `best` (overrides: effort=low) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 20:57:41 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / low |
| Spend | $0.4265 billed, $0.4309 at list price, budget $15.00; 411 calls, 53 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 73.7% (69.1-78.3) [68.9%-78.1%], 258/350 |
| Oracle pass@1 | 73.7% (69.1-78.3) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.4258) |
| Latency p50 / p95 | 3.0 s / 5.0 s |
| Grammar rejection rate | 0.0% (0 of 351 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Gold-suspect failures | 58 of 92 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 84.6% (77.9-91.3) | 84.6% | $0.0012 |
| moderate | 175 | 71.4% (64.6-78.3) | 71.4% | $0.0012 |
| challenging | 71 | 63.4% (52.1-74.6) | 63.4% | $0.0012 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 71.4% (52.4-90.5) | 71.4% | $0.0016 |
| card_games | 37 | 67.6% (51.4-81.1) | 67.6% | $0.0013 |
| codebase_community | 34 | 70.6% (55.9-85.3) | 70.6% | $0.0011 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0012 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0016 |
| financial | 22 | 68.2% (50.0-86.4) | 68.2% | $0.0014 |
| formula_1 | 46 | 78.3% (65.2-89.1) | 78.3% | $0.0012 |
| student_club | 34 | 88.2% (76.5-97.1) | 88.2% | $0.0010 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0010 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0012 |
| toxicology | 28 | 71.4% (53.6-85.7) | 71.4% | $0.0010 |

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
| gold_label_suspect | 45 |
| other | 1 |
| wrong_aggregation_or_grouping | 14 |
| wrong_filter_value | 4 |
| wrong_join_path | 5 |
| wrong_table_or_column | 10 |
