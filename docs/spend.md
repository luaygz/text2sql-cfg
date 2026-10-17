# API spend

Every API call is priced from `config/pricing.yaml` and appended to `runs/spend_ledger.jsonl`; `uv run text2sql spend` prints the ledger by label and model. The table groups the ledger's labels by stage of the work.

| Stage | API calls | Dollars |
| --- | --- | --- |
| API spike and grammar limits | 35 | $0.05 |
| Catalog descriptions, grammar size probes, client smoke tests | 626 | $0.32 |
| Retrieval indexes (few-shot pool masking), generation, selection, pipeline smoke tests | 8,618 | $0.65 |
| Eval runner smoke test, SaaS eval set drafting and review | 1,621 | $1.65 |
| Iteration rounds R0-R10 and SaaS tuning | 6,858 | $9.93 |
| Final-table runs before the grammar fix (R11) | 4,221 | $6.52 |
| Grammar-fix probes, R13 sweep and the final dev table | 7,108 | $9.54 |
| Held-out test pass | 573 | $0.58 |
| Re-recording after the determinism fixes | 1 | $0.0002 |
| Web demo and demo recording | 46 | $0.06 |
| Total | 29,707 | $29.29 |

These are the ledger's estimates: token counts from each response, priced at the flex tier (50% of standard) except the API-spike latency measurements. They are not the OpenAI invoice; at one checkpoint the account balance implied actual billing about 4% above the ledger.
