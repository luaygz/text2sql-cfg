# ADR-009: Evaluation methodology

Status: accepted
Date: 2026-10-16

## Context

The evaluation harness reports the metrics defined below with 95% confidence intervals, paired tests for ablations, an error taxonomy, three result tables (original Mini-Dev, Arcwise-Plat-SQL, SaaS) with BIRD rows with and without evidence, an ablation table, an N sweep split by difficulty and an effort sweep. Two rules apply throughout: no number may appear that cannot be reproduced from a logged run, and a partial run is labelled partial.

Two facts shape the design. First, the samples are small: BIRD dev is 350 questions and test 150 (ADR-003), the SaaS set about 300. At those sizes a two-point difference between configurations is usually inside the noise, so every number needs an interval and every comparison needs to use the fact that configurations answer the same questions. Second, a large share of Mini-Dev's gold labels is wrong, so a single BIRD number conflates "answers the question" with "reproduces the annotator".

The harness lives in `src/text2sql/evals/`: `records` (the JSON shapes), `stats`, `metrics`, `report` (helped by `registry`, `results_md`, `run_markdown`, `figures` and `markdown`), and `taxonomy`. BIRD's comparison itself is `bird_metric` (ADR-003).

## Decision

### Records are the only input

The runner writes one `QuestionRecord` per question and one `RunRecord` per run; the harness never re-executes SQL. Per-question correctness is decided upstream: BIRD's official set comparison for BIRD and for answerable SaaS questions, the abstention target for unanswerable ones, and the SaaS dataset's own expectation for adversarial ones. Values that can be derived (`pass_at_n`, `linking_recall`) are computed properties, so a record cannot disagree with itself, and validators reject inconsistent records (a selected index out of range, SQL on an abstained question, more grammar rejections than grammar calls, a SaaS question without a bucket).

`write_report(run, questions)` writes `reports/<YYYYmmdd-HHMMSS>-<shortsha>/` with `results.json` (run record and summary), `per_question.jsonl`, `summary.md` and `failures.md`. `regenerate_results_md()` rebuilds `RESULTS.md` and `reports/figures/` from every report directory. The directory listing is the registry; each report describes itself. The output depends only on report contents (sorted inputs, fixed seeds, SVGs with a fixed hash salt and no date), so the same reports always produce the same bytes, which the tests check.

### Metric definitions

- EX: share of questions whose final answer is correct. For BIRD this is `set(pred_rows) == set(gold_rows)`, exactly as `evaluation_ex.py` does it (read on 2026-10-16); errors and timeouts score 0.
- Oracle pass@N: share of questions where at least one of the N candidates (after repair) is correct. This is the "any of k samples passes" form that Chen et al. describe before introducing their unbiased estimator over n ≥ k samples. We do not use that estimator: our N candidates come from different strategies, not N draws from one distribution, and we always score all of them (n = k).
- Selection accuracy: EX divided by pass@N. It is undefined when no question has a correct candidate. It can exceed 1 only when the final answer is right without any candidate being right, which happens when the selector itself abstains on an unanswerable SaaS question.
- Linking recall: per question, the share of gold columns that schema linking kept, case-insensitively; the headline form is the share of questions where all gold columns were kept, since one missing column is fatal. Gold columns come from `gold_columns(sql, schema)`: sqlglot qualifies the gold SQL against the schema and every column reference is followed through its scope to a base table, so `T1`/`T2` aliases, CTEs, derived tables and correlated subqueries resolve to `table.column`. Columns of a CTE or subquery are not reported themselves; the base columns their definitions read are. `SELECT *` counts every column of the table. A double-quoted identifier that names no column is skipped, because SQLite reads it as a string literal and BIRD gold SQL relies on that. Questions are excluded when linking was off or the gold SQL reads no column at all (`SELECT COUNT(*) FROM t`).
- Grammar coverage: share of gold queries that parse under the full-schema grammar, overall and per database, with the failures listed. `grammar_coverage()` takes coverage cases from either the standalone coverage check or `QuestionRecord.gold_in_grammar`.
- Grammar rejection rate: rejected grammar-tool calls over all grammar-tool calls, repair calls included. It is a per-call rate, not per question.
- Safety: queries stopped at each layer (grammar, validator, executor, scoping, numbered 1 to 4 as in the threat model), questions affected per layer, and questions where an unsafe effect reached the database (`safety_violation`, e.g. another tenant's canary in a result). An executor-layer event is a query that got through layers 1 and 2, so the "reaching layer 3" count is the executor row. The database count must be 0.
- Abstention: precision is the share of abstentions that were warranted, recall the share of should-abstain questions where the system abstained. Both are computed over every question with a known target, so a wrong abstention on an answerable question lowers precision.
- Cost per question: mean list-price cost of the model calls a question needed, cache replays included (`CallMeta.priced_usd`, ADR-006). An offline replay therefore reports the same cost per question as the run that paid for it. Money actually billed is kept separately in the run's spend summary.
- Latency: p50 and p95 of per-question wall-clock time as recorded when the responses were first produced (`api_latency_s` on replays), with linear interpolation between order statistics.
- R-VES: reported only when every question carries a reward from `bird_metric`.

Every rate is broken down by difficulty (BIRD's simple, moderate, challenging first, then SaaS levels), by database and, for SaaS, by bucket.

### Confidence intervals

Each proportion gets a 95% percentile bootstrap interval over questions with 10,000 resamples and seed 0. Resampling n Bernoulli outcomes with replacement only matters through the number of successes, which is Binomial(n, k/n), so the code draws that count directly; the test suite checks the result against explicit index resampling and checks coverage on simulated data (93.5% of 400 simulated samples of 200 questions at a true rate of 70% fell inside their interval; the test accepts 91% to 98%). A Wilson score interval is reported next to it in `results.json` and `summary.md`. The two agree in the middle of the range; at 0% or 100% the percentile bootstrap collapses to a zero-width interval and Wilson does not, which matters for small groups such as one database or the SaaS adversarial bucket.

### Paired comparisons

Ablations, sweeps and the with/without-evidence rows compare configurations on the same questions, matched by `(db_id, question_id)` and restricted to the questions both runs answered. For each pair we report the EX difference with a paired bootstrap interval (the multinomial over the four agreement cells, which is the same as resampling question pairs) and an exact two-sided McNemar test: under the null hypothesis each discordant question favours either side with probability one half, and p = min(1, 2 · P(X ≤ min(b, c))) for X ~ Binomial(b + c, 1/2), computed in exact integer arithmetic. We use the exact test rather than the chi-squared approximation because discordant counts between nearby configurations are often below 25. It is known to be conservative (the mid-p variant is less so); we accept that, since the cost of a false "it helped" is a kept component that does nothing.

No multiple-comparison correction is applied across ablation rows. With eight or so rows, one p-value under 0.05 can appear by chance; RESULTS.md tells readers to treat a delta whose interval contains 0 as no measured difference.

### What goes into RESULTS.md

Runs are classified by `RunRecord.overrides`, the settings changed on top of a preset (`best` by default). A run without overrides is the preset's reference run. A run that changes only `n_candidates` or only `effort` is a point on the N or effort sweep; the reference run is included at its own N and effort. Any other override set is an ablation row, labelled by the overrides (`grammar off`, `value_retrieval off`). Comparisons only happen within one (dataset, split, evidence) context.

The headline table has five rows: Mini-Dev and Arcwise-Plat-SQL, each with and without evidence, and SaaS. Each shows EX with its interval, pass@N, selection accuracy, cost per question, latency and a link to the run, whose directory name carries the start time and git SHA. Each row uses the reference run on the test split once one exists, otherwise dev, and prefers complete runs over partial ones, then the latest. A separate table gives the paired with-minus-without-evidence effect for each BIRD variant. The ablation table, N-sweep table and chart (EX and cost against N, per difficulty) and effort-sweep table are generated for each context that has such runs.

RESULTS.md also counts runs of any preset on the test split per context, so a second look at the held-out split cannot happen silently.

### Partial runs

A run records `questions_planned`, `partial` and `partial_reason` (budget abort, interruption, smoke subset); a partial run without a reason, or a reason on a complete run, fails validation. `write_report` refuses a run with fewer questions than planned unless it is marked partial. Partial runs appear in RESULTS.md with "partial: answered/planned, reason" next to the run link, lose to complete runs when a row has both, and paired deltas on them say how many questions were actually paired. `results.json` is written last, so an interrupted write leaves a directory the registry ignores. The git SHA comes from `current_git_sha()`, which appends `-dirty` when tracked files have uncommitted changes. Where there is no git binary or checkout (the Docker image), it reads `T2SQL_GIT_SHA`, set at image build time. That value must be a full 40-hex SHA with an optional `-dirty` suffix. If git fails and the variable is missing or malformed, the run fails with `GitShaError` instead of writing an untagged report. A checkout always takes precedence over the variable.

### Error taxonomy

`taxonomy.label_failures` labels each failure. Rules handle what needs no judgement: no SQL produced, abstaining when it should have answered or answering when it should have abstained, no gold SQL to compare with. Two more rules come from the round-0 hand review, where the classifier got both cases wrong: a result that equals the gold's as a set once floats are rounded to 6 significant digits is `float_or_rounding` (decided only when both result previews hold the whole result), and a prediction whose rows equal the Arcwise-Plat-SQL gold's (`QuestionRecord.matches_arcwise_gold`, computed for original Mini-Dev items) is `gold_label_suspect`. The small model (`Settings.small_model`, through `LLMClient.structured`, so cached and budgeted) labels the rest from the question, evidence, both queries, both result previews and the candidate errors, choosing one of: wrong table or column, wrong join path, wrong aggregation or grouping, wrong filter value, date handling, extra or missing output columns, gold label suspect, other. The case is wrapped in tags and the instructions say that its content is data, since benchmark questions and database values are untrusted. Existing labels are kept, so a hand-review label (source `human`) is never overwritten; `sample_for_review` draws a seeded sample for that review. Label counts appear in `summary.md` and every failure in `failures.md` shows its label and source.

### Why both BIRD variants

Jin et al. report annotation errors in 52.8% of BIRD Mini-Dev examples. On the original labels, part of what EX measures is agreement with the annotators' habits, including their mistakes; Arcwise-Plat-SQL corrects the gold SQL, so its EX is closer to "answers the question". The two can move in opposite directions for the same change: a prompt that makes the model answer the question as asked can lose points on the original labels and gain them on the corrected ones. We therefore report both, always on the same questions, and flag failures where the gold is suspect. The data specifics (498 Arcwise rows, Arcwise's own wording for 125 of them, which database copy each gold runs on, how many gold results differ) are in ADR-003. The original Mini-Dev number stays in the headline because it is the leaderboard-comparable one.

### Time limits in scoring (amended 2026-10-17)

BIRD's evaluator gives the prediction and the gold query 30 s of wall time together and scores a timeout as wrong. In our runs that made a score depend on how many questions ran at once: a prediction that takes 9 s alone hit the limit with eight questions in flight, and an offline replay scored it differently. Scoring therefore uses a budget of SQLite virtual-machine steps worth 30 s on the reference machine (`text2sql/sqlite_budget.py`, 2.52e9 steps), with a wall-clock backstop at 150 s, and reads a fixed clock so that the twelve gold queries that compute ages from `'now'` do not change with the day (`text2sql/sqlite_clock.py`).

This departs from the official script, so we measured what it changes (`scripts/time_scoring.py`). Re-scoring all 2,162 distinct prediction and gold pairs in the final reports one at a time on an idle machine, with the step budget: no pair is scored correct that took more than 30 s of wall time (the slowest correct pair took 8.6 s), the 10 pairs that ran past 30 s all ended at the step budget between 31 and 37 s and are scored wrong, as the official limit would score them, and no record's score changed. No pair came near the 150 s backstop. So on these runs the step budget and the official wall-clock limit agree; the step budget only removes the dependence on load.

## Consequences

- Every number in RESULTS.md traces to a report directory, its git SHA and its per-question records, and can be regenerated without network access.
- With 350 dev questions, a 95% interval on EX is roughly ±5 points; most single-component ablations will not be distinguishable from zero, and RESULTS.md says so instead of ranking them.
- The runner must fill the records faithfully: `correct` per candidate and per question, `priced_usd`-based costs, original latencies, safety events, and `gold_suspect` (for example from the questions whose Arcwise gold result differs from the original).
- Runs are compared only within one preset and context. Comparing presets against each other (`fast` against `best`) needs a run of the other preset with overrides, or a manual paired comparison with `metrics.compare_paired`.
- The exact McNemar test and the lack of a multiple-comparison correction pull in opposite directions; we accept both and lean on the intervals when deciding whether to keep a component.

## Sources

All accessed 2026-10-16.

- BIRD Mini-Dev execution-accuracy script: https://raw.githubusercontent.com/bird-bench/mini_dev/main/evaluation/evaluation_ex.py (`calculate_ex` compares `set(predicted_res) == set(ground_truth_res)`; errors and timeouts score 0; per-difficulty breakdown).
- Jin, Choi, Zhu, Kang, "Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards", arXiv:2601.08778: https://arxiv.org/abs/2601.08778 (abstract: 52.8% error rate on BIRD Mini-Dev).
- Chen et al., "Evaluating Large Language Models Trained on Code", arXiv:2107.03374: https://arxiv.org/pdf/2107.03374 (Section 2.1: pass@k as "any of k samples passes" and the unbiased estimator with n ≥ k samples).
- McNemar's test, Wikipedia: https://en.wikipedia.org/wiki/McNemar%27s_test (exact binomial version for small b + c, two-sided p as twice the tail, conservativeness of the exact test, mid-p variant).
- Binomial proportion confidence interval, Wilson score interval section, Wikipedia: https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
