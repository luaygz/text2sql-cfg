# ADR-006: LLM client, response cache, pricing and budget

Status: accepted
Date: 2026-10-16

## Context

Every model call in the project (SQL generation, repair, schema linking, judging, catalog descriptions, embeddings) goes to the OpenAI API, and those calls have to meet four requirements at once. A reviewer without an API key must be able to re-run the evaluation from a committed cache. Spend is real money with a small total budget, so every call has to be priced from a table checked against the pricing page, logged, and stopped before a run crosses its cap. SQL must only ever come out of a forced grammar tool call that is re-parsed locally. And the client has to survive flex-tier capacity errors and rate limits without hand-holding.

These live in one module, `text2sql.llm`, so that no other package talks to the SDK directly:

- `client.py`: `LLMClient` with `sql_call`, `structured`, `embed` and `grammar_accepted`.
- `cache.py`: the SQLite response cache and the request-key function.
- `pricing.py` with `config/pricing.yaml`: per-call cost.
- `budget.py`: the spend ledger, `RunBudget` and `spend_report()`.
- `retry.py`: which errors are retried and how long to wait.
- `text2sql/observability.py`: JSON logging and trace spans.

## Decision

### One path for every call

`sql_call` and `structured` build a request dict and hand it to one private method. It looks the request up in the cache. On a miss it raises `CacheMiss` in offline mode; otherwise it waits for a concurrency slot (`asyncio.Semaphore(Settings.max_concurrency)`), reserves budget, calls the API inside the retry loop, writes the response to the cache, prices it, appends a ledger row, and emits a span and a log event. The caller only ever sees a response that has already been cached, so an offline replay returns exactly what the live run saw. `embed` follows the same steps per batch. Concurrent calls with the same cache key share one API call, and only the first one is billed, so a key always maps to one response.

### Cache and key

The working cache is one SQLite file, `cache/llm/responses.sqlite`, local to each checkout; git holds the same rows as shards (next section). Responses are stored as zlib-compressed JSON of the SDK object, `response.model_dump(mode="json", by_alias=True)`, along with the latency of the original call. `by_alias=True` matters: without it the SDK dumps `ResponseCustomToolCall.async_` under its Python name and the reloaded object no longer equals the original (checked against openai 3.31.0). Headers and the API key are never part of the stored data, and a test greps the cache file, the ledger and the trace file for the key.

The key is the SHA-256 of the canonical JSON (sorted keys, compact separators) of `{"endpoint", "request", "sample"}`. The request includes everything that shapes the output: model, input items, tools including the full grammar definition and description, `tool_choice`, `parallel_tool_calls`, `reasoning`, `text.format` and `max_output_tokens`. Fields that only change how a request is served are left out: `service_tier`, `prompt_cache_options`, `prompt_cache_key`, `store`, and every `prompt_cache_breakpoint` marker inside content blocks. So moving from flex to standard, or moving a breakpoint, keeps the cache hits. `sample` is an explicit index for repeated draws of the same prompt. The reasoning models used here accept no `temperature` or `seed` when reasoning is on, so diversity across samples comes from the model's own sampling, and the index is what keeps the draws apart in the cache.

Embeddings sit in a second table, one row per (model, text, dimensions). A text that was embedded once is never sent again, whatever batch it arrives in. Vectors are stored as raw little-endian float16 when every component survives the float32-to-float16 round trip exactly, and as float32 otherwise; a `dtype` column records which. Every text-embedding-3-small vector we checked (8 vectors, 256 and 1,536 dimensions, 2026-10-16) had at most 10 significant mantissa bits and fitted float16 exactly, so the cache stores the same numbers the API returned at half the size of float32. zlib on top of float16 was measured and rejected: it made 256-d vectors 2% larger and 1,536-d vectors 5% smaller. Measured size including SQLite row overhead: 766 bytes per cached 256-d embedding and 4,188 bytes per 1,536-d embedding (raw float32 would be 1,452 and 8,284). The API reports tokens and latency per batch, not per text, so each row also stores the text's share of its batch's tokens and latency, split by UTF-8 length (largest remainder for tokens, so the shares add up to the billed total).

Requests contain nothing that changes between runs. `store` is false. A repair turn replays the previous `custom_tool_call` item as `{type, call_id, name, input}` without its `ctc_` id, followed by a `custom_tool_call_output` item built by `tool_output_item(call_id, output)` (the type name in `openai/types/responses/response_custom_tool_call_output_param.py`). Reasoning items are not passed back: with `store=false` that would need `include=["reasoning.encrypted_content"]`, and the encrypted blobs would add input tokens and put opaque bytes into the cache key. The `call_id` the model generated is part of the next turn's key, which is stable because that first response is itself replayed from the cache. The live smoke test confirmed that the API accepts a repair turn shaped this way.

### Committed form: shards

Until 2026-10-16 the SQLite file itself was committed. By then it was 36 MB, a day into the project, and was expected to pass 100 MB during the iteration rounds. Every commit of a binary file that changes on each run stores a full new copy in git history, and GitHub rejects files over 100 MB. So the SQLite file is now a local working store that git ignores, and the committed form of the cache is a set of immutable, append-only shards in `cache/llm/shards/` (`text2sql.llm.shards`).

`text2sql cache export` (`make cache-export`) writes every local row that no shard holds yet into a new gzip-compressed JSON-lines file named `<UTC export time>-<first 8 hex of its SHA-256>.jsonl.gz`, and starts another file once the compressed size reaches 45 MB. Shards are never rewritten. Each line is one row: `kind` names the table (responses, embeddings, grammar verdicts, flagged requests) and the other fields are its columns. Response payloads are written as inline JSON and vectors as base64, because gzip over many rows compresses those much better than it compresses the stored zlib blobs: on the 2026-10-16 cache the responses came to 8.8 MB this way and to 21.1 MB as base64 of the zlib blobs. Rows are sorted by table and key, and gzip's timestamp and file-name fields are left empty, so the same rows always produce the same bytes; exporting a copy of the 2026-10-16 store a second time gave a byte-identical file. The store records which rows each shard holds, so a second export writes nothing. Grammar verdicts are the only rows that change after they are written (a rejection replaces an acceptance), so a verdict's identity includes its value and a later rejection goes into a new shard.

`text2sql cache import` (`make cache-import`) loads every shard the store has not recorded, one transaction per shard. Rows already stored win, as with live writes, and verdicts merge as they do live, so a rejection wins in either order. The client runs the same import whenever it opens the store, so a fresh clone, CI, a container or a `git pull` that brings new shards needs no extra step. The check compares a directory listing with the shard names the store has recorded, which costs milliseconds. It deliberately does not compare file modification times: git gives a pulled shard the checkout time, and any local write after the pull would hide it. An export imports pending shards first, so rows that already arrived in someone else's shard are not exported again. When two shards disagree on a key (two machines recorded the same request independently), shards import in name order and the older one's row is kept.

Migrating the 2026-10-16 store gave one shard of 15.7 MB holding all 22,185 rows (9,877 responses, 11,950 embeddings, 358 grammar verdicts, no flagged requests), against 36 MB for the SQLite file. Importing it into an empty store took 2.5 s, the result matched the original table by table, and the committed smoke run replayed offline from the shard alone.

### Grammar calls

`sql_call` validates the grammar offline once per fingerprint (`text2sql.grammar.validate_grammar_offline`), sends the tool `{"type": "custom", "name": "sql_query", "description": ..., "format": {"type": "grammar", "syntax": "lark", "definition": ...}}`, forces it with `tool_choice={"type": "custom", "name": "sql_query"}` and `parallel_tool_calls=false`, takes the first `custom_tool_call` named `sql_query` from the output, and re-parses its input with the grammar's lark parser. Anything else raises `GrammarCallFailed` with a `reason`, the raw input or refusal text, the call meta and, when there was a tool call, the history items needed to answer it in a repair turn. The reasons are `no_tool_call`, `refusal`, `incomplete` and `local_parse` for responses, and `api_rejected` and `flagged` for the two request refusals described below. A response cut off by `max_output_tokens` fails even when its tool input happens to parse, because a truncated query can still be a valid, shorter query.

The API also refuses some grammars that pass offline validation, with HTTP 400 and messages such as "Invalid lark grammar. regex construction fuel exhausted" (found during the API spike; see ADR-001). A 400 whose message mentions "grammar" raises `GrammarRejectedByAPI`, a subclass of `GrammarCallFailed` carrying the provider message. It is not retried and not billed, and no response is cached for it. The rejection is written to a third table, `grammar_verdicts`, keyed by grammar fingerprint, so later calls with that grammar fail at once, online or offline. `grammar_accepted(grammar)` uses the same table: on a miss it sends a probe (the small model, effort `none`, `max_output_tokens=16`) and records the verdict. A rejection overwrites an earlier acceptance; an acceptance never overwrites a rejection. That the verdict does not depend on which model compiled the grammar is an assumption, not something we have tested.

The API can also refuse a prompt as a possible policy violation: HTTP 400 with code `invalid_prompt` ("Invalid prompt: your prompt was flagged as potentially violating our usage policy"). This happened on 2026-10-16 for a gpt-6.1-sol grammar call on a BIRD toxicology question, and the same request succeeded when rerun, so the check is not deterministic. `invalid_prompt` is one of the error codes in the SDK's `ResponseError` type; we found no documentation of when it fires or whether it is billed. The client turns it into `GrammarCallFailed` (or `StructuredCallFailed`) with reason `flagged` and an unbilled meta, so the pipeline drops that candidate instead of aborting the question. It is not retried and writes no ledger row. The refusal is recorded in a fourth table, `flagged_requests`, under the request's cache key. Recording a nondeterministic outcome is deliberate: sampled responses are nondeterministic too, and the cache's job is to replay what the run saw. Without the record, an offline replay of that run would hit a cache miss on the flagged request and fail. A rerun of the same key therefore sees the same refusal; a caller that wants another try uses a new `sample` index.

### Structured output and embeddings

`structured` sends `text.format` as a strict `json_schema` built by the SDK's own strict-schema conversion (`openai.pydantic_function_tool(model)["function"]["parameters"]`, the same conversion `responses.parse` uses) and validates `output_text` with pydantic. Refusals, truncation and schema mismatches raise `StructuredCallFailed`. `responses.parse` itself is not used, because the cache has to own the request and the stored response.

`structured` also takes `max_output_tokens`; see "Output cap" below.

`embed_with_meta(texts, purpose=..., dimensions=None)` returns the vectors and one `CallMeta` for the call; `embed` returns only the vectors. Both use `Settings.embedding_model` (text-embedding-3-small). `dimensions` is passed to the API's `dimensions` parameter, which the embeddings reference documents as supported in text-embedding-3 and later models; it is part of the cache key, and leaving it unset requests the model's full 1,536 dimensions. In the meta, `usage`, `priced_usd` and `api_latency_s` are sums of the stored shares of the distinct texts, so they are identical live and replayed; `cost_usd` is what the call billed and `cache_hit` means no API call was made. Batches hold at most `Settings.embedding_batch_size` texts and an estimated 250,000 tokens, under the API's limits of 2,048 inputs and 300,000 tokens per request. Empty strings are rejected up front, because the API rejects them.

### Output cap

Every Responses request sends `max_output_tokens`, which bounds reasoning plus visible output (reasoning guide). The default, `Settings.max_output_tokens`, is 4,096 (env `MAX_OUTPUT_TOKENS`), and `sql_call` and `structured` take a per-call `max_output_tokens` that replaces it. The value is part of the cache key and is the output allowance in the budget reservation.

The default started at 25,000, the reasoning guide's suggestion for "when you start experimenting", and was lowered after two runaways on 2026-10-16. In one, gpt-6-luna at effort `none` with a strict schema emitted a complete JSON object and then repeated `"\n}"` until the 25,000-token cap, about 125 times the cost of a normal call (1 of about 60 linking calls). In the other, gpt-6.1-sol filled an 8,000-token cap with grammar-valid junk on one BIRD question. A grammar keeps every token parseable, but it cannot stop the model from producing a long parseable query. Normal calls are far below the new default: the SQL calls in the live check below produced 15 to 18 output tokens. At 4,096 tokens the worst case for one gpt-6.1-sol flex call is 4,096 * $5.00 / 1M = $0.020 of output, against $0.125 at 25,000, and the budget reserves accordingly, so runs near their cap are not refused needlessly. Calls at high effort, or callers that know their output is tiny, pass their own value.

A response that stops at the cap is not trusted. `sql_call` raises `GrammarCallFailed` with reason `incomplete` even when the truncated tool input parses, and `structured` raises `StructuredCallFailed` even when the JSON prefix is valid. Both carry the call's meta, and the call is billed and written to the ledger like any other.

### Pricing

`config/pricing.yaml` holds Standard-tier rates per 1M tokens (input, cached input, cache write, output, plus long-context rates above 272K input tokens) for gpt-6.1-sol, gpt-6-luna and text-embedding-3-small. It also holds a multiplier per service tier: default 1.0, auto 1.0, flex 0.5, batch 0.5, priority 2.0. The rates were copied from the pricing page on 2026-10-16, and the Flex and Batch tables on that page are exactly half of Standard for these models. The cost of a call is

    (input - cached - cache_write) * input_rate + cached * cached_rate
      + cache_write * cache_write_rate + output * output_rate,

all times the multiplier of the `service_tier` the response reports. Both points come from the prompt-caching guide: `input_tokens` already contains the cached and cache-write tokens, and cache writes are not an additional fee. Reasoning tokens are part of `output_tokens` and billed as output, per the reasoning guide, so they are not added again. A tier missing from the table is priced at the largest multiplier in it, which can only overstate spend. `auto` is priced as Standard because it resolves to the project's default tier; that holds as long as the project default is not changed.

`CallMeta.cost_usd` is what this call billed (0 on a cache hit). `CallMeta.priced_usd` is the list-price cost of the stored usage at the tier that served it, the same live or replayed, so offline reports can reproduce cost per question. `api_latency_s` is likewise the stored latency of the original call.

### Ledger and budget

Each billed call appends one JSON line to `runs/spend_ledger.jsonl`: timestamp, run id, phase (`T2SQL_PHASE`), purpose, model, served tier, all token counts, cost, latency and request hash. Cache hits are not written there; they are counted in the run summary.

`RunBudget` enforces the per-run cap (`Settings.max_spend_usd`) and the lifetime cap (`Settings.total_spend_cap_usd`, measured against the ledger total read when the budget is created plus this run's spend). Before each call, once a concurrency slot is free, it reserves a worst-case estimate: the request's UTF-8 bytes divided by two as input tokens at the dearer of the input and cache-write rates, plus the full `max_output_tokens` at the output rate. If spent plus reserved plus this estimate would cross either cap, it raises `BudgetExceeded` and the call is not made. When a call returns, the reservation is replaced by the actual cost; when it fails, the reservation is released. Because `max_output_tokens` is sent with every request, the output part of the estimate is a hard bound, and at most `max_concurrency` reservations are outstanding, so concurrency cannot push a run past its cap. The input part is an estimate, not a bound (English and SQL run near four bytes per token), and a property test checks the estimate against the cost formula. A second process writing to the same ledger during a run is not seen until the next run starts. `budget.summary().render()` prints the run's spend and per-model token totals, and `spend_report()` totals the whole ledger by phase and model.

### Retries and timeouts

The SDK's own retries are turned off (`max_retries=0`), so they do not multiply with ours. Up to `Settings.max_retries` (6) retries follow 429, 408, 409, 5xx, timeouts and connection errors. Some 429s are not retried, because the error-codes guide says retrying cannot help: those with code `insufficient_quota`, `credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded` or `organization_usage_limit_exceeded`, or with type `insufficient_quota`. Other 4xx errors are not retried either. A server hint is treated as the minimum wait, with up to one base delay of jitter on top. The hint is `retry-after-ms`, then `Retry-After` (seconds or an HTTP date), then, for a 429 only, the reset time of an exhausted `x-ratelimit-*` bucket. A hint longer than 600 s ends the retries, because the rate-limit guide advises deferring the request rather than retrying sooner. Without a hint, the wait is drawn uniformly from [c/2, c], where c = min(60 s, 1 s * 2^attempt). Flex "resource unavailable" 429s are retried like any other 429, and the flex guide says they are not charged. The request timeout is 900 s, as the flex guide recommends.

### Prompt caching

Every Responses request sends `prompt_cache_options={"mode": "explicit"}`. A `Message` with `cache_breakpoint=True` becomes an `input_text` block carrying `"prompt_cache_breakpoint": {"mode": "explicit"}`, the shape in the prompt-caching guide and in the SDK's `ResponseInputTextParam`. Explicit mode with no breakpoint means no caching and no write charge, so only content a caller has marked as stable is ever written. Callers put the static instructions and schema first, mark the last stable message, and put the question after it. Tools render before the input, so the grammar is part of the cached prefix. The minimum cacheable prefix is 1,024 tokens.

### Observability

`configure_logging()` sets structlog to emit JSON lines on stderr, tagged with the run id and the current trace and span ids. Library modules never configure logging themselves. `span(name, **attrs)` is a context manager that writes one record per finished span to `runs/traces/<run_id>.jsonl`. The record has trace id, span id, parent id, name, kind, start and end in Unix nanoseconds, status and attributes, plus a resource with the service name and run id, following the OpenTelemetry data model without needing an SDK or a collector. Parents come from a context variable, so spans opened in `asyncio` tasks nest under the span that created them. Every client call emits an `llm.responses` or `llm.embeddings` span with model, purpose, request hash, token counts, cost, priced cost, tier and whether it was a cache hit. `start_run(run_id)` sets the run id used by spans, logs and, by default, `RunBudget`.

### Live check

These calls were made on 2026-10-16 with gpt-6-luna on the flex tier, using a 2-column grammar and a developer message of about 3,800 tokens marked as a breakpoint:

| Call | input | cached | cache write | output | cost (USD) |
| --- | --- | --- | --- | --- | --- |
| first question | 3,982 | 0 | 3,836 | 18 | 0.00025155 |
| second question, same prefix | 3,978 | 3,836 | 0 | 15 | 0.00003003 |
| repair turn (tool call + output replayed) | 4,025 | 3,836 | 0 | 18 | 0.00003313 |
| first question again | cache hit | | | | 0 (priced 0.00025155) |
| structured output, effort none | 79 | 0 | 0 | 19 | 0.0000087 |
| grammar probe (status incomplete, as intended) | 218 | 0 | 0 | 16 | 0.0000149 |
| embeddings, 3 texts | 6 | | | | about 0.0000001 |
| embeddings, 4 texts at 256 and at 1,536 dimensions (4 calls over two runs) | 50 per call | | | | 0.000001 per call |

The first call matches the formula: (146 * 0.10 + 3,836 * 0.125 + 18 * 0.50) / 1e6 * 0.5 = $0.00025155. The second call shows the breakpoint at work: a 3,836-token prefix, tools included, read at the cached rate. Every response reported `service_tier: "flex"`. The live pytest (`T2SQL_LIVE_TESTS=1`) made one more call at $0.0000165. Total spent verifying the client: about $0.00036.

## Consequences

- `make eval-offline` can replay any run whose responses are in the committed cache, and an unexpected cache miss fails loudly instead of spending money. Changing a prompt, the grammar, the effort or `max_output_tokens` invalidates the affected keys by design.
- Lowering the default output cap from 25,000 to 4,096 changed the key of every call that relied on the default. When the default changed, 183 of the 724 cached responses had been recorded at 25,000; a caller that needs those rows to replay has to pass `max_output_tokens=25000` explicitly.
- Recording new runs now ends with `make cache-export` and committing the new shard file next to the reports it backs. A forgotten export leaves the rows only on the recording machine, and `make eval-offline` on a clone then fails with `CacheMiss` rather than replaying silently.
- Git history grows by the compressed size of new rows only. Each response still carries an echo of the request's tools, including the grammar, and of the `text.format` schema; together those were about 40% of the uncompressed payload JSON on 2026-10-16. If shards grow faster than expected, the echo can be dropped from stored payloads without changing keys.
- Spend accounting depends on `config/pricing.yaml` being current. A price change means editing that file, not code. A model missing from the file fails at the budget check, before any money is spent.
- The budget's input estimate is deliberately pessimistic, so a run near its cap stops a little early instead of a little late.
- Assumptions we have not verified: that a grammar rejected by the API is rejected the same way for every model; that a 400 rejection, including `invalid_prompt`, is never billed (ADR-001 observed this for grammar rejections, such responses carry no usage, and the ledger records nothing for them); and that `auto` resolves to Standard pricing for this project.
- Flex calls ran at 2 to 8 s latency in the live check. Latency reported from a replay is the stored `api_latency_s`, not the replay's own wall time.
- Float16 storage rests on an observation, not a documented guarantee. If the API starts returning vectors with more precision, `pack_vector` stores them as float32 without losing anything; only the cache gets larger. Per-text token and latency shares inside a multi-text batch are an apportionment; the per-batch totals are exact and are what the ledger bills.

## Sources

All accessed 2026-10-16.

- Pricing (Standard, Batch, Flex, Fast tables; long-context threshold; embedding prices): https://developers.openai.com/api/docs/pricing.md
- Prompt caching (explicit mode, breakpoint shape, 1,024-token minimum, cost formula, write and read multipliers): https://developers.openai.com/api/docs/guides/prompt-caching.md
- Reasoning (reasoning tokens billed as output tokens, `max_output_tokens`, incomplete responses, encrypted reasoning items): https://developers.openai.com/api/docs/guides/reasoning.md
- Flex processing (Batch rates, 900 s timeout, unbilled 429 resource unavailable): https://developers.openai.com/api/docs/guides/flex-processing.md
- Rate limits (headers, `Retry-After` as a minimum, deferring long waits, disabling SDK retries): https://developers.openai.com/api/docs/guides/rate-limits.md
- Error codes (billing and quota 429 codes that should not be retried): https://developers.openai.com/api/docs/guides/error-codes.md
- Embeddings guide and API reference (text-embedding-3-small, 1,536 dimensions, the `dimensions` parameter for text-embedding-3 and later models, 2,048 inputs and 300,000 tokens per request): https://developers.openai.com/api/docs/guides/embeddings.md, https://developers.openai.com/api/reference/resources/embeddings/methods/create.md
- openai Python SDK 3.31.0 type definitions in the project's virtualenv: `types/responses/response_input_text_param.py` (`prompt_cache_breakpoint`), `response_create_params.py` (`PromptCacheOptions`), `response_custom_tool_call_output_param.py`, `response_usage.py` (`cache_write_tokens`), `response_error.py` (the `invalid_prompt` code), `lib/_tools.py` (`pydantic_function_tool`), `_base_client.py` (the SDK's own retry-header handling), `resources/embeddings.py` (`dimensions: int | Omit`; the SDK requests base64 float32 by default).
