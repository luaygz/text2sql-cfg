# ADR-008: Pipeline design from the literature

Status: Accepted
Date: 2026-10-16

## Context

The pipeline reimplements the ideas of the top BIRD systems (CHESS, CHASE-SQL, MCS-SQL, XiYan-SQL, OpenSearch-SQL, Agentar-Scale-SQL, with repair from DIN-SQL and MAC-SQL) as OpenAI API calls, and the iteration rounds add those components one at a time in order of expected value. This ADR records, per stage, what the source system actually does, how we rebuild it with the Responses API, and what gain the papers report, so that `retrieval/`, `generation/`, `selection/` and `pipeline.py` can be written without rereading the papers.

The mechanisms and the original prompt templates, with their provenance, are in `docs/research/prompts-from-papers.md`. Citations are in `docs/references.md`; bracketed numbers below refer to it. Numeric claims we intend to put in the README are checked in `docs/research/claims.md`.

Four facts shape every decision below.

1. Every reported gain comes from 2023–2025 models (GPT-4, GPT-4o, Gemini 1.5 Pro, Claude 3.5) that reasoned in visible text. Our generator is a reasoning model (`gpt-6.1-sol`) that reasons in hidden reasoning items before the tool call. Prompt techniques that existed to make a model think (chain-of-thought templates, long worked demos) should matter less. OpenAI's reasoning guide says to try zero-shot first and that examples which do not match the instructions "may produce poor results" [30]. Expect the deltas to shrink and measure each one.
2. SQL only ever comes out of the forced `sql_query` grammar tool (constraint 2, ADR-001). Every paper prompt that asks for SQL in a code block, a JSON field or `<FINAL_ANSWER>` tags is adapted: we keep the method text, drop the output-format text, and the tool call carries the SQL. Calls that produce something other than SQL (keywords, linked columns, a judge's choice, unit tests) use JSON structured output through `LLMClient.structured`.
3. The API rejects grammars above roughly 250 distinct lexemes (ADR-001). Several BIRD databases have more columns than that, so their full-schema grammar does not fit and schema linking is partly forced on us, whatever Maamari et al. [15] found about prompts.
4. `temperature` is not accepted when reasoning effort is above `none` (ADR-001). Diversity has to come from the strategy, the schema view, the few-shot set, the model and the effort setting.

## Decision

### Model tiers and call types

| Stage | Calls per question | Model (config field) | Output |
| --- | --- | --- | --- |
| Question analysis: literals, keywords, skeleton, requested outputs, complexity class | 1 | `small_model` (gpt-6-luna) | structured |
| Value retrieval | 0 LLM calls; embeddings for LSH candidates | `embedding_model` | — |
| Schema linking (LLM pass) | 1–3 | `small_model` | structured |
| Few-shot retrieval | 0 LLM calls; one embedding | `embedding_model` | — |
| Candidate strategies | N (default 5) | `generator_model` (gpt-6.1-sol), one strategy on `small_model` | grammar tool |
| Repair | at most 2 per failing candidate | same model as the candidate, continuing its conversation | grammar tool |
| Pairwise judge | at most m(m−1) for m distinct result clusters, skipped when one cluster | `generator_model`, low effort | structured |
| Unit-test generation / evaluation | 1 + k | `generator_model` / `small_model` | structured |
| Answer explanation | 1 | `small_model` | structured |

Prompt layout follows the caching rules in ADR-001 and ADR-006. Tools render first and are part of the cached prefix. Next comes a developer message whose first block holds what every strategy shares for a database (task description, BIRD conventions in benchmark mode, the rendered schema), with the cache breakpoint at its end; the strategy's method text follows the breakpoint, and the user message carries everything question-specific (evidence, matched values, few-shots, question). Strategies that use the same grammar therefore share one cached prefix. Two consequences follow. A per-question linked-schema grammar changes the tool definition, so strategies that use it get no cache hit on the schema block; the full-schema grammar is stable per database and does. And shuffling table order for diversity, as CHASE-SQL and MCS-SQL do, would break caching too, so we do not shuffle in generation (MCS-SQL itself only shuffles in schema linking).

### Stage 1: schema catalog and schema rendering

Sources. XiYan-SQL's M-Schema [16, 17] renders each table as a list of `(column:TYPE, description, Primary Key, Examples: [v1, v2, v3])` tuples plus a foreign-key list. With full schema and a single generation on BIRD dev it beat DDL by 2.03 points on average across four models (GPT-4o: 57.95 vs 55.67) and beat MAC-SQL's format by 0.65 on GPT-4o; the XiYanSQL-QwenCoder README reports GPT-4.1 at 59.39 with M-Schema against 54.11 with DDL. MCS-SQL [13] adds sample rows as CSV (+2.4 on BIRD dev with GPT-4). CHESS shows retrieved example values inline in the schema.

Ours. `render_schema` (`text2sql.catalog`, ADR-010) should produce an M-Schema-like block: type, primary key, the BIRD `database_description` text, up to three example values (XiYan drops examples longer than 50 characters and keeps one for dates), and foreign keys. Matched values from Stage 2 are added per column in the user message, not in the cached block. This stage is a formatting decision, not an ablation row, but the README can cite the M-Schema numbers when explaining it.

### Stage 2: question analysis and value retrieval

Sources. CHESS [12] extracts keywords with one few-shot LLM call, then for each keyword and each prefix and suffix around its spaces queries a MinHash LSH index over distinct values of text columns (character 3-grams, 100 permutations, threshold 0.01, top 10), keeps candidates with `difflib` ratio ≥ 0.3 and embedding similarity ≥ 0.6 (`text-embedding-3-small`), then keeps values within 0.9 of the best per column. It skips primary keys and columns whose names look like ids, URLs, emails, dates, phones or addresses. CHASE-SQL [14] uses the same approach and loses 2.92 points on BIRD dev without it (73.01 → 70.09). CHESS loses 4.76 on its dev subsample without entity and column-description retrieval. OpenSearch-SQL [18] loses 1.4 points on Mini-Dev without value retrieval. Agentar-Scale-SQL [19] does keyword work and few-shot skeleton extraction in one "task understanding" call.

Ours. One `small_model` structured call returns: database literals (Agentar), keywords and key phrases (CHESS), a question skeleton with literals replaced by their column or type and columns by `<COLUMN>` (Agentar, used in Stage 4), the requested outputs in question order (OpenSearch's SELECT alignment, used in the generation prompt), and a complexity class `easy | non_nested | nested` (DIN-SQL's classifier [9], used by cheap-path routing). Matching runs locally in three passes: case-insensitive exact match against catalog distinct values; the datasketch MinHash LSH with CHESS's parameters and column filters; embedding re-ranking of only the LSH candidates (embedded on demand and cached, so we never embed whole columns). Output is `{table.column: [values]}`. Columns with a match are force-included by schema linking, as CHESS does. The adapted keyword prompt starts from CHESS `template_extract_keywords.txt` and Agentar's task-understanding prompt (prompts-from-papers, Part 1 §1 and Part 3 §4.3).

### Stage 3: schema linking

Sources. MCS-SQL [13] links tables, then columns, with three prompts whose table and column order is shuffled and 20 samples each, and takes the union: recall of gold schema items on BIRD dev rose from 61.3% (one greedy call) to 77.1% (sampling) to 89.8% (three shuffled prompts); linking added 2.1 EX. XiYan-SQL [17] scores columns by embedding similarity to keywords, then lets an LLM select columns in two rounds, removing already-selected non-key columns from the pool each round and re-adding primary and foreign keys; it reports +1.4 to +2.2 EX averaged over three generators. CHESS [12] reduces columns to about ten with 94% column recall, but its v3 notes that with small schemas and strong models the selector can hurt, and its best BIRD configuration drops it. Maamari et al. [15] measured 4.8 to 11.6 points lost to schema linking with ft:GPT-4o and recommend the full schema whenever it fits.

Ours. Two passes. The embedding pass retrieves the top columns per keyword from column documents (name, BIRD description, value description) embedded once per database, querying with question-plus-keyword and evidence-plus-keyword as CHESS does. The LLM pass (`small_model`, structured `{tables, columns}`) chooses from that shortlist plus every column of every table that the shortlist touches, with a recall-first instruction ("an extra column is cheap, a missing one is fatal"). We run it twice with two fixed table orders and take the union (a cheap version of MCS's shuffling that keeps the two prompt prefixes cacheable), then add value-matched columns, every primary key of a selected table, and the foreign-key columns that connect selected tables. Linking recall against gold SQL columns is logged per question. The full-schema strategy stays, both for diversity and because the literature says a strong model may prefer it; when the full-schema grammar does not fit (ADR-001, ADR-005), that strategy keeps the full schema in the prompt and uses the widest grammar that fits, built from the union of all linking passes.

### Stage 4: few-shot retrieval

Sources. DAIL-SQL [10] masks table and column names in the question as `<mask>` and values as `<unk>`, embeds the masked question, ranks training examples by distance, then prefers those whose SQL skeleton matches a preliminary prediction (Jaccard ≥ 0.85 in the released code), and shows only question–SQL pairs without their schemas. On Spider with GPT-4, five DAIL-selected examples raise EX from 72.3 to 82.4. On BIRD dev MCS-SQL measured random 57.0, question similarity 59.3 and masked-question similarity 60.0, and few-shots were its largest single gain (+4.8). OpenSearch-SQL loses 4.6 on Mini-Dev without few-shots. For CHASE-SQL, training-set examples added only about one point with Gemini 1.5 Pro (5 examples: 58.80 vs 57.75 zero-shot), so it generated examples per database instead. OpenAI's guidance [30, 31] is to start without examples for reasoning models.

Ours. Embed the Stage 2 skeleton and retrieve the k nearest training questions by cosine similarity over precomputed skeletons of the training pool (k = 3 to start, swept later). For BIRD, the pool is the train split, preferably the BIRD team's `bird23-train-filtered` subset (6,601 of 9,428 examples kept after quality filtering, per the leaderboard news of 19 Sep 2025), since our Mini-Dev labels are already noisy enough. The skeletons are produced by the same Stage 2 prompt so test and pool are masked the same way. DAIL's skeleton filter needs a preliminary SQL; we add it later using the cheap-path candidate if few-shots earn their place. Examples go in the user message as question, evidence and SQL. Few-shots are on only for the "direct, linked schema" strategy at first and are ablated as a switch.

### Stage 5: grammars

The grammar builder is described in ADR-005. This pipeline asks for two grammars per request, linked and full (or widest-that-fits), both built with `build_grammar(schema, GrammarOptions(mode=...))`, and passes each strategy the one matching its schema view.

### Stage 6: candidate strategies

All strategies are one `LLMClient.sql_call` with the forced grammar tool. Instructions are adapted from the sources below with the output-format text removed.

Divide and conquer (CHASE-SQL [14]). The paper's generator decomposes the question into sub-questions written as pseudo-SQL, solves them bottom-up, assembles, then simplifies. On BIRD dev with Gemini 1.5 Pro a single candidate scored 63.92 against a 57.75 baseline; removing this generator from the full system cost 1.24, and it was the generator that most often uniquely solved challenging questions. The paper only shows one worked demo; the full instruction template, with 13 "database admin instructions", lives in the CHESS repository (prompts-from-papers, Part 2 §1a). We put the method description in the developer message and tell the model to work through it before calling `sql_query`; the worked demo is an optional switch.

Query plan (CHASE-SQL). Reason in execution order: locate tables, scan and filter, join, aggregate, return columns. Single candidate 63.62 (+5.87); removing it cost 0.65; strongest on moderate questions. Same adaptation as above (Part 2 §1b).

Direct generation, full schema, no few-shots. The Maamari-style baseline and the baseline configuration for the iteration rounds.

Direct generation, linked schema, with retrieved few-shots. The MCS-SQL / DAIL-SQL style generator.

Small model on the linked schema. The cheap extra sample that Agentar-Scale-SQL and XiYan-SQL get from mixing models; also the first candidate of the cheap path.

All generation prompts include a short block of BIRD annotation conventions in benchmark mode only, because every strong system carries one: CHASE/CHESS's 13 admin instructions, Agentar's 14 (adds NULL filtering for ascending sorts and MIN, and formatting rules), OpenSearch's style alignment. The common rules are: select only the columns asked for, in the order asked; join before MIN/MAX; prefer `ORDER BY … LIMIT 1` over nested MAX subqueries; filter NULLs on sorted or minimised columns; no string concatenation in SELECT; `STRFTIME` for dates; follow the evidence. These encode BIRD's gold-label style, so the README should say so; the SaaS prompts do not get them.

Candidate counts in the literature: CHASE-SQL generates 21 and saw no gain beyond 20; Agentar uses 17 and its pass@k gains flatten after 8; XiYan uses 5 to 10; OpenSearch-SQL with GPT-4o kept improving up to 21. CHASE-SQL's 21 candidates had an oracle ceiling of 82.79 against 68.84 for self-consistency and 73.01 with its trained selector. The N-sweep of 1, 3, 5, 8 covers the range where the curves are steepest. For N > 5 the extra samples are second runs of divide-and-conquer and query-plan with a different few-shot set or effort setting.

Considered and deferred: CHASE-SQL's online synthetic examples, its best single generator (+9.34 with Gemini 1.5 Pro, but only +1.44 with Mistral Large). Generating examples means the model writes SQL, which constraint 2 requires to come through the grammar tool, so it costs one grammar call per example. The full-database part of it is question-independent and could be built once per database offline; it is the first thing to try if few-shots from the train split help.

### Stage 7: execution and repair

Sources. CHASE-SQL [14] re-prompts a failing candidate with the schema, question, evidence, the failed query and its execution result, up to three times, on an error or an empty result, and drops candidates that still fail; this added 1.85–3.83 per single generator and removing it cost 3.78 on the full system. CHESS [12] lost 6.80 without revision. MAC-SQL's refiner [11] (−4.63 when removed) also triggers on NULLs in the first rows. DIN-SQL [9] found that a "generic" prompt telling GPT-4 its SQL was buggy lowered Spider accuracy by 3.3 points, while a "gentle" prompt that asks it to check for issues raised it by 0.9. The newer systems report much smaller gains: XiYan 0.55, Agentar 0.52, OpenSearch 0.8.

Ours. Run every candidate through the validator (`validate_sql`) and `SandboxedExecutor`. Repair when execution errors, the validator rejects, or the result is empty while the question analysis does not mark the question as possibly empty. The repair is a continuation of the candidate's own conversation: its previous items (including reasoning) plus `tool_output_item(call_id, feedback)`, then a new forced `sql_call`. The feedback is the SQLite error or validator rule, or "0 rows", plus value hints in the spirit of CHESS's revision and OpenSearch's agent alignment: for each string literal the query compares to a column, whether that value exists there, and the closest retrieved values if not. Wording follows DIN-SQL's lesson: state the observed problem and ask the model to check the query against the question, never assert it is wrong when there is no error signal. At most two repairs per candidate (CHASE and MAC-SQL use three). A candidate that still fails is kept for the logs but excluded from selection.

OpenSearch-SQL's consistency alignment [18] maps onto this stage and Stage 2 rather than becoming its own pass: SELECT alignment is the requested-outputs list in the generation prompt (removing it cost 2.0 on Mini-Dev), value alignment is the literal check above, and style alignment is the conventions block. OpenSearch applies some of these as regex rewrites of the SQL; we do not rewrite model SQL for accuracy, because any change has to come back through the grammar tool.

### Stage 8: selection

Clustering. Group candidates by normalised execution result (multiset of rows; ordered comparison only when the query has a top-level ORDER BY). Error and failed candidates are excluded. Every top system does this first: MCS-SQL's confidence is the share of candidates in a cluster, XiYan and Agentar keep one representative per cluster, CHESS clusters before writing unit tests.

Majority vote. The largest non-empty cluster wins. Ties break by measured strategy accuracy on the dev split (XiYan orders by generator performance), then by the shortest SQL. Expected value: CHASE-SQL went from 63.01 (single query) to 68.84 with self-consistency over 21 candidates; OpenSearch-SQL gained 2.4 on Mini-Dev, mostly on challenging questions.

LLM judge. CHASE-SQL's selector compares two candidates at a time, in both orders, on the union of the schema elements the two queries use, and the candidate with the most pairwise wins is chosen; candidates with the same result count as agreeing without a call. Comparing in only one order cost about 2 points. Its fine-tuned Gemini Flash selector gained 4.17 over self-consistency. The same paper is also the warning: off-the-shelf Gemini 1.5 Pro and Claude 3.5 were 64% and 60% accurate at picking the right one of two, and a listwise ranker over all candidates scored 65.51, below self-consistency. XiYan's prompted GPT-4o selector scored 67.47 against 69.56 for its fine-tuned 7B model, and XiYan's candidate reorganisation (one shortest query per cluster, clusters in size order, ties by generator accuracy) beat a random presentation order by 2.6 to 5.2 points. MCS-SQL's listwise multiple choice beat majority vote by only 0.6 and only after dropping clusters with under 20% support. Agentar runs a round-robin tournament among cluster representatives with an RL-trained selector.

Ours. A pairwise round-robin among cluster representatives (CHASE Algorithm 3, Agentar's tournament): for each unordered pair, two `generator_model` calls at low effort with the order swapped, each returning structured `{winner: "A" | "B"}`. The prompt shows question, evidence, the union of schema elements used by the pair, both SQL strings and the first rows of each result (XiYan shows 10, CHESS 20), and is adapted from CHASE's selection prompt (Part 2 §1e). Score is pairwise wins; ties go to the larger cluster. Skip the judge when there is one cluster, and gate it on vote share: only call it when the top cluster holds less than a threshold of the votes, tuned on dev. Because both orders are always asked, presentation-order bias cancels, so the order does not need to be randomized. A listwise variant in cluster-size order is the ablation against it. Expect a small gain or none: the large gains in the papers came from fine-tuned selectors, and fine-tuning is out of scope (README roadmap).

Unit tests. This is CHESS v3's Unit Tester [12], not an idea from a separate paper; it exists only in arXiv v3 (Nov 2024) and in the repository code from 2024-11-13. One call sees the question, schema and the candidate clusters with their results, and writes natural-language tests designed to separate the clusters ("The answer SQL query should …"); the code always adds a fixed test that only the best answer should pass. Each test is then evaluated in its own call against all candidates, which beat evaluating all tests per candidate (68.31 vs 66.78 on BIRD dev). The score is tests passed, with ties to the largest cluster; the step is skipped when there is one cluster. CHESS reports accuracy peaking at 10 tests; it gives no ablation of unit tests against plain voting, so the expected value is unknown. Ours: generation on `generator_model`, evaluation on `small_model`, both structured; start with three tests plus CHESS's fixed one, and sweep 3, 5 and 10 if it helps. Prompts adapted from CHESS `template_generate_unit_tests.txt` and `template_evaluate.txt` (Part 1 §4).

All three selectors are reported against oracle pass@N.

### Stage 9: answer and cheap path

The confidence flag is the winning cluster's vote share. Abstention and clarification are not in any of these papers (BIRD never tests them); they come from the SaaS eval and `GrammarOptions.allow_abstain`.

Cheap path. Generate the small-model linked candidate first, then one direct full-schema candidate; if both execute cleanly with the same result and the question analysis classes the question as `easy`, return it. DIN-SQL's three-way classification is the precedent for routing by question type, and XiYan-SQL reports that about 45% of BIRD dev questions get unanimous candidates, which bounds how often a cheap path can end early. Report both paths' cost and accuracy.

### Order of addition

Starting from the baseline (one candidate, full schema, grammar on, no retrieval, no repair), add one component per round, keep it only if McNemar's test on dev says it helps or it cuts cost at equal accuracy:

1. Value retrieval: the most consistent gain across systems (CHASE −2.92 when removed, CHESS −4.76 with column-description retrieval, OpenSearch −1.4).
2. Schema linking: mixed evidence (+1.4 to +2.2 in XiYan and MCS-SQL, negative for strong models in Maamari et al.). On small Mini-Dev schemas it may lose accuracy; it stays as a strategy input and a grammar-size necessity even if it does not win as a filter.
3. Execution and repair: large with older models (3.8 to 6.8), under one point in 2025 systems.
4. Multiple candidates with majority vote: +5.8 in CHASE-SQL, +2.4 in OpenSearch-SQL; the oracle ceiling (pass@N) is the number to watch.
5. Judge selection: gains in the literature come from fine-tuned selectors; prompted selectors were at or below voting.
6. Few-shots: +4.6 to +4.8 for GPT-4-era systems; OpenAI's guidance predicts less for reasoning models.
7. Unit-test selection: no isolated ablation published.
8. Cheap-path routing: a cost change, judged at equal accuracy.

Every expected delta above is from older models and different data, and is a prior for which rounds to run first, not a prediction.

## Consequences

- The pipeline has seven LLM-backed components and only the strategies and repair emit SQL, all through the grammar tool; everything else is structured output, so constraint 2 holds by construction.
- Linked-schema strategies pay full input price for the schema block on every call because their grammar (part of the cached prefix) changes per question. If cost per question is too high, the first lever is to give more strategies the per-database full or widest grammar.
- Not shuffling schema order in generation gives up one of CHASE-SQL's diversity sources in exchange for caching. If pass@N stays close to single-candidate EX, revisit this.
- We cannot reproduce the fine-tuned parts of CHASE-SQL, XiYan-SQL, Agentar-Scale-SQL or ReViSQL; the README should say that selection is where the gap to those systems is expected, and the roadmap item "fine-tuned selector via the OpenAI fine-tuning API" follows from it.
- The BIRD conventions block is a benchmark-specific prompt; it must be off in production and tenant modes and called out in the README.
- Three choices are fixed here: the repair cap is two (the sources use three); the unit-test count starts at three (CHESS peaks at ten); the judge uses both orders rather than one random order.
- Interfaces needed from other components: `LLMClient.sql_call` with `history` and `tool_output_item` for repair turns, `LLMClient.structured` and `LLMClient.embed`; `build_grammar` for linked and full schemas with a fit check; `render_schema` in an M-Schema-like format; `SandboxedExecutor` results with row lists for clustering.

## Sources

All read on 2026-10-16. Full bibliographic entries in docs/references.md.

- CHESS: https://arxiv.org/abs/2405.16755 (v1, v2, v3 HTML), https://github.com/ShayanTalaei/CHESS (templates, run configs, `src/database_utils/db_values/*`, `src/workflow/agents/*`)
- CHASE-SQL: https://arxiv.org/abs/2410.01943, ICLR camera-ready https://proceedings.iclr.cc/paper_files/paper/2025/file/974ff7b5bf08dbf9400b5d599a39c77f-Paper-Conference.pdf
- MCS-SQL: https://arxiv.org/abs/2405.07467, https://aclanthology.org/2025.coling-main.24.pdf
- DIN-SQL: https://arxiv.org/html/2304.11015v3, https://github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting
- MAC-SQL: https://arxiv.org/html/2312.11242v6, https://github.com/wbbeyourself/MAC-SQL (`core/const.py`, `core/agents.py`, `core/chat_manager.py`)
- DAIL-SQL: https://arxiv.org/html/2308.15363, https://github.com/BeachWang/DAIL-SQL
- XiYan-SQL: https://arxiv.org/html/2411.08599v3, https://arxiv.org/html/2507.04701, https://github.com/XGenerationLab/M-Schema, https://github.com/XGenerationLab/XiYanSQL-QwenCoder
- OpenSearch-SQL: https://arxiv.org/html/2502.14913, https://github.com/OpenSearch-AI/OpenSearch-SQL
- Agentar-Scale-SQL: https://arxiv.org/html/2509.24403 (v6), https://github.com/antgroup/Agentar-Scale-SQL
- The Death of Schema Linking?: https://arxiv.org/html/2408.07702
- BIRD leaderboard and news (bird23-train-filtered, bird-sql-dev-1106): https://bird-bench.github.io/
- OpenAI reasoning best practices: https://developers.openai.com/api/docs/guides/reasoning-best-practices.md
- OpenAI prompting guidance for GPT-5.6 Sol: https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6.md
- OpenAI reasoning models guide: https://developers.openai.com/api/docs/guides/reasoning.md
- ADR-001 (this repository) for the grammar size limit, caching rules and the temperature restriction.
