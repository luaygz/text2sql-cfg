# Run 20261016T212245-adea5b

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | bird_minidev / dev, evidence on |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:22:45 UTC |
| Status | complete: 30 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.0000 billed, $0.0365 at list price, budget $0.2000; 33 calls, 33 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 83.3% (70.0-96.7) [66.4%-92.7%], 25/30 |
| Oracle pass@1 | 83.3% (70.0-96.7) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.0363) |
| Latency p50 / p95 | 3.1 s / 7.2 s |
| Grammar rejection rate | 0.0% (0 of 30 calls) |
| Grammar coverage of gold SQL | 100.0% (100.0-100.0), 30/30 |
| Gold-suspect failures | 3 of 5 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| simple | 12 | 91.7% (75.0-100.0) | 91.7% | $0.0012 |
| moderate | 12 | 83.3% (58.3-100.0) | 83.3% | $0.0011 |
| challenging | 6 | 66.7% (33.3-100.0) | 66.7% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| california_schools | 1 | 100.0% (100.0-100.0) | 100.0% | $0.0015 |
| card_games | 2 | 100.0% (100.0-100.0) | 100.0% | $0.0010 |
| codebase_community | 2 | 100.0% (100.0-100.0) | 100.0% | $0.0008 |
| debit_card_specializing | 5 | 60.0% (20.0-100.0) | 60.0% | $0.0016 |
| european_football_2 | 2 | 50.0% (0.0-100.0) | 50.0% | $0.0021 |
| financial | 2 | 100.0% (100.0-100.0) | 100.0% | $0.0011 |
| formula_1 | 3 | 100.0% (100.0-100.0) | 100.0% | $0.0012 |
| student_club | 4 | 100.0% (100.0-100.0) | 100.0% | $0.0009 |
| superhero | 1 | 100.0% (100.0-100.0) | 100.0% | $0.0007 |
| thrombosis_prediction | 6 | 83.3% (50.0-100.0) | 83.3% | $0.0012 |
| toxicology | 2 | 50.0% (0.0-100.0) | 50.0% | $0.0010 |

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
| extra_or_missing_output_columns | 1 |
| gold_label_suspect | 2 |
| wrong_aggregation_or_grouping | 1 |
| wrong_table_or_column | 1 |
