# Run 20261017T020652-661088

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_arcwise / dev, evidence off |
| Git SHA | `6633bbb782a91fa85cce5691fea1f64a203bdabf` |
| Started | 2026-10-17 02:06:52 UTC |
| Status | complete: 349 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0000 billed, $0.4195 at list price, budget $1.00; 424 calls, 424 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 79.1% (74.8-83.4) [74.5%-83.0%], 276/349 |
| Oracle pass@1 | 79.1% (74.8-83.4) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.4140) |
| Latency p50 / p95 | 3.6 s / 7.5 s |
| Grammar rejection rate | 0.0% (0 of 351 calls) |
| Grammar coverage of gold SQL | 98.9% (97.7-99.7), 345/349 |
| Gold-suspect failures | 0 of 73 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 104 | 82.7% (75.0-89.4) | 82.7% | $0.0011 |
| moderate | 174 | 80.5% (74.7-86.2) | 80.5% | $0.0012 |
| challenging | 71 | 70.4% (59.2-80.3) | 70.4% | $0.0013 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 21 | 52.4% (33.3-71.4) | 52.4% | $0.0014 |
| card_games | 37 | 78.4% (64.9-91.9) | 78.4% | $0.0011 |
| codebase_community | 34 | 85.3% (73.5-97.1) | 85.3% | $0.0012 |
| debit_card_specializing | 21 | 85.7% (71.4-100.0) | 85.7% | $0.0012 |
| european_football_2 | 36 | 91.7% (80.6-100.0) | 91.7% | $0.0014 |
| financial | 21 | 85.7% (71.4-100.0) | 85.7% | $0.0014 |
| formula_1 | 46 | 78.3% (65.2-89.1) | 78.3% | $0.0012 |
| student_club | 34 | 94.1% (85.3-100.0) | 94.1% | $0.0010 |
| superhero | 36 | 80.6% (66.7-91.7) | 80.6% | $0.0010 |
| thrombosis_prediction | 35 | 54.3% (37.1-71.4) | 54.3% | $0.0012 |
| toxicology | 28 | 78.6% (64.3-92.9) | 78.6% | $0.0011 |

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
| date_handling | 6 |
| extra_or_missing_output_columns | 5 |
| other | 1 |
| wrong_aggregation_or_grouping | 18 |
| wrong_filter_value | 28 |
| wrong_join_path | 3 |
| wrong_table_or_column | 12 |
