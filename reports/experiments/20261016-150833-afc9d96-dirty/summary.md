# Run 20261016T150833-90d352

| Field | Value |
|---|---|
| Config | `baseline` (overrides: fewshot_k=0, question_analysis on, schema_linking on, strategies=direct_linked_fewshot) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `afc9d969d8071241684324fa41f3d965e81c3ca2-dirty` |
| Started | 2026-10-16 15:08:33 UTC |
| Status | complete: 350 questions |
| Candidates / effort | 1 / medium |
| Spend | $1.36 billed, $1.39 at list price, budget $2.00; 4857 calls, 3860 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 66.6% (61.7-71.4) [61.5%-71.3%], 233/350 |
| Oracle pass@1 | 66.6% (61.7-71.4) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0039 (total $1.38) |
| Latency p50 / p95 | 12.4 s / 53.3 s |
| Grammar rejection rate | 2.0% (7 of 350 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 346/350 |
| Linking recall (all gold columns linked) | 91.4% (88.3-94.3); mean column recall 97.8% over 350 questions |
| Gold-suspect failures | 60 of 117 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 81.7% (74.0-88.5) | 81.7% | $0.0033 |
| moderate | 175 | 64.6% (57.1-71.4) | 64.6% | $0.0041 |
| challenging | 71 | 49.3% (38.0-60.6) | 49.3% | $0.0044 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0039 |
| card_games | 37 | 56.8% (40.5-73.0) | 56.8% | $0.0041 |
| codebase_community | 34 | 64.7% (47.1-79.4) | 64.7% | $0.0046 |
| debit_card_specializing | 21 | 61.9% (42.9-81.0) | 61.9% | $0.0035 |
| european_football_2 | 36 | 83.3% (69.4-94.4) | 83.3% | $0.0040 |
| financial | 22 | 50.0% (27.3-72.7) | 50.0% | $0.0039 |
| formula_1 | 46 | 69.6% (56.5-82.6) | 69.6% | $0.0035 |
| student_club | 34 | 79.4% (64.7-91.2) | 79.4% | $0.0040 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0032 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0039 |
| toxicology | 28 | 64.3% (46.4-82.1) | 64.3% | $0.0050 |

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
| date_handling | 4 |
| extra_or_missing_output_columns | 13 |
| gold_label_suspect | 25 |
| no_sql_produced | 7 |
| other | 3 |
| wrong_aggregation_or_grouping | 25 |
| wrong_filter_value | 14 |
| wrong_join_path | 9 |
| wrong_table_or_column | 17 |
