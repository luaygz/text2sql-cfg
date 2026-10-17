# ADR-011: Retrieval (question analysis, value retrieval, schema linking, few-shot retrieval)

Status: accepted
Date: 2026-10-16

## Context

ADR-008 plans pipeline stages 2-4 as: a small-model analysis of each question (literals, keywords, a masked skeleton, requested outputs, a complexity class); value retrieval in three passes (exact, MinHash LSH as in CHESS, embedding re-rank of LSH candidates only); schema linking as an embedding shortlist followed by a recall-first LLM selection run twice with two fixed table orders; and few-shot retrieval over masked question skeletons (DAIL-SQL). The code is `src/text2sql/retrieval/`, the prompts are `prompts/question_analysis.yaml` and `prompts/schema_linking.yaml`, and the indexes live under `data/indexes/` (gitignored).

Constraints that shaped the decisions: the API budget ($0.60 for retrieval), the committed response cache (every LLM response and embedding lands in the response cache, which is committed to git as shards under `cache/llm/shards/`), and the SaaS database, where one index is shared by every tenant's requests.

## Decision

### Question analysis

One `gpt-6-luna` structured call, effort `none` (`DEFAULT_ANALYSIS_EFFORT`), returns `QuestionAnalysis(literals, keywords, skeleton, requested_outputs, complexity, may_be_empty)`. The prompt merges CHESS's keyword-extraction template with Agentar-Scale-SQL's task-understanding prompt (literals plus a skeleton where literals become kind tags such as `<YEAR>` and schema mentions become `<COLUMN>`), adds OpenSearch-style requested outputs and DIN-SQL's three classes, and carries six worked examples written for domains outside Mini-Dev. It sees no schema, so the 1,935-token instruction block is identical for every database and sits behind a cache breakpoint: in the pilot every call after the first read it from the prompt cache. Version 1.1 narrowed `may_be_empty` to existence checks and "if any" requests after version 1.0 marked most list questions as possibly empty, which would have switched off repair-on-empty for them.

All structured calls go through `calls.structured_call` with an output cap (2,000 tokens for analysis, 3,000 for linking). In the first measurement one linking call wrote a complete JSON object and then about 25,000 tokens of newlines and braces until the global limit, costing $0.0063 where a normal call costs $0.00005. The cap bounds that, and because the object itself was complete, it is recovered from the cut-off text (`LLMClient.structured` gained `max_output_tokens` for this).

### Value retrieval (`ValueIndex`)

Offline, per database, from the catalog and the read-only SQLite file. Columns are indexed with CHESS's filters: text-typed (or untyped), not a primary key, no `id`, `url`, `email`, `web`, `phone`, `date`, `time`, `address` in the name, and CHESS's size rule (a name column under 5M characters of distinct values, or under 2M characters averaging under 25, or fewer than 100 distinct values). Three changes: name filters match whole name tokens (CHESS's substring `date` also skips `candidate`); `street`/`str` count as addresses (california_schools has four street columns with about 13,000 values each, which questions return but never filter on); and a column is skipped when more than half its distinct values have no letters but a digit, or look like a date, URL, e-mail or UUID. Those are compared as numbers or dates, not named in words, and character 3-gram similarity between digit strings is noise (this dropped the zip, phone-like and numeric-text columns, for example `formula_1.lapTimes.time` and `california_schools.schools.Zip`). Values longer than 100 characters are dropped individually.

Signatures are datasketch `MinHash` over lowercase character 3-grams with CHESS's 100 permutations; the LSH threshold is CHESS's 0.01. For those parameters datasketch chooses 100 bands of one row, so a value is a candidate when any of its 100 min-hashes equals the query's. datasketch's `MinHashLSH` keeps band keys in Python dictionaries; inserting 50,000 short strings took 16 s and about 700 MB, and card_games alone has 216,602 indexable values. The bands are therefore stored as sorted numpy arrays (searched with `searchsorted`, memory-mapped on load, 800 bytes per value); a test checks that the candidate sets equal datasketch's `MinHashLSH.query` on the same strings, and the share of equal min-hashes is the Jaccard estimate CHESS ranks by.

`match` searches each literal and keyword, the parts before and after each space and the right-hand side of `=` (CHESS's search strings), plus quoted spans of the question: (1) case- and whitespace-insensitive exact lookup over all indexed values; (2) LSH top 10 per string, kept at difflib ratio 0.3 or more, then per column within 0.9 of the column's best ratio; (3) with an LLM client, embeddings of those survivors and their search strings only, kept at cosine 0.6 or more and within 0.9 of the column's best. Exact hits come first; at most five values per column (the number `render_matched_values` shows).

Index sizes: california_schools 39,177 values, card_games 216,602, codebase_community 43,049, debit_card_specializing 541, european_football_2 11,476, financial 144, formula_1 3,072, student_club 21,194, superhero 1,526, thrombosis_prediction 297, toxicology 23, saas_crm 177. Building all twelve takes about 30 s and about 270 MB of disk, card_games 171 MB of it. BIRD indexes are built from the Mini-Dev copies of the databases (`release="minidev"`); the dev release has a few more rows in three databases, so a handful of values that exist only there are not indexed.

### Tenant data in the SaaS index

The value index is one file shared by every tenant's requests, like the catalog, so a matched value could reach a prompt of a tenant that does not own it. Scoping matches per tenant would need tenant ids stored per value and a `ScopeContext` in `match`; instead tenant-scoped tables (`samples_withheld` in the catalog) are skipped unless the build gets the `ScopePolicy`, and with it only columns with at most 50 distinct values are considered and only values present in every tenant are indexed. What survives is shared vocabulary: deal stages, ticket priorities and statuses, payment methods, team names and the templated ticket and activity subjects. Account and contact names, canaries (a test checks that none of `canary_values()` is indexed) and anything that only some tenants have never enter the index, so any matched value also exists in the caller's own tenant. Casing variants survive only if every tenant has them; `tickets.priority` keeps `High`, `high`, `URGENT` and the like because all eight tenants do. In user mode (owner scoping) a value may come from rows of another user of the same tenant; since it is vocabulary that every tenant has, it says nothing about those rows, and we accept that.

### Schema linking

1. Embedding pass. One document per column (table name and description, column name, human or LLM description, value description) is embedded once per database and stored in `data/indexes/<db_id>/columns.npy`. The question, the evidence and each keyword are embedded and each contributes its five nearest columns (CHESS's top 5). CHESS embeds question-plus-keyword and evidence-plus-keyword; bare keywords repeat across questions, so their embeddings are cache hits and the committed cache grows less.
2. LLM pass, twice. The small model gets the schema rendered by `render_schema` in catalog order, and in a second call with tables and columns reversed. Each order is a fixed developer-message prefix per database with a cache breakpoint, so both stay cached (linking calls read about 5,000 cached tokens each on california_schools). The user message holds the matched values, the 15 best shortlist columns as hints, the evidence and the question. The model returns `{tables, columns}` with a recall-first instruction.
3. Assembly (`assemble`): the union of both answers, the value-matched columns and the top 5 shortlist columns, then every primary key of a kept table, declared foreign keys between kept tables, and key columns that kept tables share by name (a primary key in one of them, or `id` in the name). Most Mini-Dev databases declare few foreign keys, so without that rule `transactions_1k.CustomerID` disappears when `customers` is selected.

ADR-008 planned to show the model only the tables the shortlist touches. Every Mini-Dev schema renders under 7,000 tokens and saas_crm under 4,000, so the model sees the whole schema whenever it renders under 12,000 tokens (`FULL_VIEW_MAX_TOKENS`). A cached full schema is cheaper than an uncached per-question subset, and the model can pick join tables the shortlist missed. Wider schemas fall back to the touched tables.

### Few-shot retrieval (`FewShotIndex`)

Pools: "bird" is `load_bird_train()` (6,601 filtered train pairs), "saas" is `data/saas/fewshot_pool.jsonl` from the SaaS eval builder (40 pairs, no evidence). Every pool question is masked by `analyze_question` itself, same prompt, model (`gpt-6-luna`) and effort (`none`), and the skeletons are embedded and stored under `data/indexes/fewshot/<pool>/`. `retrieve` embeds the test skeleton and returns the k nearest by cosine, skipping repeated questions or SQL. Pool SQL is stored as `normalize_sql(sql)` (without a schema, since the train databases are not downloaded), or as written when it does not normalize, so examples look like what the grammar forces.

Masking the pool with gold SQL locally would have been free: literals in the gold SQL are easy to find in the question. But the test side has no gold SQL and is masked by the model, which also replaces column mentions by `<COLUMN>`; a pool masked by a different procedure would compare skeletons that differ in style, which is what masking is meant to remove. We also tried a cheaper call that asks only for literals and skeleton with the same instructions: on 12 pilot questions its skeletons masked fewer column mentions (`total enrollment` left in, `updated 10 years` unmasked) and twice ended in stray characters, so the pool uses the full analysis call. Cost per pool question is about $0.000045 (flex, the 1,935-token instructions read from cache).

All retrieval embeddings use `text-embedding-3-small` with `dimensions=256` (`EMBEDDING_DIMENSIONS`). The OpenAI embeddings guide says the `dimensions` parameter shortens embeddings "without the embedding losing its concept-representing properties"; the committed cache stores each 256-d vector in 766 bytes instead of about 4.2 KB at 1,536 dimensions. CHESS's 0.6 cosine threshold for value re-ranking was set for full-length vectors; with 256 dimensions the value hit rate below is still 99%, so it was kept.

### Measurements on the BIRD dev split (350 questions)

`uv run --frozen python -m text2sql.retrieval measure` runs analysis, value matching and linking for every dev question, compares against the original Mini-Dev gold SQL (`gold_columns` from `text2sql.evals.metrics`, scored against the catalog schema), and writes per-question results and a summary to `data/indexes/measurements/`. Every gold query resolved. With the response cache in place the run replays offline for free. Confidence intervals are Wilson 95%.

| linking | full recall (gold columns all linked) | mean column recall | mean columns |
| --- | --- | --- | --- |
| returned by `link_schema` | 94.0% (329/350, 91.0-96.1) | 98.1% | 13.7 |
| without the top-5 shortlist columns | 89.1% (312/350) | 96.7% | 9.4 |
| pass 1 only (catalog order), with shortlist columns | 90.3% (316/350) | 97.1% | 13.6 |
| pass 2 only (reversed order), with shortlist columns | 92.9% (325/350) | 97.8% | 13.6 |
| no LLM pass: shortlist columns and values only | 49.4% (173/350) | 82.7% | 12.4 |

The variants are recomputed from the stored passes; tables a pass selected without columns are not stored, so they are slight underestimates. Table recall of the returned linking is 96.0% (336/350). Full recall by difficulty: simple 94.2% (98/104), moderate 95.4% (167/175), challenging 90.1% (64/71). The full schemas average 77.1 columns and about 2,742 tokens as rendered for prompts (four characters per token); the linked schemas average 13.7 columns and about 501 tokens, 18% of the full size. In 14 of the 21 misses a whole table is missing, six of them in formula_1 (`driverStandings` three times, `lapTimes`, `constructorStandings`, `races`); the rest are single columns such as `disp.type` or `results.time`.

Value retrieval: the gold SQL compares a column with 400 string literals (`=`, `<>`, `IN`, or `LIKE` without wildcards); 346 of them are values of an indexed column. Value retrieval returned 343 of those 346 for the right column (99.1%, 97.5-99.7). The other 54 are in columns the filters skip (mostly numeric or date text) or are spellings the database does not contain.

Cost (spend ledger, phase `retrieval`): $0.291 in total. The BIRD pool cost $0.226 (6,600 luna calls, 12.7M of 13.1M input tokens read from the prompt cache, 573K output tokens, plus $0.0025 of embeddings) and took 12 minutes at 64 concurrent requests, with no question skipped. The SaaS pool cost $0.0017. The dev measurement cost $0.061 over its runs (1,050 luna calls, about 9,600 embeddings); flex-tier rate limiting (HTTP 429, retried after 300 s) made it take about 75 minutes of wall time. The rest was pilots and column embeddings.

### Commands

`uv run --frozen python -m text2sql.retrieval build --dataset bird` (all 11 Mini-Dev databases and the bird pool; `--db <id>` limits the databases, `--skip-fewshot` skips the pool) and `... build --dataset saas`. The typer app is `text2sql.retrieval.cli:app` for mounting as `text2sql index`. Value indexes need no API; column embeddings and pool masking go through `LLMClient` and replay from the response cache in offline mode.

## Consequences

- `data/indexes/` must be built before any run with value retrieval, linking or few-shots; the loaders raise `FileNotFoundError` naming the build command. Offline rebuilds work only if the committed cache holds the column embeddings and pool analyses.
- Retrieval adds to the committed response cache: 7,775 responses with 11.4 MB of compressed payload (mostly the 6,641 pool analyses; the API echoes request settings and the JSON schema in every payload) and 11,950 256-d embeddings with 6.1 MB of vector data, about 17.5 MB before SQLite overhead. That is above the 15 MB target. The responses are the larger part and cannot shrink without dropping the pool or changing what the cache stores, both outside this module.
- Linking uses `DEFAULT_LINKING_EFFORT = "none"` and analysis `DEFAULT_ANALYSIS_EFFORT = "none"`; the pipeline should use the same so that recall matches these numbers and test skeletons match the pool's.
- The SaaS value index cannot help with tenant-specific spellings (a customer name written in lowercase, say). That is the price of one shared index; the generator still sees the column and can use case-insensitive comparisons.
- Thresholds (0.3, 0.6, 0.9, top 10, top 5 per query, 5 shortlist columns, 50 distinct values for vocabulary) are CHESS's or set on the dev split; the test split was not used.

## Sources

- docs/adr/008-pipeline-design.md and docs/research/prompts-from-papers.md (this repository): CHESS `template_extract_keywords.txt`, `db_values/preprocess.py`, `search.py`, `retrieve_entity.py`, `run_preprocess.sh`; Agentar-Scale-SQL task-understanding prompt; MCS-SQL shuffled linking; DAIL-SQL masking.
- OpenAI embeddings guide, `dimensions` parameter and normalization: https://developers.openai.com/api/docs/guides/embeddings.md (accessed 2026-10-16).
- datasketch 2.0.0 as installed: `MinHash.bulk`, `MinHashLSH`, `datasketch.lsh._optimal_param(0.01, 100, 0.5, 0.5) == (100, 1)` (checked in `tests/retrieval/test_lsh.py`).
- Measurements: `data/indexes/measurements/dev_summary.json` and `dev_questions.jsonl`; spend: `runs/spend_ledger.jsonl`, phase `retrieval`.
