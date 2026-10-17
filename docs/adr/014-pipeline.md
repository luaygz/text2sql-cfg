# ADR-014: Pipeline composition, abstention and presets

Status: accepted (presets revised after the iteration rounds)
Date: 2026-10-16

## Context

ADR-008 describes the stages of one request and where each idea comes from. Four packages implement them: retrieval (ADR-011: question analysis, value index, schema linking, few-shots), generation (ADR-012: strategies, prompts, repair turns), selection (ADR-013: clustering, vote, judge, unit tests) and the guard (ADR-015: the four safety layers in one call). `text2sql.pipeline` composes them. What ADR-008 leaves open, and this ADR decides: which failures stop a candidate and which feed repair, when the pipeline abstains or asks to clarify, how the cheap path reuses work, which grammar each candidate gets, what a trace records for the eval runner, and the three named presets.

## Decision

### Stages and switches

A request runs these stages in order; each opens a trace span `pipeline.<stage>` and is recorded in `PipelineTrace.stages` with its wall time, API latency and calls:

| Stage | Runs when | Calls |
| --- | --- | --- |
| `resources` | always | none; loads `DatabaseResources` once per database and mode |
| `analysis` | `question_analysis` | 1 small-model structured call (effort `none`, as the few-shot pool skeletons were made) |
| `values` | `value_retrieval` | embeddings for re-ranking LSH candidates |
| `linking` | `schema_linking` | 1 embedding call, then 2 small-model passes at once |
| `fewshots` | `fewshot_k > 0` | 1 embedding of the skeleton |
| `grammars` | always | none |
| `cheap_path` | `cheap_path` | the two cheap candidates |
| `candidates` | unless the cheap path answered | the rest of the schedule |
| `selection` | always | judge or unit-test calls when they run |
| `explain` | `explain` | 1 small-model structured call |
| `answer` | always | none |

`PipelineConfig` validates combinations that cannot work rather than silently doing less. Value retrieval, schema linking, few-shots and the cheap path all need the question analysis (keywords, skeleton, complexity), so turning analysis off with any of them on is an error. The cheap path needs at least two candidates, and both `small_linked` and `direct_full` among the first N of the schedule. `grammar=false` (the ablation) requires `repair=false`: a JSON candidate has no tool-call conversation to continue, and the ablation should compare like with like. `literal_check=true` requires `repair=true`, since the check only triggers repair turns. `apply_overrides` parses CLI `--set key=value` by field type and re-validates; `name` cannot be overridden, because reports pair the preset name with its overrides.

A structured call that fails in the analysis stage drops the analysis and the stages that depend on it, with a line in `trace.warnings`; schema linking already tolerates a failed pass on its own (ADR-011). Only `BudgetExceeded`, `CacheMiss` and `FileNotFoundError` (a missing catalog or index) leave `Pipeline.run`; when one candidate raises, the other candidates are cancelled and the original exception is re-raised, not an `ExceptionGroup`.

### Resources, modes and limits

`DatabaseResources` holds the catalog, the full schema (including `tenant_id` and hidden columns, which scoping needs), the visible schema, the full-schema grammar, the rendered full schema, the guard, and the value and column indexes, loaded on first use. For SaaS the full schema comes from the database file, because the catalog leaves out what the model must not see. The mode fixes the limits, so grammar, validator and executor agree:

| Mode | LIMIT bound and executor row cap | Executor timeout | Abstain allowed |
| --- | --- | --- | --- |
| benchmark | 1,000 | 10 s | no |
| production | 200 | 2 s | yes |
| tenant | 200 | 2 s | yes |

The benchmark timeout is longer than the 2 s default of the other modes because some BIRD gold queries take seconds on the larger databases, and a candidate killed for being slow is a lost candidate; EX itself is scored separately with BIRD's 30 s evaluator. The SaaS database is served only in tenant mode: without scoping every tenant's rows would be readable. BIRD is served in benchmark or production mode. `full_grammar(db_id, dataset=, mode=)` builds the same grammar without loading an index or starting executor workers, for the demo's grammar view.

### Grammars

The full-schema grammar is built once per database and mode from the visible schema. The linked grammar is built per request from the linked schema, intersected with the visible schema so that nothing linking returns can widen what the model may name. With linking off, the linked view is the full view (same grammar, same prompt text), so linked strategies share the cached prefix. When the full-schema grammar does not fit `GrammarSize.fits_api_budget`, the full view keeps the full schema in its prompt and uses the linked grammar (ADR-008: the widest grammar that fits), its layer-2 allowlist becomes the linked schema, and a warning is logged and kept in the trace; with linking off there is nothing to fall back to, so the full grammar is tried and the API decides. All Mini-Dev grammars fit (ADR-005), so this path exists for larger schemas.

### Candidates and repair

The candidates are the first N entries of `generation.schedule(config.strategies, N)`, run concurrently. `generator_effort` overrides the effort of generator-tier strategies only. Each output goes through `QueryGuard.run` with the candidate's view grammar and, for linked candidates, the linked schema as the layer-2 allowlist.

Repair (at most `max_repairs` per candidate, each continuing the candidate's own conversation) is triggered by:

- an SQLite error (`QueryFailed`, including the executor's result-size limit);
- a timeout. We decided to repair timeouts: the usual cause in BIRD is a missing join condition or an unfiltered scan, which the model can fix when told; the cost is bounded by `max_repairs` and the 2 s or 10 s limit;
- a layer-2 rejection (`validator`), fed back as `rule: detail`;
- an empty result when the analysis says the question expects rows (`may_be_empty` false). Without an analysis, empty results are not repaired: DIN-SQL's finding that telling a model its correct query is wrong lowers accuracy argues against guessing.
- with `literal_check`, a string the query compares a column with that the column does not hold, while close values are stored (next section). When the result is also empty and rows are expected, this trigger is used instead of the empty-result one, because it names a likely cause.

Rejections by the scoping layer or the executor's authorizer are not repaired. They are safety stops; feeding them back would let the model probe the guard. Error and empty feedback carries value hints: the retrieved values of every matched column the failing SQL names. A candidate's final state is its last attempt that executed (so a repair that turns an empty result into an error keeps the empty result), else its last attempt that produced SQL or an abstention.

A failed grammar call (`GrammarCallFailed`, including `GrammarRejectedByAPI`) ends the candidate; it is never retried as free text. Every grammar call and every failure is counted per candidate (`grammar_calls`, `grammar_failures`, the runner's grammar rejection rate). A `local_parse` failure, where the API returned a tool input the local grammar rejects, is logged as a layer-1 (`grammar`) safety event: the grammar stopped that text before the guard saw it. API-side failures (`no_tool_call`, `refusal`, `incomplete`, `api_rejected`) are API health, not safety events; an API rejection of a grammar also adds a trace warning, since every call with that grammar will fail.

### Literal check

The round-0 review found the model copying a value as the evidence spells it when the database stores another spelling (`status = 'legal'` where the column holds `'Legal'`, `'strength'` for `'Strength'`); the query runs and returns nothing or a wrong count. ADR-008 plans OpenSearch-SQL's value alignment as feedback to the repair turn rather than a rewrite of the model's SQL, and `pipeline/literals.py` implements it. It is off by default (`literal_check=false`); the `fast` and `best` presets turn it on.

After a candidate executes, empty or not, the check collects every comparison of a bare column with a string literal: `=`, `!=`/`<>`, `IN (...)` and `LIKE` without `%`, `_` or `ESCAPE`, wherever it sits (WHERE, ON, CASE WHEN). sqlglot's qualify and scope walk resolve the column to its base table through T1..Tn aliases, correlated subqueries, derived tables and CTEs whose output is a bare column; a computed output such as `lower(T1.status)` is not followed. Columns without SQLite TEXT affinity (INTEGER, REAL, DATE and DATETIME in BIRD) are skipped, as are queries sqlglot cannot qualify; at most 10 comparisons are checked per query. A literal counts as missing only when no row matches it under the query's own operator (so `LIKE 'legal'` on `'Legal'` is fine). It triggers a repair only when the column holds something close: up to three values equal to it after `lower(trim(...))`, or, when value retrieval ran, the retrieved values for that column. A missing literal with nothing close (a real empty answer, most likely) does not trigger.

The lookups never run model text as SQL. Each query is built from the schema's table and column names, double-quoted, with the literal as a bound parameter, on a dedicated `mode=ro` connection with `query_only` set and a progress handler that stops all lookups of one query after 2 s; a lookup that fails or runs out of time is skipped. The lookups read any visible column, which in tenant mode would expose other tenants' spellings, so the check runs only in benchmark and production mode. It runs only when a repair can follow (`number < max_repairs`), and a `value` repair counts against `max_repairs` like the others.

The feedback (`repair` prompt 1.2, sections `value` and `value_check`) states what was observed, one line per literal, for example "legalities.status has no value 'legal'. Stored values that differ from it only in case or surrounding spaces: 'Legal'.", and asks the model to use the stored value if the question means it and otherwise to resubmit the query unchanged, following DIN-SQL's finding that asserting a correct query is wrong lowers accuracy. Generic value hints are not appended; the stored values are already in the observation. The attempt records the trigger as `Attempt.repair_kind == "value"`.

Replayed offline on the 350 round-0 predictions without value retrieval, the check fires on 4 queries (415, 766 and 769 from the review, and 640, `'Mornington'` for `'mornington'`), all of them failures, and on no correct prediction; the lookups took 0.8 s in total and at most 0.11 s per query. The review's other literal failures are not caught: 563 compares a DATETIME column, which is skipped; 1350 (`'2019-8-20'` in a TEXT column holding `'2019-08-20'`), the wrong `'Melbourne'` (945) and the garbled title of 584 have no case or spacing variant; 1113 is a wildcard `LIKE`. Those need value retrieval, date normalisation or a prompt change.

### Prompt-cache warm-up

All full-view candidates of a database share their cached prefix (tools plus developer message 1, ADR-012), but only after one request has written it. Launched together, five candidates on a cold prefix each pay the 1.25x write. The pipeline keeps one gate per prefix (full-schema grammar fingerprint, model, effort): the first candidate on it runs alone, the others on that prefix wait for it, and every later question finds the gate open. The cache lives at least 30 minutes after its last use on GPT-5.6 and later models, so one warm-up per database and process is enough for a run. The wait is recorded as `CandidateTrace.gate_wait_s` and left out of `model_latency_s`.

### Abstain and clarify

Only production and tenant modes, where the grammar admits `ABSTAIN: <reason>`; benchmark mode always answers when a candidate executed.

- Abstain when more than half of the candidates that produced output (SQL or an abstention) abstained, or when some abstained and none executed. The reason is the most common abstention reason, ties to the earliest candidate in schedule order. Confidence is the abstaining share.
- Clarify when the executed candidates fall into more than one cluster and none holds more than a third of them, for example three candidates with three different results. Confidence is the largest cluster's share. With two candidates no split can trigger it.
- Otherwise select. With no executed candidate the answer is `failed`, with the count of candidate outcomes as the reason.

The thresholds are a starting point to tune on the SaaS dev questions (ADR-017); the abstain precision and recall metric there is what moves them.

### Selection gating

`first` takes the earliest executed candidate (the baseline). `vote` is `majority_vote` with the schedule position of each strategy as its rank and `prefer_non_empty` unless the analysis says an empty result is plausible. `judge` and `unit_test` first vote, and call the LLM selector only when there is more than one cluster and the winner's share is below `judge_threshold`; with the pairwise judge asking every ordered pair of representatives, gating is what keeps its cost bounded. Confidence in the answer is the chosen cluster's vote share.

### Cheap path

The first `small_linked` and `direct_full` candidates in the schedule run first (stage `cheap_path`). If both execute with rows and no repair, their results form one cluster, and the analysis classes the question `easy`, their answer is returned. Otherwise the rest of the schedule runs and the two cheap candidates are reused as its members, so an escalated question costs the same N candidates as without the cheap path. Candidates are indexed in the order they were generated, so `trace.candidates[i].index == i` either way.

### Answer

The answer carries the model's SQL (the trace also holds the scoped SQL that ran and its bound parameters), the first 10 rows, and the schema elements, which are the base columns the SQL reads, resolved with sqlglot through aliases and subqueries (`evals.metrics.gold_columns`). An earlier design took the schema elements from the small-model explanation call; we read them from the SQL instead, since that is exact and free. The optional explanation (`explain`, off in benchmark runs) is one small-model call that sees the question, the SQL and those elements but no result rows: rows are database values, which may carry planted instructions (ADR-015), and describing what a query does needs none of them.

### Trace, latency and events

`PipelineTrace` holds the analysis, matched values, link result, few-shots, grammar fingerprints and sizes per view, every candidate with every attempt (call metadata, SQL or abstention, guard rejection, execution error, guarded result with executed SQL and parameters, result fingerprint, repair feedback and the kind of repair it triggered), the clusters, the selection, the safety events, the cheap-path flag, prompt tags and per-stage records. Safety events reach the trace through a context variable: the shared per-database guard writes every event to the JSONL log through `CollectingEventLog`, which also appends it to the list of the request whose task is running, so concurrent requests never see each other's events.

Two latencies are kept. `elapsed_s` is wall time. `model_latency_s` is the critical path over the API latency stored with each response: sequential stages add up, concurrent candidates take the slowest, schema linking is its embedding call plus the slower of its two passes, the judge the slowest of its concurrent comparisons, unit tests the writer plus the slowest check. Local execution time is left out. Because response metadata is replayed from the cache, an offline replay reports the same `model_latency_s` as the run that paid for the responses, which is what the p50 and p95 in reports need. `cost_usd` is list price including cache hits, `billed_usd` what the run was charged.

`Pipeline.run(request, on_event=...)` optionally calls back with `PipelineEvent(stage, status, elapsed_s, data)` at the start and end of each stage, once per finished candidate, for the clusters and the selection, and with the answer and total cost at the end. The callback is synchronous; an exception in it is logged and ignored.

### Presets

| Preset | Analysis | Values | Linking | Few-shots | Strategies (N) | Effort | Repair | Literal check | Selector |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline` | off | off | off | 0 | direct_full (1) | medium | off | off | first |
| `fast` | off | off | off | 0 | direct_full (1) | low | 2 | on | vote |
| `best` | off | off | off | 0 | direct_full (1); schedule direct_full, divide_conquer, query_plan for N > 1 | medium | 2 | on | vote |

The first versions of `fast` (cheap path over three strategies) and `best` (every stage on, five candidates, judge) were provisional. The iteration rounds (EXPERIMENTS.md, R0 to R13) measured each component on the dev split and kept what earned its cost: the BIRD conventions in the prompt (a prompt change, so every preset gets it), the trailing-newline grammar fix, and repair with the literal check (no measurable gain or cost, kept as a safety net). Voting over five full-schema candidates gained 2.0 points before the grammar fix and 0.3 after it (R13): it had been voting away decoding artifacts. So `best` is one `direct_full` candidate; its schedule names two more full-schema strategies so that an N-sweep (`--set n_candidates=k`, voted) shares the cached prompt prefix. `fast` is `best` at low reasoning effort, the lowest-latency configuration measured. The mixed-model ensemble, the judge, unit tests, few-shots, value retrieval and the cheap path remain available through overrides and appear as rows of the results tables.

### Live check

On 2026-10-16 (`T2SQL_PHASE=pipeline`, flex tier, run cap $0.40) `baseline` and `best` ran on three BIRD dev questions from `toxicology` (195 simple, 197 moderate, 206 challenging) and two hand-written SaaS questions in tenant mode (tenant 3: open tickets per priority; five accounts with the highest invoiced total). The few-shot pools were not built yet, so `best` ran with `fewshot_k=0`. Costs are list prices per question (`trace.cost_usd`); latency is `model_latency_s`.

| Question | baseline | best |
| --- | --- | --- |
| BIRD 195 | correct, $0.0007, 2.3 s | correct, 5/5 agree, $0.0054, 13.6 s |
| BIRD 197 | failed (output cap), $0.0209, 36.0 s | wrong, 4/5 agree, $0.0072, 20.2 s |
| BIRD 206 | correct, $0.0012, 4.4 s | correct, 5/5 agree, $0.0074, 18.2 s |
| SaaS tickets | answered, $0.0009, 2.7 s | answered, 4/5 agree, $0.0069, 10.6 s |
| SaaS invoices | answered, $0.0014, 3.6 s | answered, 4/5 agree, $0.0075, 13.2 s |

In `best`, question analysis took 2.1 to 2.8 s and under $0.0001, schema linking 7 to 9 s on BIRD and 2 to 3 s on SaaS (two small-model passes), and the five candidates 3.7 to 9.1 s for $0.005 to $0.007; linking is the slowest stage on BIRD. No judge call was made: the top cluster always held at least 4 of 5 votes. The whole check, including one run that aborted, cost $0.06 in the ledger.

Two problems surfaced, both outside this package. On question 197 (evidence `bond_type = '-'`) every `gpt-6.1-sol` candidate wrote the literal `'-'` with a stray character before the closing quote (`'-聖'`, `'- counsel'`), and the baseline call ran to the output cap; `gpt-6-luna` wrote `'-'` correctly, and the grammar accepts `'-'` under lark and byte-level llguidance, so this looks like a server-side constraint or tokenization issue (ADR-005 describes the grammar fix). The four broken candidates agreed on a NULL result and won the vote. And a first attempt at the run stopped when the API answered one toxicology request with HTTP 400 `invalid_prompt` ("flagged as potentially violating our usage policy"), which the LLM client raised untyped; the same request succeeded on retry (the client now turns such a refusal into a dropped candidate rather than an aborted question, ADR-006).

## Consequences

- Every stage can be switched off for the ablation table, and impossible combinations fail at configuration time rather than producing a run that quietly measures something else.
- Repairing timeouts and validator rejections costs extra calls on hard questions; the trace records each attempt, so the repair stage's cost and its share of fixed candidates can be read from any run.
- The abstain and clarify thresholds are untuned guesses. Benchmark numbers are unaffected by them.
- `model_latency_s` assumes the concurrency the code has today (candidates, linking passes, judge comparisons). If a stage's internal concurrency changes, its critical-path rule must change with it.
- The warm-up gate delays the first question per database by one candidate's latency. A run that interleaves many databases pays it once per database.
- With few-shot pools not yet built, a `best` run needs `--set fewshot_k=0` until `python -m text2sql.retrieval build` has produced them; the pipeline raises `FileNotFoundError` with the build command otherwise.
- The literal check costs a table scan per missing literal and one repair call where a compared value has a close stored variant; in the round-0 replay that was 4 of 350 questions. Its lookups are a second, read-only path to the database next to the guard, kept safe by building the SQL from schema names and binding the literal, and kept out of tenant mode.

## Sources

- ADR-005, ADR-008 (OpenSearch-SQL value alignment and DIN-SQL's feedback wording, as summarised there), ADR-011 to ADR-013 and ADR-015 in this repository.
- Round-0 failure review, `docs/research/failure-review-r0.md` (recommendation 1 of the most actionable patterns).
- OpenAI prompt caching guide, https://developers.openai.com/api/docs/guides/prompt-caching.md (read 2026-10-16): cache writes at 1.25x and reads at 0.05x of input price for GPT-6.1 Sol, a cached prefix stays reusable for at least 30 minutes after its last write or reuse, and the prefix includes tool definitions.
