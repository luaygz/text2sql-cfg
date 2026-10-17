# Run 20261016T174838-f00d5a

| Field | Value |
|---|---|
| Config | `best` (overrides: cheap_path on, n_candidates=5, question_analysis on, schema_linking on, strategies=divide_conquer,query_plan,direct_linked_fewshot,direct_full,small_linked) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `9686e41c8770ce71b6781e3ffe88ebe476f0fdc0` |
| Started | 2026-10-16 17:48:38 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 5 / medium |
| Spend | $0.0004 billed, $2.12 at list price, budget $6.00; 5801 calls, 5796 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 73.1% (68.6-77.7) [68.3%-77.5%], 256/350 |
| Oracle pass@5 | 74.3% (69.7-78.9) |
| Selection accuracy (EX / pass@N) | 98.5% |
| Cost / question | $0.0060 (total $2.12) |
| Latency p50 / p95 | 16.2 s / 76.8 s |
| Grammar rejection rate | 1.0% (14 of 1345 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 60 of 94 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 83.7% | $0.0043 |
| moderate | 175 | 71.4% (64.6-78.3) | 73.1% | $0.0064 |
| challenging | 71 | 63.4% (52.1-74.6) | 63.4% | $0.0076 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0077 |
| card_games | 37 | 64.9% (48.6-78.4) | 67.6% | $0.0042 |
| codebase_community | 34 | 76.5% (61.8-91.2) | 76.5% | $0.0077 |
| debit_card_specializing | 21 | 57.1% (38.1-76.2) | 57.1% | $0.0074 |
| european_football_2 | 36 | 80.6% (66.7-91.7) | 86.1% | $0.0064 |
| financial | 22 | 63.6% (45.3-81.8) | 63.6% | $0.0069 |
| formula_1 | 46 | 76.1% (63.0-87.0) | 78.3% | $0.0056 |
| student_club | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0029 |
| superhero | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0068 |
| thrombosis_prediction | 35 | 57.1% (40.0-74.3) | 57.1% | $0.0042 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0091 |

## Safety

Adversarial questions: 0. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 9 | 7 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| date_handling | 1 |
| extra_or_missing_output_columns | 11 |
| gold_label_suspect | 48 |
| other | 3 |
| wrong_aggregation_or_grouping | 12 |
| wrong_filter_value | 7 |
| wrong_join_path | 1 |
| wrong_table_or_column | 11 |
