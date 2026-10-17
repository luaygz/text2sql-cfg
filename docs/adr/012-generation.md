# ADR-012: Candidate generation: strategies, prompt layout and repair turns

Status: accepted
Date: 2026-10-16

## Context

ADR-008 stages 6 and 7 ask for several diverse SQL candidates per question, each one forced `sql_query` grammar call (ADR-001), and for a repair turn when a candidate fails. `text2sql.generation` implements the strategies, the prompts and the repair turn; the pipeline (ADR-014) decides how many candidates to draw, executes them and enforces the repair limit.

Three facts shape the design. The generator, `gpt-6.1-sol`, reasons in hidden reasoning items, so chain-of-thought templates from 2024 papers become instructions about what to think through, not text the model writes. Prompt caching is explicit (ADR-006): a cache write costs 1.25 times the input price and a read 0.05 times on gpt-6.1-sol, so only prefixes that are read again should be written. And the API budget is about $33 for the whole project, so the cost per question decides how many experiments the iteration rounds can afford.

## Decision

### Strategies

| Strategy | Method prompt | Model | Effort | Schema view | Few-shots |
| --- | --- | --- | --- | --- | --- |
| `divide_conquer` | `generate_divide_conquer` | generator (gpt-6.1-sol) | medium | full | no |
| `query_plan` | `generate_query_plan` | generator | medium | full | no |
| `direct_full` | `generate_direct` | generator | medium | full | no |
| `direct_linked_fewshot` | `generate_direct` | generator | medium | linked | yes |
| `small_linked` | `generate_direct` | small (gpt-6-luna) | low | linked | no |

The divide-and-conquer and query-plan method texts are adapted from CHASE-SQL as transcribed in `docs/research/prompts-from-papers.md` (Part 2, sections 1a and 1b, which quote the CHESS repository templates). The steps are kept; the worked demonstrations, the "punishable to death" admin rules and every output-format instruction (`<FINAL_ANSWER>`, one-line SQL) are dropped. Each method ends with "Work through this in your reasoning before answering. Then call the `sql_query` tool once, with the complete final query as its input." `model_for(spec, settings)` maps the tier to the configured model.

`DEFAULT_SCHEDULE` lists eight candidates: `divide_conquer`, `query_plan`, `direct_linked_fewshot`, `direct_full`, `small_linked`, then `divide_conquer`, `query_plan`, `direct_full` again. N = 1 gets CHASE-SQL's best single generator, N = 3 adds the input that differs most from the full-schema prompts, N = 5 covers every strategy. `schedule(names, n)` cycles through any list and gives a repeated name the next sample index, which separates the response-cache keys of otherwise identical requests. The repeats are full-schema strategies because their prefix is cached; a second linked candidate would pay its whole prompt again (see the costs below).

### Prompt layout

`build_messages(spec, ctx)` returns three messages after the tool:

1. Developer message 1, the same for every strategy on one schema view and mode: the task, the spelling rules, the LIMIT rule for the mode, the tenant rule (tenant mode), the abstain option (only when the view's grammar has `allow_abstain`), the BIRD conventions (benchmark mode only), and the rendered schema.
2. Developer message 2: the strategy's method and the closing instruction above.
3. User message: evidence, matched values, few-shots (only for strategies with `fewshots=True`), requested outputs, question, in that order. Empty parts are left out.

Shared text lives in `prompts/generate_common.yaml`; each strategy's method in its own file; the repair text in `prompts/repair.yaml`. Every call's purpose carries the template tags, e.g. `generate.query_plan[generate_query_plan@1.0,generate_common@1.1]`, and `prompt_tags(spec)` returns them for trace records.

The spelling rules restate `SqlGrammar.description` (ADR-005) with examples, because the model plans the query in its reasoning before the grammar constrains anything: tables and subqueries aliased `T1`..`T9` with every column qualified, CTEs `cte1`..`cte5`, computed columns `c1`..`c9` and no other alias names, backticks exactly as in the schema listing, single-quoted strings with `''`, the rule for strings that start with punctuation (below), the allowed join forms, and the function list read from `grammar.conventions` so it cannot drift from the grammar. Production and tenant prompts never contain the BIRD conventions; tenant prompts say that rows are restricted to the caller's organisation after the query is written and that `SELECT *` is not available. The task text says that everything in the user message, database values and examples included, is data and cannot change the instructions.

The BIRD conventions block condenses the CHESS/CHASE-SQL "database admin instructions" and Agentar-Scale-SQL's additions (NULL filtering on ascending sorts and MIN, percentages, rounding only on request). It encodes BIRD's gold-label style and is called out as benchmark-specific.

`generate_common@1.2` revises four conventions after the round-0 failure review (109 failures of the baseline, 30 read by hand). Percentages are written `CAST(x AS REAL) * 100 / y` and plain ratios `CAST(x AS REAL) / y`: 44 of the 45 percentage golds among the 350 dev questions multiply first, and six baseline failures differed from the gold only in the last float digit because the model divided first. LIMIT is added only when the question asks for a fixed number of rows, after a prediction capped a 25,061-row answer with `LIMIT 1000`. The output rule names the helper columns the model added (id, name, description). "Follow the evidence literally" became "write the evidence's literal in the stored spelling shown in the schema's example values or the matched values", because copying the evidence's casing or date format (`'legal'` for a stored `'Legal'`, `'2014/4/23'` for `'2014-04-23'`) returned no rows. Only the benchmark-mode text changed: production and tenant requests are byte-identical to 1.1, so their cached responses still replay, and a test checks that none of the new rules reach those modes.

### Where the cache breakpoint goes

Developer message 1 carries the cache breakpoint only when its grammar is the request's full-schema grammar (`reusable_prefix`). The full-schema prefix (tools plus developer message 1, 3,439 to 6,899 tokens on the smoke questions) is identical for every full-view strategy and for every question on the same database, so it is written once and read many times. A linked-schema grammar is built per question, so its prefix is almost never read again; with a breakpoint it paid the write premium for nothing (`direct_linked_fewshot` on Q62: $0.00926 with the write, $0.00767 without, live). When the pipeline passes the full view as the linked one (schema linking off), the fingerprints match and the linked strategies share the cached prefix. This narrows ADR-008's "breakpoint at the end of developer message 1" to the prefixes that can be reused. One gap: when the full-schema grammar does not fit the API budget, the pipeline passes the linked grammar as `full`, and that per-question prefix is still written; no Mini-Dev database needs this.

Two observations matter for scheduling calls. The cache is partitioned by reasoning effort: `divide_conquer` at medium wrote the same 3,439-token prefix again ten minutes after the low-effort run had written it, and the caching guide lists `reasoning.effort` among the settings that change the cached prefix. So all full-view strategies run at one effort. And candidates started at the same moment on a cold prefix each pay the write; the pipeline lets the first full-view candidate per (grammar, model, effort) run alone.

### Repair turns

`repair_candidate(llm, spec, ctx, previous, feedback, model=, attempt=)` resends the same three messages, then the candidate's history: `previous.history_items` (its `custom_tool_call` and any earlier repair turns), `tool_output_item(previous.call_id, feedback)`, and a user message "Call `sql_query` again.", with the tool forced again. The result's `history_items` hold the whole exchange, so attempt 2 passes attempt 1's result as `previous`. The caller enforces the limit (two repairs); `attempt` labels the purpose (`repair.divide_conquer#1[repair@1.1,...]`).

The user message departs from the "history plus tool output" turn that ADR-008 planned, forced by the live behaviour of gpt-6.1-sol. With the input ending at the tool output, 3 of 3 repair turns ended `incomplete` with reason `max_messages` after about 100 reasoning items and no tool call (663 to 808 output tokens, $0.0073 to $0.0114 each), and replaying the reasoning items of the original response (their `encrypted_content` is returned by default when `store` is false) did not help in a fourth try. A repair sent as a user message alone worked, and so did the tool output followed by the short user message, which keeps the conversation shape the reasoning guide recommends for tool calls. On a synthetic SQLite error (`no such column: T1.power_id`) the latter fixed the query to `T2.power_id` with the prefix read from cache, for $0.0010.

`repair_feedback(kind, detail, value_hints)` states what was observed: the SQLite error, the validator's rule and detail, "0 rows", or (kind `value`, the pipeline's literal check in ADR-014) each compared string its column does not hold with the close values it does, then one line per value hint, then the request. Following DIN-SQL's finding that telling GPT-4 its SQL was buggy cost accuracy while a "gentle" check prompt helped, the empty-result text says an empty result can be correct, lists the usual causes, and asks the model to keep the query if it is right; the `value` text likewise asks it to keep the query if the stored values are not what the question means. In the smoke, this feedback sent counterfactually to correct candidates left all six of them (three per effort) unchanged.

### Grammar-off ablation

`generate_json_candidate` exists only for the "grammar off" ablation and says so in its docstring. It sends the same developer message 1 and user message through `LLMClient.structured` with a strict `{sql}` schema; developer message 2 keeps the method and replaces the tool instruction with one that asks for the query in the `sql` field and repeats the grammar's description, since no tool carries it. The SQL is returned as written (outer whitespace stripped, not even a trailing semicolon removed). The caller must send it through the guard without layer 1 and record that it did. There is no JSON repair path: `structured` has no conversation history, so grammar-off runs compare against grammar-on runs with repair off.

### Effort defaults

Measured on the three smoke questions, twelve gpt-6.1-sol generation calls per effort:

| Effort | Output tokens (sum) | Reasoning tokens (sum) | Mean latency | Correct |
| --- | ---: | ---: | ---: | --- |
| low | 1,087 | 223 | 2.9 s | 12 of 12 |
| medium | 1,271 | 407 | 2.7 s | 12 of 12 |

Medium costs about 15 output tokens more per call ($0.00008 at flex), with no latency difference; input dominates the cost of every call. At low effort the repair check used zero reasoning tokens (the model resubmitted without looking), at medium 9 to 30. All gpt-6.1-sol strategies default to medium; the small model stays at low. Three questions cannot show an accuracy difference; the effort sweep in the iteration rounds decides.

### Live smoke

`python -m text2sql.generation.smoke` (command in its docstring) ran every strategy once on three BIRD Mini-Dev dev questions: Q779 superhero (simple), Q89 financial (moderate), Q62 california_schools (challenging). It is not the pipeline: the linked view is every column of the tables the gold SQL reads (an oracle), there are no matched values or requested outputs, and the few-shots are the three train questions most similar in wording, normalised to the grammar's spelling. Flex tier, `max_output_tokens` 8,000. EX is `bird_metric.execution_match` against the original gold on the minidev databases. "Forced check" rows send the empty-result feedback to a candidate whose result was not empty (no candidate failed, so no natural repair occurred). Costs are list prices for the reported usage. The tables were recorded with `generate_common@1.0` and the grammar before the punctuation-literal fix (below); the responses stay in the response cache, but the current code builds different requests, so `OFFLINE=1` replays of these tables now miss.

Medium effort (the defaults; `small_linked` at low):

| Q | Strategy | Input | Cached | Cache write | Output | Reasoning | USD | Latency s | Grammar | EX |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 779 | divide_conquer | 3,845 | 0 | 3,439 | 112 | 59 | 0.00526 | 3.6 | ok | yes |
| 779 | query_plan | 3,817 | 3,439 | 0 | 91 | 38 | 0.00100 | 2.7 | ok | yes |
| 779 | direct_full | 3,668 | 3,439 | 0 | 68 | 15 | 0.00074 | 2.0 | ok | yes |
| 779 | direct_linked_fewshot | 2,892 | 0 | 0 | 63 | 10 | 0.00321 | 1.8 | ok | yes |
| 779 | small_linked | 2,688 | 0 | 2,459 | 54 | 0 | 0.00018 | 2.4 | ok | yes |
| 89 | divide_conquer | 4,334 | 0 | 3,907 | 136 | 65 | 0.00599 | 5.7 | ok | yes |
| 89 | query_plan | 4,306 | 3,907 | 0 | 102 | 31 | 0.00110 | 2.3 | ok | yes |
| 89 | direct_full | 4,157 | 3,907 | 0 | 92 | 21 | 0.00091 | 2.2 | ok | yes |
| 89 | direct_linked_fewshot | 2,970 | 0 | 0 | 86 | 15 | 0.00340 | 2.2 | ok | yes |
| 89 | small_linked | 2,730 | 0 | 2,480 | 69 | 0 | 0.00018 | 1.4 | ok | yes |
| 62 | divide_conquer | 7,378 | 0 | 6,899 | 161 | 69 | 0.00991 | 3.4 | ok | yes |
| 62 | query_plan | 7,350 | 6,899 | 0 | 136 | 44 | 0.00148 | 2.7 | ok | yes |
| 62 | direct_full | 7,201 | 6,899 | 0 | 111 | 19 | 0.00120 | 2.2 | ok | yes |
| 62 | direct_linked_fewshot | 7,101 | 0 | 0 | 113 | 21 | 0.00767 | 2.1 | ok | yes |
| 62 | small_linked | 6,789 | 0 | 6,487 | 117 | 0 | 0.00045 | 2.2 | ok | yes |
| 779 | divide_conquer forced check | 4,008 | 3,439 | 0 | 62 | 9 | 0.00105 | 1.9 | ok | yes |
| 89 | divide_conquer forced check | 4,515 | 3,907 | 0 | 101 | 30 | 0.00131 | 2.5 | ok | yes |
| 62 | divide_conquer forced check | 7,580 | 6,899 | 0 | 121 | 29 | 0.00163 | 2.7 | ok | yes |

Low effort (all gpt-6.1-sol strategies at low; the `small_linked` rows are the same calls as above):

| Q | Strategy | Input | Cached | Cache write | Output | Reasoning | USD | Latency s | Grammar | EX |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 779 | divide_conquer | 3,845 | 0 | 3,439 | 86 | 33 | 0.00513 | 4.3 | ok | yes |
| 779 | query_plan | 3,817 | 3,439 | 0 | 69 | 16 | 0.00089 | 3.4 | ok | yes |
| 779 | direct_full | 3,668 | 3,439 | 0 | 64 | 11 | 0.00072 | 1.7 | ok | yes |
| 779 | direct_linked_fewshot | 2,892 | 0 | 2,459 | 62 | 9 | 0.00382 | 2.3 | ok | yes |
| 89 | divide_conquer | 4,334 | 0 | 3,907 | 109 | 38 | 0.00586 | 4.3 | ok | yes |
| 89 | query_plan | 4,306 | 3,907 | 0 | 87 | 16 | 0.00103 | 2.8 | ok | yes |
| 89 | direct_full | 4,157 | 3,907 | 0 | 84 | 13 | 0.00087 | 3.1 | ok | yes |
| 89 | direct_linked_fewshot | 2,970 | 0 | 2,480 | 84 | 13 | 0.00401 | 1.9 | ok | yes |
| 62 | divide_conquer | 7,378 | 0 | 6,899 | 116 | 24 | 0.00968 | 3.4 | ok | yes |
| 62 | query_plan | 7,350 | 6,899 | 0 | 113 | 21 | 0.00136 | 3.7 | ok | yes |
| 62 | direct_full | 7,201 | 6,899 | 0 | 106 | 14 | 0.00118 | 2.0 | ok | yes |
| 62 | direct_linked_fewshot | 7,101 | 0 | 6,487 | 107 | 15 | 0.00926 | 2.2 | ok | yes |
| 779 | divide_conquer forced check | 4,008 | 3,439 | 0 | 51 | 0 | 0.00100 | 2.1 | ok | yes |
| 89 | divide_conquer forced check | 4,515 | 3,907 | 0 | 69 | 0 | 0.00115 | 2.0 | ok | yes |
| 62 | divide_conquer forced check | 7,580 | 6,899 | 0 | 90 | 0 | 0.00148 | 2.0 | ok | yes |

(The low-effort linked rows were made while the linked prefix still carried a breakpoint, hence their cache writes.)

Prompt caching works across the strategies that share the full-schema grammar: on every question the first one (`divide_conquer`) wrote the prefix and `query_plan`, `direct_full` and the repair turn read exactly that many tokens. All 27 distinct generation calls (30 table rows; the `small_linked` calls appear in both tables) and all 6 check turns returned grammar-valid SQL. The four gpt-6.1-sol strategies wrote byte-identical SQL on all three questions at both efforts; only the small model differed (an added `LIMIT 1`, an extra NULL guard).

Three challenging questions were run with `divide_conquer` and `direct_full` only, to see the cost tail:

| Q | Strategy, effort | Input | Cached | Cache write | Output | Reasoning | USD | Latency s | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 116 financial | divide_conquer, low | 4,363 | 3,907 | 0 | 193 | 76 | 0.00162 | 4.3 | ok, EX no* |
| 116 financial | direct_full, low | 4,186 | 3,907 | 0 | 149 | 28 | 0.00122 | 3.9 | ok, EX no* |
| 116 financial | divide_conquer, medium | 4,363 | 3,907 | 0 | 336 | 228 | 0.00233 | 7.5 | ok, EX no* |
| 116 financial | direct_full, medium | 4,186 | 3,907 | 0 | 163 | 55 | 0.00129 | 8.1 | ok, EX no* |
| 218 toxicology | divide_conquer, low | 2,904 | 0 | 2,456 | 8,000 | 91 | 0.04352 | 71.6 | runaway |
| 218 toxicology | divide_conquer, medium | 2,904 | 0 | 2,456 | 8,000 | 257 | 0.04352 | 126.2 | runaway |
| 416 card_games | divide_conquer, low | 7,530 | 0 | 7,082 | 4,000 | 74 | 0.02930 | 33.8 | runaway |
| 416 card_games | divide_conquer, medium | 7,530 | 0 | 7,082 | 4,000 | 192 | 0.02930 | 39.0 | runaway |

\* All four Q116 queries return 430.4545454545455 against gold's 430.45454545454544; the official EX compares values exactly, so a different but equivalent arithmetic order scores as wrong. The `max_output_tokens` cap was 8,000 for Q218 and 4,000 for Q416. `direct_full` was not run on Q218 and Q416: the budget check stopped the run after the runaways.

### Runaway string literals (fixed in the grammar)

On Q218 (gold `T1.label = '+'`) and Q416 (gold `T1.power = '*'`) every `divide_conquer` attempt, at both efforts, wrote a valid prefix of the right query and then never closed the one-character literal: `WHERE T1.label = '+ за' AND T1.label = '+ final' AND ... '+ answer' AND ... '+ done' AND ... '+ end'`, or `T1.power = '*ரு' OR T1.power = '* grant' OR ... '*$' OR '*%'`, until `max_output_tokens` (26,856 characters on Q218). Each runaway cost the whole output cap: $0.044 at 8,000 tokens, about $0.125 at the old 25,000 default. 26 of the 350 dev questions have a one-character punctuation literal in their gold SQL (15 on toxicology, 7 on thrombosis_prediction). Apart from these runaways and the failed repair turns described above, every generation and repair call in the smoke used at most 336 output tokens.

The cause is tokenization on the hosted decoder: a quote, one punctuation character and the closing quote form a single token there, and once the model is at `'+` it practically never emits the lone closing quote. The grammar now accepts a string that starts with one of `" # ( ) * + - . / : = ? [` only as that character alone or followed by a digit, so after `'+` the closing quote is forced; other such values are written as a concatenation, `'(' || 'none)'` (ADR-005, "One-character punctuation literals and the hosted decoder"). `generate_common@1.1` adds the same rule to the spelling section, with the character list read from `grammar.conventions.TRAP_PUNCTUATION`, and a test checks that the spellings the prompt recommends parse and the one it forbids does not. One check after the fix, with the new grammar and prompt:

| Q | Strategy, effort | Input | Cached | Cache write | Output | Reasoning | USD | Latency s | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 218 toxicology | divide_conquer, medium | 3,083 | 0 | 2,635 | 464 | 382 | 0.00606 | 7.9 | ok, `T1.label = '+'`, EX no |

The literal closes. The query misses gold because it computes the share of atoms rather than of molecules, a reasoning error, not a grammar one. ADR-005 reports 10 of 10 correct runs of gpt-6.1-sol on Q218, Q197 and Q416 with the new grammar; they were not repeated for this ADR. The default `max_output_tokens` was also lowered to 4,096, with a per-call override (ADR-006), which bounds the cost of any future runaway.

### Cost per question

From the medium-effort rows, with the full-schema prefix warm (written by an earlier question on the same database within 30 minutes): a full-view call costs $0.0007 to $0.0015 (up to $0.0023 for a harder question), `direct_linked_fewshot` $0.0032 to $0.0077 because its prompt is never cached, `small_linked` $0.0002 to $0.0005, and a repair turn on a full-view candidate $0.0010 to $0.0016. That puts N = 5 at roughly $0.009 per question and N = 1 at roughly $0.0013, plus one prefix write of $0.005 to $0.01 per database and effort. The smoke prefixes (mean 4,748 tokens) are close to the dev-split mean estimated from rendered schema sizes (about 4,800), so for the 350 dev questions generation alone costs about $3 at N = 5, $0.5 at N = 1 and $0.4 for the `direct_full` baseline, before question analysis, linking, selection, repairs and runaways. The linked strategy is the most expensive per call; dropping it, or caching a wider per-database linked schema, is the first lever if N = 5 runs are too dear.

## Consequences

- On these questions the method prompts did not change what gpt-6.1-sol wrote: its hidden reasoning was 10 to 70 tokens and the four gpt-6.1-sol strategies agreed byte for byte. Diversity for voting and pass@N will come mostly from the linked schema with few-shots and the small model, and repeated samples may add little. The N-sweep in the iteration rounds should report how often candidates agree before paying for N = 8.
- Repair needs the extra user message on gpt-6.1-sol. ADR-006's live check of a plain tool-output repair turn used gpt-6-luna; it does not carry over.
- Mixing efforts across full-view strategies splits the cache; an effort override must apply to all of them.
- A grammar call that fails inside constrained decoding costs the whole output cap. The punctuation-literal fix removes the known case; the lower per-call output cap bounds unknown ones.
- Prompt text changes need a version bump (`prompts/*.yaml` changelogs) and invalidate cached responses by design. The grammar fix and `generate_common@1.1` changed every generation request, so cached responses recorded before them (this ADR's smoke tables, any baseline replay) no longer match live requests and have to be re-recorded once.

## Sources

Read on 2026-10-16:

- OpenAI, Reasoning models guide (reasoning items with tool calls, `reasoning.context`, encrypted reasoning in stateless mode, `max_output_tokens` and incomplete responses): https://developers.openai.com/api/docs/guides/reasoning.md
- OpenAI, Prompt caching guide (explicit breakpoints, 1.25x write and 0.05x read on gpt-6.1-sol, 30-minute lifetime, settings that change the cached prefix including `reasoning.effort`, per-machine caches): https://developers.openai.com/api/docs/guides/prompt-caching.md
- `docs/research/prompts-from-papers.md` (this repository): CHASE-SQL divide-and-conquer and query-plan templates via the CHESS repository (Part 2, 1a and 1b), the CHASE-SQL query fixer (1d), DIN-SQL generic and gentle self-correction (Part 1, section 6), Agentar-Scale-SQL's database admin instructions (Part 3, section 4). The papers themselves were not re-read for this ADR.
- ADR-001, ADR-005, ADR-006 and ADR-008 of this repository.
- Live measurements: `runs/spend_ledger.jsonl` (phase `generation`) and the response cache (`cache/llm/shards/`).
