# Experiments

The iteration log: one entry per round, in order, including the rounds that did not help. Every number comes from a report directory under `reports/experiments/` (moved there from `reports/` so `RESULTS.md` only shows final-code runs), whose name carries the git SHA it was recorded at. The development history was squashed into one commit before publication, so that SHA, like the others in this log, is not a commit in this repository. These reports are the record of what was measured. Most rounds ran while other work was being edited in the same tree (see the provenance note below), and none has been replayed at its own commit, so they are not claimed to replay exactly; the runs behind RESULTS.md are, and do.

Protocol, fixed before the first round:

- All tuning happens on the BIRD Mini-Dev `dev` split (350 questions, original gold, with evidence). The `test` split (150) is run once, after the last round, with the configuration chosen here.
- A component is kept only if the paired comparison against the previous round says it helps (exact McNemar on per-question correctness, and a 95% bootstrap interval on the EX delta that excludes zero), or if it cuts cost at equal accuracy.
- Every prompt change bumps the template version; the entry names the versions used.
- Cost is the list price at the flex tier, as recorded per call in the spend ledger.
- After each round, 30 failures are read by hand and labelled; the largest bucket decides the next change.

Provenance of the `-dirty` suffixes. The SHA and the dirty flag are taken when a report is written. Until `afc9d96`, a run's own appends to the tracked spend ledger counted as uncommitted changes, which is why R0-R2 carry the suffix. Later rounds ran while other work was being edited in the same working tree: the literal check and the conventions prompt were being written during R3 (both off or unloaded for that round), the offline-flag fix to the CLI and runner landed during R6-R9, and the `bird_conventions` switch (default on, same prompt text) during R10; EXPERIMENTS.md itself was often uncommitted. As far as I can tell none of these edits changed a request those rounds sent, but that is not proven, so the reports of these rounds are a record of what was measured, not runs that today's code is guaranteed to replay. Everything in RESULTS.md was re-run at clean commits after the iteration rounds and is replayed by `make eval-offline`.

## R0 (2026-10-16): baseline

- Hypothesis: none; this is the reference every later claim is measured against.
- Configuration: preset `baseline`, one `direct_full` candidate on gpt-6.1-sol at medium effort, full schema, grammar on, no retrieval, no repair. Prompts `generate_common@1.1`, `generate_direct@1.0`.
- Result: EX 68.9% (64.0-73.7), 241/350. Simple 83.7%, moderate 66.3%, challenging 53.5%. Gold SQL inside the grammar 98.9%; 2 of 350 calls produced no valid tool call.
- Cost: $0.0015 per question at list price ($0.50 billed for the run); model latency p50 4.4 s, p95 10.9 s.
- Report: `reports/experiments/20261016-145044-333f6b8-dirty`.
- Failure review (30 of 109, read against the original gold, the Arcwise gold and the databases; full table in [docs/research/failure-review-r0.md](docs/research/failure-review-r0.md)): 17 gold-label problems, 3 wrong filter values (stored spelling or casing differs from the question or evidence), 2 extra or missing output columns, 2 wrong join paths, 1 each of date handling, wrong column, ties under `LIMIT 1`, float precision, a window function the grammar excludes, and a self-imposed `LIMIT 1000`. 33 of all 109 failures match the Arcwise gold. Percentages: in 44 of 45 percentage questions the gold multiplies before dividing, and six failures differ only in the last float digit because of that ordering. The automatic classifier agreed with the hand labels on 21 of 30.
- Decision: keep as the reference.

## R1 (2026-10-16): value retrieval

- Hypothesis: matched database values in the prompt fix the "stored spelling differs" failures (CHASE-SQL lost 2.9 points without it).
- Change: R0 plus question analysis (gpt-6-luna, `question_analysis@1.1`) and value retrieval (exact match, LSH, embedding re-rank); matched values go in the user message. Confound: question analysis also adds a requested-outputs block to every generation prompt, so this round changed the first-attempt prompt as well as adding values; the two effects are not separated.
- Result: EX 68.0% (63.1-72.9). Paired against R0: -0.9 points (95% CI -3.4 to +1.7), 12 questions only R0 got right and 9 only R1 got right, exact McNemar p = 0.66.
- Cost: $0.0014 per question; model latency p50 rose from 4.4 s to 8.0 s because analysis runs first.
- Report: `reports/experiments/20261016-150252-075f993-dirty`.
- Decision: not kept. No measurable difference. With BIRD's evidence field on, most literals the model needs are already given, so the values add little; it should be retried without evidence and as repair feedback, where the review says the misses are.

## R2 (2026-10-16): schema linking as a filter

- Hypothesis: a linked schema (18% of the full schema's tokens) reduces wrong-column errors.
- Change: R0 with the single candidate on the linked schema instead of the full one (`direct_linked_fewshot` with `fewshot_k=0`), linking by the two-pass small-model linker without values. This is linking without value retrieval: value-matched columns, which the linker normally adds, were absent, which is why recall here (91.4%) is below the 94.0% the retrieval work measured with values.
- Result: EX 66.6% (61.7-71.4); linking recall 91.4% (all gold columns linked). Paired against R0: -2.3 points (95% CI -5.4 to +0.6), McNemar p = 0.19.
- Cost: $0.0039 per question, 2.6 times R0, because the per-question linked prompt never hits the prompt cache while the full-schema prefix does; latency p50 12.4 s.
- Report: `reports/experiments/20261016-150833-afc9d96-dirty`.
- Decision: not kept as a filter. This matches Maamari et al. (2024): a strong model does at least as well with the whole schema. Linking stays available as one candidate strategy's view for diversity.

## R3 (2026-10-16): execution feedback and repair

- Hypothesis: re-prompting a candidate that errors, is rejected by the validator, or returns no rows when the question expects rows recovers some failures (DIN-SQL, MAC-SQL, CHASE-SQL report 1.9 to 6.8 points with older models).
- Change: R0 plus question analysis (needed to know when an empty result is suspicious) and up to two repair turns per candidate (`repair@1.1`), continuing the candidate's own tool conversation. Same confound as R1: the analysis adds the requested-outputs block to the first attempt, so the -0.9 mixes that change with repair. Repair itself touched only 9 questions; the final ablation (repair off from `best`, analysis off in both arms) isolates it at 0.0.
- Result: EX 68.0% (63.1-72.9). Paired against R0: -0.9 points (95% CI -3.1 to +1.4), McNemar p = 0.63. Only 9 of 350 candidates triggered a repair (17 extra calls) and none of them ended correct: under the grammar, gpt-6.1-sol almost never writes SQL that fails to run, and the empty-result trigger fires rarely.
- Cost: $0.0013 per question (the first attempts partly hit the prompt cache of R1); latency p50 11.9 s.
- Report: `reports/experiments/20261016-152252-afc9d96-dirty`.
- Decision: not kept on its own. Execution errors are not where this generator fails; wrong values and wrong readings are. Next: make repair fire on value mismatches (a literal that does not occur in its column), which the R0 review identified.

## R4 (2026-10-16): BIRD conventions from the failure review

- Hypothesis: several R0 failures are convention mismatches with BIRD's gold style rather than wrong reasoning: helper columns, a self-imposed LIMIT, percentages divided before multiplying, and evidence literals copied in a spelling the database does not store.
- Change: `generate_common@1.2` rewrites the benchmark-only conventions block (text in ADR-012): return only the asked columns in order; write evidence literals in the stored spelling shown by the schema's example values; add LIMIT only for a fixed number of rows; percentages as `CAST(x AS REAL) * 100 / y`. The examples in the block are invented, not taken from dev questions. Production and tenant prompts are byte-identical to before. Everything else as R0.
- Result: EX 72.3% (67.4-76.9). Paired against R0: +3.4 points (95% CI +0.9 to +6.3), 18 questions gained and 6 lost, exact McNemar p = 0.023. Simple 83.7% (unchanged), moderate 69.1% (+2.8), challenging 63.4% (+9.9).
- Cost: $0.0014 per question; latency p50 4.1 s.
- Report: `reports/experiments/20261016-153552-5036546-dirty` (the uncommitted changes at run time were the in-progress literal check, which is off in this configuration).
- Failure labels (rules first, then gpt-6-luna): 43 gold-label suspects (the prediction matches the Arcwise gold, or the classifier says the gold is wrong), 16 aggregation or grouping, 11 wrong column, 10 wrong filter value, 10 output columns.
- Decision: kept. This is a statistically significant gain on dev. These rules encode BIRD's annotation style, which the README has to say plainly; they are off for the SaaS database.

## R5 (2026-10-16): repair with the literal check

- Hypothesis: a repair turn triggered when a string literal is not stored in its column (but a case- or space-insensitive variant is) fixes the remaining wrong-filter-value failures. Replaying the check on R0's predictions, it fired on 4 queries, all failures, and on no correct one.
- Change: R4 plus `repair=true` and `literal_check=true` (`repair@1.2`). First attempts are byte-identical to R4's requests, so they replay from the response cache.
- Result: EX 72.3%, identical to R4 question by question. After the R4 conventions (write evidence literals in the stored spelling), the check fired once in 350 questions, and execution errors are rare under the grammar.
- Cost: one extra call, $0.0012 for the run.
- Report: `reports/experiments/20261016-154452-1e4e7b3-dirty`.
- Decision: no measurable effect. Kept switched on for the multi-candidate rounds, where the extra strategies write longer SQL that is more likely to fail, and measured again by the repair-off row of the final ablation table.

## R6 (2026-10-16): five candidates and a majority vote

- Hypothesis: several strategies (divide-and-conquer, query plan, direct on the linked schema, direct on the full schema, gpt-6-luna on the linked schema) disagree on hard questions, and a vote over their execution results recovers errors (self-consistency gained 5.8 points in CHASE-SQL).
- Change: R5 plus question analysis, schema linking (for the two linked-schema strategies), the first five entries of the default schedule, and `selector=vote`.
- Result: EX 73.1% (68.6-77.7); oracle pass@5 74.9%; the vote picks a correct candidate on 97.7% of the questions where one exists. Single-candidate accuracy per strategy: divide-and-conquer 72.0%, direct on the linked schema 70.6%, direct on the full schema 70.3%, query plan 70.0%, gpt-6-luna 63.4%. Paired against R5: +0.9 points (95% CI -1.7 to +3.7), McNemar p = 0.68. Simple 82.7%, moderate 71.4%, challenging 63.4%.
- Cost: $0.0091 per question, 6.5 times R5; latency p50 14.4 s, p95 65 s.
- Report: `reports/experiments/20261016-154803-df8ad14-dirty`.
- Decision: not kept as the default. The candidates are too correlated for voting to pay: the oracle ceiling is only 2.6 points above the best single strategy, so no selector can buy much here. This is the opposite of what CHASE-SQL reported for 2024 models and fits ADR-008's expectation that reasoning models leave less on the table for test-time sampling.

## R7 (2026-10-16): pairwise LLM judge

- Hypothesis: a judge comparing cluster representatives (CHASE-SQL's selection agent, prompted, both orders per pair) beats the vote on split decisions.
- Change: R6 with `selector=judge` and `judge_threshold=1.0` (judge whenever the vote is not unanimous). Candidates replay from the cache; only judge calls are new.
- Result: EX 70.9% (66.0-75.4); selection accuracy fell from 97.7% to 94.7%. Paired against R6 (vote): -2.3 points (95% CI -4.0 to -0.6), 1 question gained and 9 lost, McNemar p = 0.021.
- Cost: $0.0100 per question.
- Report: `reports/experiments/20261016-160723-df8ad14-dirty`.
- Decision: not kept. The judge is significantly worse than the vote. CHASE-SQL's gains came from a fine-tuned selector, and its own prompted baselines were at or below self-consistency; this replicates that with gpt-6.1-sol.

## R8 (2026-10-16): retrieved few-shot examples

- Hypothesis: three train-set examples with a similar masked question skeleton (DAIL-SQL) help the linked-schema strategy (few-shots were MCS-SQL's largest single gain, +4.8, with GPT-4).
- Change: R6 with `fewshot_k=3` for the `direct_linked_fewshot` strategy (pool: BIRD's 6,601 filtered train pairs). The other four strategies' requests are unchanged and replay from the cache.
- Result: EX 73.4% (68.9-78.0), pass@5 75.1%. The few-shot strategy's own accuracy moved from 70.6% to 70.9%. Paired against R6: +0.3 points (95% CI 0.0 to +0.9), McNemar p = 1.0.
- Cost: $0.0095 per question.
- Report: `reports/experiments/20261016-161256-df8ad14-dirty`.
- Decision: not kept. Consistent with OpenAI's guidance that reasoning models often do not need examples; the effect is within noise.

## R9 (2026-10-16): unit-test selection

- Hypothesis: CHESS's unit tester (natural-language tests written to separate the clusters, each checked against every cluster) picks better than the vote on split decisions.
- Change: R6 with `selector=unit_test` and `judge_threshold=1.0` (three written tests plus the fixed one; writer gpt-6.1-sol, checker gpt-6-luna). Candidates replay from the cache.
- Result: EX 71.4% (66.6-76.0); selection accuracy 95.4% against the vote's 97.7%. Paired against R6: -1.7 points (95% CI -3.4 to -0.3), McNemar p = 0.070.
- Cost: $0.0097 per question. Latency p95 334 s: flex-tier 429 responses are retried after 300 s, and the selector adds sequential calls.
- Report: `reports/experiments/20261016-161301-df8ad14-dirty`.
- Decision: not kept. Both LLM selectors lose to the plain vote on this candidate pool.

## R10 (2026-10-16): reasoning effort

- Hypothesis: more reasoning before the tool call helps the hard questions (Agentar-Scale-SQL found test-time gains concentrate there); less reasoning may cost little.
- Change: R5 with `generator_effort=high`, and separately `generator_effort=low` (R5 is medium).
- Result: high effort 72.3% (67.4-76.9), identical in aggregate to medium (paired delta 0.0, 95% CI -2.6 to +2.6, p = 1.0); low effort 70.6% (65.7-75.1), -1.7 against medium (95% CI -4.0 to +0.6, p = 0.21). By difficulty, high vs medium: simple 83.7 vs 83.7, moderate 69.7 vs 69.1, challenging 62.0 vs 63.4.
- Cost per question: low $0.0014, medium $0.0014, high $0.0022 (+57%). Latency p50: low 2.8 s, medium 4.1 s, high 4.3 s.
- Reports: `reports/experiments/20261016-164416-0da06d1-dirty` (high), `reports/experiments/20261016-164419-0da06d1-dirty` (low).
- Decision: keep medium. High costs more for nothing measurable; low is cheaper only in latency.

## First stopping point (after R10)

The stopping rule (two consecutive rounds without a significant dev gain) first triggered after R2, and R3 did not change that. Rounds continued because the protocol also set a minimum of five rounds, and R4, the fifth, produced the only significant gain. The rule then triggered again after R6 and R7, and R8 to R10 confirmed it. Only R4 (the BIRD conventions block) produced a significant gain over the baseline: +3.4 points, p = 0.023.

At this point (after R10) the chosen configuration was R5: one `direct_full` candidate on gpt-6.1-sol at medium effort with `generate_common@1.2`, full schema, grammar on, repair turns with the literal check, no retrieval, no linking, no few-shots. Its schedule also names `divide_conquer` and `query_plan` so that the N-sweep votes over full-schema strategies that share the cached prompt prefix. R11 to R13 changed it again; the final configuration is at the end of this log.

What had not helped by then, in one line each: value retrieval (no difference with evidence on), linking as a filter (-2.3, more expensive), repair on its own (rarely fires under the grammar), five strategies with a vote (+0.9 at 6.5 times the cost), a prompted pairwise judge (-2.3, significant), few-shots (+0.3), unit-test selection (-1.7), high effort (0.0 at +57% cost).

## R11 (2026-10-16): the final runs at `9e6058b`/`9686e41`, and what they showed

The first pass of the final table re-measured every component at one commit, in the order of `scripts/final_runs.sh` as it stood at `9e6058b`. The first ten directories carry `-dirty` because the re-recorded demo GIF and tape were not yet committed; no code differed from `9e6058b` (they were committed unchanged as `9686e41`). All runs are on the dev split.

| Report | Configuration | EX |
| --- | --- | --- |
| `reports/experiments/20261016-170229-9e6058b-dirty` | best (then one candidate), Mini-Dev, evidence on | 72.3% |
| `reports/experiments/20261016-170442-9e6058b-dirty` | best, Mini-Dev, evidence off | 64.0% |
| `reports/experiments/20261016-170921-9e6058b-dirty` | best, Arcwise-Plat-SQL, evidence on | 84.0% |
| `reports/experiments/20261016-171127-9e6058b-dirty` | best, Arcwise-Plat-SQL, evidence off | 77.4% |
| `reports/experiments/20261016-171326-9e6058b-dirty` | best, SaaS | 86.1% |
| `reports/experiments/20261016-171335-9e6058b-dirty` | BIRD conventions off | 65.7% |
| `reports/experiments/20261016-171742-9e6058b-dirty` | repair and literal check off | 72.3% |
| `reports/experiments/20261016-171955-9e6058b-dirty` | grammar off (JSON output) | 74.3% |
| `reports/experiments/20261016-172344-9e6058b-dirty` | value retrieval on | 70.3% |
| `reports/experiments/20261016-173011-9e6058b-dirty` | five-strategy ensemble, vote | 73.1% |
| `reports/experiments/20261016-173435-9686e41` | ensemble with few-shots | 73.4% |
| `reports/experiments/20261016-173941-9686e41` | ensemble with pairwise judge | 70.9% |
| `reports/experiments/20261016-174410-9686e41` | ensemble with unit-test selection | 71.4% |
| `reports/experiments/20261016-174838-9686e41` | ensemble with cheap path | 73.1% |
| `reports/experiments/20261016-175316-9686e41` | low effort | 70.6% |
| `reports/experiments/20261016-175531-9686e41` | high effort | 72.3% |
| `reports/experiments/20261016-175747-9686e41` | N=8, voted | 74.6% |
| `reports/experiments/20261016-182818-9686e41` | N=3, voted | 74.0% |
| `reports/experiments/20261016-183134-9686e41` | N=5, voted | 74.3% |
| `reports/experiments/20261016-183444-9686e41` | baseline preset | 72.3% |
| `reports/experiments/20261016-183709-9686e41` | fast preset (then low effort) | 70.6% |

Two results changed the plan:

- N-sweep over the `best` schedule (direct_full, divide_conquer, query_plan, voted): N=1 72.3%, N=3 74.0% (+1.7, McNemar p = 0.11), N=5 74.3% (+2.0, 95% CI +0.3 to +3.7, p = 0.039), N=8 74.6% (+2.3, CI +0.3 to +4.3, p = 0.039), at $0.0014, $0.0051, $0.0083 and $0.0133 per question. Voting over full-schema samples of the strong model helps where the R6 ensemble (which included the linked-schema and gpt-6-luna candidates) did not. With a dozen comparisons on the same dev split behind us, p = 0.039 is suggestive rather than conclusive.
- Grammar off (JSON structured output, same prompt and guard): 74.3% against 72.3% with the grammar (11 questions only JSON got right, 4 only the grammar got right, p = 0.12). All 350 JSON queries parse under the grammar, so the gap is not coverage. Reading the 11 ([docs/research/grammar-vs-json.md](docs/research/grammar-vs-json.md)): 5 garbled literals at the very end of the query (`'#'` written as `'#159'`, `'1:54%'` with a stray quote mark), 2 runaways to the output cap, 4 plausible-either-way.

## R12 (2026-10-16): a trailing newline in the grammar

- Hypothesis: the garbled literals have a decoding cause. Every one was the last token of its query; punctuation-final literals at the end of a query were mangled 6 of 22 times, elsewhere 0 of 37.
- Finding: gpt-6.1-sol ends a tool input with `\n` whenever the grammar allows it (6 of 6 real requests, 18 of 18 copy probes). Our grammar forbade it, which removes the tokens the model normally ends on (`'\n`, `%'\n`), and the model then fails to close a punctuation-final literal or keeps writing. Copy probes of such literals under the old grammar: 5 of 18 exact; with an optional trailing newline: 18 of 18.
- Change: `start: (query | abstain) "\n"?`; `SqlGrammar.parse` drops the newline. No prompt change. Gold coverage unchanged (98.9%); all 12 grammars accepted by the API.
- Result on the seven affected questions (the exact `best` requests, several samples each): garbled or run-on outputs 10 of 29 before, 0 of 21 after; correct 17 of 29 before, 19 of 21 after. Probe spend $0.25. Data: `docs/adr/data/literal_end_probes.json`, ADR-005.
- Decision: kept. It changes every generation request, so the final table is re-run at a commit that includes it.

## R13 (2026-10-16): the N-sweep again, after the newline fix

- Hypothesis: voting over five full-schema candidates still adds two points (R11).
- Change: `best` with the R12 grammar, N = 1, 3, 5, 8 (direct_full, divide_conquer, query_plan cycled, voted).
- Result: N=1 74.3% (69.7-78.9), N=3 74.3%, N=5 74.6% (pass@5 75.4%), N=8 74.3% (pass@8 75.7%). Paired against N=1: N=5 +0.3 (95% CI -0.6 to +1.4, p = 1.0), N=3 and N=8 0.0. The single candidate gained 2.0 points from the grammar fix alone (72.3% to 74.3%), and the vote's R11 advantage disappeared: it had been voting away the decoding artifacts that the fix removed.
- Reports: `reports/experiments/20261016-190605-4242e7e` (N=5), `reports/experiments/20261016-192152-4242e7e` (N=8), `reports/experiments/20261016-193053-4242e7e` (N=1), `reports/experiments/20261016-193321-4242e7e` (N=3).
- Decision: one candidate. The final ablation run was stopped after these four runs, before spending on N=5 reference runs for the other datasets.

## Final configuration

`best` is one `direct_full` candidate on gpt-6.1-sol at medium effort, with `generate_common@1.2` (the BIRD conventions), the R12 grammar (optional trailing newline), full schema, repair turns with the literal check, no retrieval, no linking, no few-shots. Keeping repair and the literal check is a deliberate deviation from the protocol's keep rule: neither helped measurably (R3, R5, and 0.0 in the final repair-off ablation), and neither costs anything measurable, since they fire on a handful of questions. They stay as a safety net for inputs where execution errors are more common than on BIRD dev; the final ablation table reports them off so the reader can see they add nothing here. Its schedule also names `divide_conquer` and `query_plan`, so that `--set n_candidates=k` gives the voted N-sweep without new prompt prefixes. `fast` is the same at low reasoning effort. Everything in RESULTS.md is re-run at the final commit, so `make eval-offline` can replay it; rows that match these rounds replay from the response cache.

What did not help, in one line each: value retrieval (no difference with evidence on), linking as a filter (-2.3, more expensive), repair on its own (rarely fires under the grammar), five strategies with a vote (+0.9 at 6.5 times the cost), a prompted pairwise judge (-2.3, significant), few-shots (+0.3), unit-test selection (-1.7), high effort (0.0 at +57% cost), and, once the decoding bug was fixed, voting over samples of the strong model (+0.3 at N=5).

## Determinism fixes (2026-10-17, after the test pass)

Replaying every report offline (`make eval-offline`, from a cache directory holding only the committed shards, with no API key) found three reports that did not reproduce because of machine load, none of them on the test split:

- Arcwise-Plat-SQL dev without evidence (`20261016-200122-41a88a8`): question 247's prediction takes 9 s on an idle machine and hit BIRD's 30 s wall-clock limit while eight questions ran at once, so the run scored it wrong and an idle replay scored it right.
- The two five-strategy ensemble rows (`20261016-202806-41a88a8`, `20261016-205344-41a88a8`): a candidate's execution under the 10 s wall-clock limit, and in another report a literal-check lookup under its 2 s limit, behaved differently under load, which changed a repair request.
- Five further reports, one of them on the test split, matched on the day they were recorded and not on the next (questions financial/194 and thrombosis_prediction/1232): questions that compute ages from `'now'` (twelve Mini-Dev gold queries do) return different rows when the date changes. These did not need re-recording, because pinning the clock to the recording day makes them replay exactly.

Fixes, all in code that does not touch prompts or model requests: SQLite time limits for scoring, previews, the literal check and benchmark-mode candidates are budgets of virtual-machine steps (`text2sql/sqlite_budget.py`, calibrated at 84 M steps/s on the slowest finishing gold query), on connections without a statement cache, because SQLite charges a re-run statement from where its previous run stopped; scoring keeps a wall-clock backstop at five times the limit, and production and tenant modes keep the 2 s wall-clock limit for denial-of-service protection. Scoring and benchmark-mode connections read a fixed clock, 2026-10-16 12:00:00 UTC, the day every reported run was recorded (`text2sql/sqlite_clock.py`).

After the fixes every other report replayed identically, including all five test-split reports. The three reports above were re-recorded at `6633bbb` (`20261017-020652-6633bbb`, `20261017-020916-6633bbb`, `20261017-021621-6633bbb`; one new API call, $0.0002). The only score that changed is Arcwise-Plat-SQL dev without evidence, 78.8% to 79.1% (question 247). The superseded directories were not kept.

The SaaS reports need no clock pinning to replay: no SaaS gold query and no recorded SaaS candidate reads the clock, because the SaaS prompts and questions use the dataset's as-of date (2026-09-30) explicitly. Tenant mode keeps the real clock on purpose, so a future SaaS run whose SQL did read the clock would depend on the day.

SaaS evaluation runs were at first left on tenant mode's 2 s wall-clock limit, and that broke a replay. Replaying all 25 reports one at a time on 2026-10-17, with the code at `8848f66` and the default eight questions in flight, 24 matched and the SaaS dev report (`20261016-200319-41a88a8`) stopped on a cache miss. This was an ordinary `make eval-offline`-style run, with only the machine's usual background load (load average about 4 to 6 on 12 cores). The candidate for saas-answerable-108, a correlated `NOT EXISTS` with a payments subquery that runs in about 1.3 s on an idle machine, hit the 2 s limit, and the replay sent a timeout repair that the recording never made. Replayed alone at low load, the report matched; with 24 busy loops on the machine, the same miss came back every time.

The fix gives evaluation runs in every mode the step budget alone, as benchmark candidates already had: the eval runner builds its resources with `evaluation=True`, and `execution_limits` in `pipeline/resources.py` turns the wall clock off for them. Interactive tenant and production requests keep the 2 s wall clock. Neither SaaS report recorded a timeout, an execution error or a repair, so every recorded query had finished within both its step budget and 2 s, and the change cannot alter a recorded outcome. After it, both SaaS reports replayed identically, with the 24 busy loops running and at normal load.

## The dev-to-test gap (analysis of the committed reports, no new runs)

`best` scores 74.3% on dev and 68.0% on test with the original labels, and 85.1% and 85.2% with the Arcwise-Plat-SQL labels. Splitting the questions by whether the original gold's result differs from the corrected gold's (`gold_suspect` in `per_question.jsonl`; reports `20261016-193953-c2450ae` and `20261016-211125-70b12ce`):

| Split | Labels agree: n, EX | Original label suspect: n, EX |
| --- | --- | --- |
| dev | 255, 87.5% | 95, 38.9% |
| test | 111, 85.6% | 39, 17.9% |

The share of suspect labels is the same on both splits, and where the labels agree the splits score the same (Fisher p = 0.62). The gap is in the suspect questions, where the prediction matched the original label far more often on dev (Fisher p = 0.025, one test chosen after looking). Had test matched suspect labels at dev's rate, test EX would be about 73.5%. The failure classifier's labels tell the same story: gold-suspect is 46 of 90 dev failures and 26 of 48 test failures, and the convention-style category (extra or missing output columns) is 10 of 90 and 6 of 48, so test does not fail more often on the conventions themselves.

The reading: the rounds above tuned the prompt, R4's conventions block most of all, by reading dev failures against dev's original labels, and some of what they learned was the quirks of those particular labels. The dev score on original labels is optimistic by about 6 points, and the Arcwise-Plat-SQL scores are the better comparison between splits. The conventions block's 8.3-point dev gain splits into 16 questions where the labels agree (81.2% to 87.5% on that subset) and 13 where the original label is suspect; the second part did not carry over to test, so its held-out effect is probably nearer the 4.6 points the first part is worth than the full 8.3.

