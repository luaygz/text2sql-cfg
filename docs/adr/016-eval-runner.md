# ADR-016: Evaluation runner, reproduction and CLI

Status: accepted
Date: 2026-10-16

## Context

ADR-009 fixed what the harness computes from records; this ADR covers how the records get made. The runner has to send a dataset split through the pipeline, score every answer the way the benchmark does, stay inside a spend cap, and leave behind a report that anyone can regenerate without an API key. Four rules shape it: no number in the README that `make eval-offline` cannot reproduce from the committed cache; the held-out test split is touched once; every run prints its spend and aborts past its budget; a partial run is labelled partial.

Three result tables need three scoring paths. Original Mini-Dev gold belongs to the Mini-Dev database package, Arcwise-Plat-SQL gold to the BIRD Dev release (ADR-003), and the SaaS set (ADR-017) scores answers with bound tenant parameters, abstentions, and leak checks rather than gold SQL alone.

Code: `src/text2sql/evals/datasets.py` (items per table), `scoring.py` (one item to one `QuestionRecord`), `runner.py` (`run_eval`), `reproduce.py`, and `src/text2sql/cli.py`.

## Decision

### Run shape

`run_eval` is `plan_run`, then `execute_plan`, then `finish_run`. The plan fixes the configuration (a preset plus `--set` overrides, re-validated by `apply_overrides`) and the questions. `--limit N` takes a seeded sample of N items kept in dataset order, so a limited run always picks the same questions and covers several databases rather than the first database in the file. Evidence is a run setting, not an override: `--no-evidence` sets `PipelineConfig.use_evidence` and `RunRecord.with_evidence` together, and `--set use_evidence=...` is rejected so the two cannot disagree.

Overrides are stored in `RunRecord.overrides` typed (`n_candidates=3` as an integer) and under the names RESULTS.md uses to place a run: `generator_effort` is recorded as `effort`, so an effort override lands in the effort sweep, an `n_candidates` override in the N sweep, and anything else in the ablation table. `RunRecord.config` holds the full pipeline configuration plus model names, service tier, the limit and the sample seed.

Questions run concurrently under a semaphore (`--concurrency`, default 8) through one `Pipeline`, so its per-prefix prompt-cache gate (ADR-014) is shared across questions: the OpenAI prompt-caching guide says the first request writes a prefix and later ones reuse it, and the pipeline lets the first candidate on a schema prefix write it while the rest wait. The runner therefore adds no ordering of its own beyond dataset order.

### Budget and partial runs

Each run has one `RunBudget` (`MAX_SPEND_USD`) shared by the pipeline and the failure classifier. When the budget refuses a call, the question that hit it is dropped, no new question starts, questions already in flight finish, and the report is marked partial with the budget's message as the reason. RESULTS.md shows partial runs as `partial: k/n`. If the budget runs out while labelling failures, the run keeps its scores and leaves those failures unlabelled. A run stopped before any question finished writes no report. The spend summary (`RunBudget.summary().render()`) is printed when a run ends, also when it fails.

### Scoring

BIRD: the final SQL and every candidate that passed the guard and executed in the sandbox are scored with `bird_metric.execution_match`, the reimplementation of `evaluation_ex.py`: prediction first, one 30 s deadline for both statements, `set(pred) == set(gold)`, any error a miss. Candidates the guard rejected, or that failed or timed out in the sandbox, count as wrong for pass@N, because the selector could never have chosen them. Scoring runs on the gold's own database release: the pipeline always runs on the Mini-Dev package, and an Arcwise item is re-scored on the Dev release. An Arcwise item whose question and evidence Arcwise did not change sends exactly the original request, so it replays from the response cache at no cost; only the reworded items need new calls. An original Mini-Dev item is `gold_suspect` when its Arcwise-Plat-SQL correction returns a different result on the same database, or when the original gold fails to run.

Linking recall uses `metrics.gold_columns` against the schema the model sees; for SaaS that excludes the tenant column the scoping layer adds. Grammar coverage normalises the gold with `normalize_sql` and parses it with the pipeline's full-schema grammar; it is left empty for SaaS, whose gold carries tenant filters and parameters the model never writes.

SaaS: the scoped SQL that the executor ran is re-executed next to the gold with the item's bound parameters, under the same EX semantics (`execution_match(..., params=...)`). A tenant-bucket item is asked once per tenant in `eval_tenants` and is correct only if every tenant gets its own right answer. That keeps one record per item: expanding each tenant into its own record would count correlated outcomes as independent and narrow the intervals falsely. The record shows the requesting tenant's run; its candidates are scored by re-binding their scoped SQL to every tenant. Cost and latency are the requesting tenant's run, the cost of answering the question once. Unanswerable items are correct iff the system abstained. Every SaaS item, not only adversarial ones, goes through `safety.leaks.judge_attack` over all executed candidates; a leak sets `safety_violation`. An adversarial item is correct iff nothing leaked and, when the attack wraps a legitimate question, the system either abstained or answered that question correctly. A clarification request counts as neither an answer nor an abstention.

Cost per question is the trace's list price (`CallMeta.priced_usd`) and latency the trace's model-latency critical path (`CallMeta.api_latency_s`, stages summed, parallel candidates maxed, local execution excluded). Both come from the cached responses, so an offline replay reproduces them exactly; wall-clock time would not.

### Held-out split

`--split test` and `--split all` (which contains the test questions) require `--allow-test`. Every such run is appended to `runs/held_out_runs.jsonl` before it starts, so even a run that crashes before writing a report leaves a trace; RESULTS.md also counts test-split reports per table.

### Reproduction

`text2sql reproduce [REPORT_DIR ...]` (`make eval-offline` with no arguments) replays each report with `offline=True`: the stored pipeline configuration, not today's preset, on exactly the questions in its `per_question.jsonl`. It passes only if every replayed `QuestionRecord` equals the stored one field for field, the recomputed summary equals the stored summary, and RESULTS.md is exactly what the reports render to. A cache miss fails the report: today's code sends a request the recorded run never made. Failure labels are replayed only where the run produced them, and labels a reviewer assigned by hand are carried over. A replay is not a new test-split run and is not logged as one. `make smoke-offline` replays a single committed smoke report, which is what CI runs.

### CLI

`text2sql` (typer and rich) has `ask` (one question with the trace: grammar sizes, candidates, result clusters, selection, final SQL and rows), `eval`, `reproduce`, `report` (regenerate RESULTS.md), `spend` (ledger by phase and model), `grammar --db --show [--mode]` (the full-schema grammar the pipeline builds), and mounts `catalog`, `index` (the value and few-shot index builder, ADR-011), `safety` (the adversarial suite, ADR-015) and `demo` (the web demo, loopback by default). Argument errors (unknown preset or setting, a test split without `--allow-test`, a tenant on a BIRD database, SaaS outside tenant mode) exit with status 2 before any model call. Commands import the pipeline and the OpenAI SDK lazily.

## Consequences

- A report is only as durable as the requests it recorded. Changing a prompt, the grammar, a tool description, a model name or the pricing table makes old reports fail `reproduce`. That is the point of the check, but it means reports from earlier iteration rounds must be re-run or moved out of `reports/` (they are kept under `reports/experiments/`, which `make eval-offline` does not replay, and described in EXPERIMENTS.md) before `make eval-offline` can pass at HEAD.
- Offline replay needs the BIRD databases (`make data`), the catalogs (`OFFLINE=true make catalog`) and, for presets with retrieval, the indexes (`OFFLINE=true make index`); all three rebuild from the committed cache without an API key.
- Previews of gold and predicted rows are kept for failures only, from a separate read-only execution with its own 30 s limit; they never affect a score.
- R-VES is not computed: its timing loop does not reproduce exactly offline. The records leave it empty, so the summary shows none.
- Asking a tenant-bucket question once per tenant multiplies its pipeline runs; the extra runs are mostly cache hits because the model never sees the tenant, but repairs that depend on the tenant's rows are billed.

## Sources

All accessed 2026-10-16.

- BIRD Mini-Dev `evaluation/evaluation_ex.py`: https://raw.githubusercontent.com/bird-bench/mini_dev/main/evaluation/evaluation_ex.py (`calculate_ex` compares `set(predicted_res) == set(ground_truth_res)`; one `func_timeout(meta_time_out, execute_sql, ...)` around both statements, default 30 s; timeouts and errors score 0).
- OpenAI, Prompt caching guide: https://developers.openai.com/api/docs/guides/prompt-caching.md ("The first request writes an eligible prefix to the cache and subsequent requests look for the longest matching cached prefix available"; cache writes at 1.25x input for GPT-5.6 and later; 30-minute minimum lifetime).
