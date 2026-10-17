# ADR-013: Candidate selection: clustering, vote, pairwise judge, unit tests

Status: accepted
Date: 2026-10-16

## Context

ADR-008 stage 8 decides what selection does: cluster the executed candidates by result, then pick one cluster by majority vote, by a prompted pairwise judge (CHASE-SQL's Algorithm 3), or by LLM-written unit tests (CHESS v3's Unit Tester). It leaves open what "the same result" means, how every tie is broken, and what the LLM selectors cost. `text2sql.selection` implements this stage; this ADR records those choices and the live smoke run.

Only candidates that executed without error reach selection (the pipeline drops failures). Candidates with empty results are kept, since they may be right.

## Decision

### What counts as the same result

A cluster is exactly an equivalence class of BIRD's EX metric. The official `evaluation_ex.py` scores a prediction as correct iff `set(predicted_res) == set(ground_truth_res)`, and `bird_metric.results_match` reimplements that. So for an unordered result the fingerprint is the set of rows, not the multiset ADR-008 mentions: duplicate rows collapse, because EX ignores them, and splitting two answers that EX scores identically would only split their votes. Values are encoded to follow Python equality, which is what the set comparison uses:

- `1`, `1.0` and `-0.0 == 0` match (an integral float encodes as the exact int, so `2**53 + 1` and `float(2**53 + 1)` stay apart, as they do in Python).
- Other floats match only when equal; there is no tolerance, because EX has none. `0.1 + 0.2` and `0.3` are different answers.
- NULL matches only NULL; text never matches a number or a blob.
- Column names do not count; column count does (rows of different width are never equal).

A property test checks the claim directly: for random results, fingerprint equality equals `results_match`. Every member of a cluster therefore scores the same against any gold query.

Two exceptions to EX's view. A query with a top-level ORDER BY (detected with sqlglot by `has_top_level_order_by`: the outermost SELECT or compound query, not CTEs, subqueries, windows or aggregates) gets an order-sensitive fingerprint that keeps duplicates, as ADR-008 asks, unless its result has at most one distinct row, where order cannot matter. That keeps the common `ORDER BY x DESC LIMIT 1` versus `WHERE x = (SELECT MAX(x) ...)` pair in one cluster. SQL that sqlglot cannot parse counts as unordered. Second, a truncated result (more rows than the executor's cap) never matches a complete one.

CHESS clusters by `repr()` of the result list, which is order- and type-sensitive (`1` and `1.0` split). Ours is deliberately closer to the metric.

The representative of a cluster is the member with the shortest SQL after collapsing whitespace, lowest candidate index on a tie (XiYan-SQL's choice per ADR-008). Clusters are listed largest first, then by lowest member index; this is also the order in which the LLM selectors show them.

### Tie-break order

All three selectors rank clusters by one key, in this order:

1. (vote only, on by default) a cluster of empty results loses to any cluster with rows;
2. the selector's score: votes, pairwise wins, or unit tests passed;
3. cluster size, larger first;
4. the best strategy rank among the cluster's members, lower first (the caller passes the ranks; strategies it does not rank come last);
5. the representative's SQL length, shorter first;
6. the representative's candidate index.

Step 1 follows ADR-008's "the largest non-empty cluster wins". BIRD questions essentially always have an answer: running all 500 Mini-Dev gold queries today with a 10 s limit, 498 returned rows, 2 failed or timed out, and none returned an empty result. The pipeline already repairs empty candidates, so an empty result that survives is more likely a wrong filter value than a true empty answer. The caller turns it off (`prefer_non_empty=False`) when the question analysis says the answer may be empty. The LLM selectors do not demote empty clusters; the model sees the empty result and decides.

`vote_share` is always the chosen cluster's size over all executed candidates, whichever selector chose it.

### Pairwise judge

For m clusters the judge asks every ordered pair of representatives, so each unordered pair twice with A and B swapped: m(m−1) calls on the generator model at the caller's effort, none when m < 2. The score is pairwise wins. CHASE-SQL compares both orders because, per the camera-ready, "ignoring the both side comparison will reduce the final performance by roughly 2%"; asking both orders also cancels position bias without any randomness, so every request is deterministic and the response cache works. No seed or question id is needed.

This departs from CHASE's Algorithm 3 in one way that matters. CHASE compares all candidates and awards a point, without a call, to one side of every same-result pair, so a large cluster collects many points before the judge is asked anything. We compare representatives only, as ADR-008 decided, so cluster size counts only as the first tie-break. A single candidate that wins every comparison beats a cluster of seven. That is the point of a judge, and the pipeline limits it by calling the judge only below a vote-share threshold. CHASE breaks remaining ties "arbitrarily"; ours are deterministic.

The prompt (`prompts/judge_pairwise.yaml`, adapted from CHASE's selection prompt) shows the question, the evidence, the two SQL strings, and for each result its column names, row count and first 10 rows. The schema is the union of what the two queries read, as in CHASE: tables named in the queries plus the columns `evals.metrics.gold_columns` resolves, with primary and foreign keys of those tables kept by `DatabaseSchema.subset`, rendered by `render_schema` with descriptions and sample values. That needs the caller's `catalog` (and, in tenant mode, the visible `schema` the candidates were written against). Without a catalog, or when a query cannot be resolved, the prompt uses the caller's `schema_text`. The structured output is `{reason, winner}`, reason first so it is written before the choice; the reasons go into `Selection.notes`. A call that fails structurally (refusal, truncation, bad JSON) awards no win, and its cost is still returned. `BudgetExceeded` and `CacheMiss` propagate.

### Unit tests

One writer call (the generator model) sees the schema union of all representatives, the question, the evidence and every cluster with its size, representative SQL and result preview, and writes `n_tests` tests in CHESS's "The answer SQL query should ..." form (default 3; extra tests are dropped). CHESS's fixed test is always appended verbatim: "Only the best answer from the set of candidates that most accurately answers the question, given the database schema and hint should pass this test." Then one checker call per test (the small model) judges all representatives at once, which is the design CHESS found better (68.31 against 66.78). Verdicts are matched by the candidate number shown; a missing verdict is a fail, an unknown number is ignored, and the first of duplicate verdicts counts. The score is tests passed; ties go to the larger cluster, as in CHESS's `pick_the_best_candidate`. A failed writer call leaves only the fixed test; a failed checker call passes nobody. With m ≥ 2 that is at most n_tests + 2 calls whatever m is.

CHESS checks every candidate; we check representatives only, since members of a cluster share their result. Members' SQL can still differ, so CHESS could give them different verdicts; we trade that for shorter prompts. The writer and checker share one effort setting, because the selector's signature has one. After the first smoke run, writer prompt 1.1 restored CHESS's rule against tests on particular output values ("should return 'K-8', not 'Adult'"), which only restate a preference.

### Interface additions

Beyond the core selector interface: `ExecutedCandidate.from_result(index=, strategy=, sql=, result=)` (sets `ordered` from the model's SQL, not a tenant-scoped rewrite), `majority_vote(..., prefer_non_empty=True)`, optional `catalog`, `schema` and `strategy_rank` on both LLM selectors, and `Selection.notes`. Call purposes carry the prompt tag: `selection.judge/judge_pairwise@1.0`, `selection.unit_test.write/unit_tests_write@1.1`, `selection.unit_test.check/unit_tests_check@1.0`.

No prompt-cache breakpoints are set. Judge prompts share little prefix, since each pair has its own schema union, and checker calls cost about $0.00004 each on the small model; concurrent calls would each pay the cache-write premium anyway.

### Live smoke

`tests/selection/test_selection_live.py` (marked `live` and `bird`) builds two disagreements from our BIRD dev split. Each runs a plausible wrong query in two spellings (so the wrong answer wins the vote 2 to 1) and the gold query, then runs both LLM selectors with the catalog's schema union. Models: `gpt-6.1-sol` (judge, writer) and `gpt-6-luna` (checker), both at low effort, flex tier, `max_output_tokens` 8,000. Run with `T2SQL_PHASE=selection MAX_SPEND_USD=0.20 T2SQL_LIVE_TESTS=1 uv run --frozen pytest tests/selection/test_selection_live.py -s`.

| Question | Wrong answer (2 votes) | Judge | Unit tests |
| --- | --- | --- | --- |
| 82, california_schools: grade span of the school with the highest longitude; evidence: highest means largest absolute value | `ORDER BY Longitude DESC LIMIT 1` | gold, 2 of 2 wins | gold, 4 of 4 tests; wrong 0 |
| 368, card_games: percentage of borderless cards | integer division, returns 0 | gold, 2 of 2 wins | gold, 4 of 4 tests; wrong 0 |

Cost per call, as billed on flex:

| Call | Input tokens | Output tokens (reasoning) | Cost |
| --- | --- | --- | --- |
| Judge, `gpt-6.1-sol` | 656–715 | 38–42 (0) | $0.00086–0.00090 |
| Unit-test writer, `gpt-6.1-sol` | 669–752 | 82–199 (0–70) | $0.0011–0.0017 |
| Unit-test checker, `gpt-6-luna` | 611–685 | 33–84 (0–49) | $0.00004–0.00005 |

For a two-cluster question the judge cost $0.0017–0.0018 and unit-test selection $0.0013–0.0019. The judge grows with m(m−1) (12 calls at four clusters, about $0.011 at these prompt sizes, more with bigger schema unions); unit-test selection stays at n_tests + 2 calls and grows only with the size of the candidate block. The whole smoke, including one rerun after the writer prompt change, cost $0.0096 over 22 billed calls (spend ledger, phase `selection`). At low effort `gpt-6.1-sol` spent no reasoning tokens on judge calls.

Two easy cases show that the plumbing works and that the models follow the prompts. They say nothing about selector accuracy; the iteration rounds measure that against vote and oracle pass@N.

## Consequences

- Clusters are EX-exact, so float noise splits votes: two queries computing the same average by different arithmetic can differ in the last bit and land in different clusters. A tolerance would merge them but break the guarantee that a cluster's members score alike; revisit only if traces from the iteration rounds show such splits deciding outcomes.
- Order-sensitive fingerprints split answers that EX scores identically, for example a list with and without the ORDER BY the question asked for. That costs vote concentration on BIRD and is semantically right for users. The caller decides through `ExecutedCandidate.ordered`; building candidates with `ordered=False` in benchmark mode is the switch if splits hurt.
- Empty-result demotion is right for BIRD (no empty gold answer in Mini-Dev) and wrong for the rare question whose answer is empty; the pipeline passes `prefer_non_empty=False` when the analysis says the answer may be empty.
- The judge needs up to 56 generator calls at N = 8 with all candidates disagreeing. Gating on vote share in the pipeline is what keeps it affordable.
- `text2sql.selection` imports `gold_columns` from `text2sql.evals.metrics` rather than keeping a second column resolver.

## Sources

All accessed 2026-10-16.

- CHASE-SQL, arXiv v1 HTML, §3.5 and the selection-prompt appendix (both orders, union of the two candidates' columns and tables): https://arxiv.org/html/2410.01943
- CHASE-SQL, ICLR 2025 camera-ready, Algorithm 3 text ("roughly 2%", arbitrary tie-break): https://proceedings.iclr.cc/paper_files/paper/2025/file/974ff7b5bf08dbf9400b5d599a39c77f-Paper-Conference.pdf
- CHESS unit-test writer (fixed test, clustering by `repr`): https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/unit_tester/tool_kit/generate_unit_test.py
- CHESS unit-test checker (one call per test over all candidates, tie to the largest cluster): https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/unit_tester/tool_kit/evaluate.py
- CHESS prompt templates: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_generate_unit_tests.txt and https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_evaluate.txt
- BIRD Mini-Dev EX comparison (`set(predicted_res) == set(ground_truth_res)`): https://raw.githubusercontent.com/bird-bench/mini_dev/main/evaluation/evaluation_ex.py
- The CHESS 68.31 vs 66.78 figure and the XiYan-SQL representative choice are taken from docs/research/prompts-from-papers.md and ADR-008, not re-read for this ADR.
