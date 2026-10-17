# Run 20261016T212043-562def

| Field | Value |
|---|---|
| Config | `best` (overrides: none) |
| Dataset | saas / test, evidence n/a |
| Git SHA | `70b12ce88825feb7263dfaf0a75ccf74d10bb829` |
| Started | 2026-10-16 21:20:43 UTC |
| Status | complete: 90 questions |
| Candidates / effort | 1 / medium |
| Spend | $0.1196 billed, $0.1642 at list price, budget $6.00; 140 calls, 36 cache hits |

## Metrics

Intervals are 95% percentile bootstrap over questions; Wilson intervals in brackets.

| Metric | Value |
|---|---|
| EX | 81.1% (72.2-88.9) [71.8%-87.9%], 73/90 |
| Oracle pass@1 | 81.1% (72.2-88.9) |
| Selection accuracy (EX / pass@N) | 100.0% |
| Cost / question | $0.0013 (total $0.1182) |
| Latency p50 / p95 | 3.2 s / 6.9 s |
| Grammar rejection rate | 0.0% (0 of 126 calls) |
| Abstain precision / recall | 84.6% (61.5-100.0) / 91.7% (75.0-100.0) |
| Gold-suspect failures | 0 of 17 |

## By difficulty

| Difficulty | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| easy | 38 | 92.1% (81.6-100.0) | 92.1% | $0.0011 |
| medium | 26 | 69.2% (50.0-84.6) | 69.2% | $0.0013 |
| hard | 26 | 76.9% (61.5-92.3) | 76.9% | $0.0016 |

## By database

| Database | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| saas_crm | 90 | 81.1% (72.2-88.9) | 81.1% | $0.0013 |

## By SaaS bucket

| Bucket | n | EX (95% CI) | pass@N | Cost / q |
|---|---|---|---|---|
| adversarial | 15 | 86.7% (66.7-100.0) | 86.7% | $0.0010 |
| answerable | 45 | 73.3% (60.0-86.7) | 73.3% | $0.0016 |
| tenant | 18 | 88.9% (72.2-100.0) | 88.9% | $0.0012 |
| unanswerable | 12 | 91.7% (75.0-100.0) | 91.7% | $0.0009 |

## Safety

Adversarial questions: 15. Questions where an unsafe effect reached the database: 0.

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
| extra_or_missing_output_columns | 2 |
| gold_label_suspect | 1 |
| wrong_aggregation_or_grouping | 1 |
| wrong_filter_value | 5 |
| wrong_join_path | 5 |
