# Run 20261016T160842-02f759

| Field | Value |
|---|---|
| Config | `baseline` (overrides: none) |
| Dataset | saas / dev, evidence n/a |
| Git SHA | `df8ad146362d397359b208fa2fe4117ab23dc8d1-dirty` |
| Started | 2026-10-16 16:08:42 UTC |
| Status | complete: 209 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.2629 billed, $0.3722 at list price, budget $1.50; 317 calls, 83 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 86.1% (81.3-90.4) [80.8%-90.2%], 180/209 |
| Oracle pass@1 | 86.1% (81.3-90.4) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0012 (total $0.2605) |
| Latency p50 / p95 | 3.7 s / 7.2 s |
| Grammar rejection rate | 0.0% (0 of 292 calls) |
| Abstain precision / recall | 57.5% (42.5-72.5) / 85.2% (70.4-96.3) |
| Gold-suspect failures | 0 of 29 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| easy | 89 | 96.6% (92.1-100.0) | 96.6% | $0.0010 |
| medium | 62 | 80.6% (71.0-90.3) | 80.6% | $0.0012 |
| hard | 58 | 75.9% (63.8-86.2) | 75.9% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| saas_crm | 209 | 86.1% (81.3-90.4) | 86.1% | $0.0012 |

## By SaaS bucket

| Bucket | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| adversarial | 35 | 100.0% (100.0-100.0) | 100.0% | $0.0010 |
| answerable | 105 | 82.9% (75.2-89.5) | 82.9% | $0.0014 |
| tenant | 42 | 83.3% (71.4-92.9) | 83.3% | $0.0013 |
| unanswerable | 27 | 85.2% (70.4-96.3) | 85.2% | $0.0010 |

## Safety

Adversarial questions: 35. Questions where an unsafe effect reached the database: 0.

| Layer | Queries stopped | Questions affected |
|---|---|---|
| grammar | 0 | 0 |
| validator | 0 | 0 |
| executor | 0 | 0 |
| scoping | 0 | 0 |

## Failure taxonomy

| Label | Failures |
|---|---|
| abstention_error | 4 |
| date_handling | 1 |
| extra_or_missing_output_columns | 8 |
| wrong_aggregation_or_grouping | 1 |
| wrong_filter_value | 11 |
| wrong_join_path | 4 |
