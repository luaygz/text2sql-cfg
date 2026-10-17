# Run 20261016T200319-e601fd

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | saas / dev, evidence n/a |
| Git SHA | `41a88a836fa385225e7737edd13ac9197637fa02` |
| Started | 2026-10-16 20:03:19 UTC |
| Status | complete: 209 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.2631 billed, $0.3740 at list price, budget $15.00; 316 calls, 90 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 87.1% (82.3-91.4) [81.9%-91.0%], 182/209 |
| Oracle pass@1 | 87.1% (82.3-91.4) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0013 (total $0.2615) |
| Latency p50 / p95 | 3.7 s / 7.8 s |
| Grammar rejection rate | 0.0% (0 of 292 calls) |
| Abstain precision / recall | 96.2% (88.5-100.0) / 92.6% (81.5-100.0) |
| Gold-suspect failures | 0 of 27 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| easy | 89 | 96.6% (92.1-100.0) | 96.6% | $0.0010 |
| medium | 62 | 83.9% (74.2-91.9) | 83.9% | $0.0013 |
| hard | 58 | 75.9% (63.8-86.2) | 75.9% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| saas_crm | 209 | 87.1% (82.3-91.4) | 87.1% | $0.0013 |

## By SaaS bucket

| Bucket | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| adversarial | 35 | 100.0% (100.0-100.0) | 100.0% | $0.0010 |
| answerable | 105 | 84.8% (77.1-91.4) | 84.8% | $0.0014 |
| tenant | 42 | 78.6% (66.7-90.5) | 78.6% | $0.0013 |
| unanswerable | 27 | 92.6% (81.5-100.0) | 92.6% | $0.0010 |

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
| abstention_error | 3 |
| extra_or_missing_output_columns | 9 |
| wrong_filter_value | 9 |
| wrong_join_path | 6 |
