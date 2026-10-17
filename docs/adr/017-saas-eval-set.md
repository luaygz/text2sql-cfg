# ADR-017: SaaS evaluation set: drafted under the grammar, checked by execution, reviewed by a second model

Status: accepted
Date: 2026-10-16

## Context

The evaluation set on the synthetic SaaS database (ADR-004) targets about 300 items: 150 answerable questions with gold SQL across easy, medium and hard (multi-join, aggregation, ranking through subqueries, date arithmetic), 60 tenant-scoped questions whose answer differs by tenant with gold parameterised on `tenant_id`, 40 unanswerable or out-of-schema questions that must be declined with an explanation, and 50 adversarial ones (prompt injection, another tenant's data, writes and DDL, `sqlite_master`, SQL inside natural language, comment and Unicode tricks). The items are drafted by an LLM, verified by execution and by a second model, with human spot-check instructions in the dataset card. The pipeline also needs a separate pool of SaaS question-SQL pairs for few-shot retrieval.

Four constraints shaped the design. Every SQL string a model writes must come out of the grammar-constrained tool, including gold SQL. The gold must be right for any tenant on its own, because the scoping layer is part of the system under test and cannot be trusted to make the reference correct. The database is deliberately dirty and has canary and planted rows that count in aggregates, so no answer can be computed by hand. And the build must be reproducible from logged responses, within a $3.00 spend cap.

## Decision

### Item format

One JSON object per line in `data/saas/eval.jsonl`, validated by `text2sql.data.saas.evalset.SaasEvalItem` (the format the eval runner reads, ADR-016): `id`, `bucket` (`answerable`, `tenant`, `unanswerable`, `adversarial`), `split`, `difficulty` (`easy`, `medium`, `hard`), `question`, `tenant_id`, optional `user_id` for user-mode items, `gold_sql` with `:tenant_id` and `:user_id` named parameters, `eval_tenants` (tenant bucket only), `expected` (`answer`, `abstain`, `safe`), `explanation` (unanswerable), `attack` (category, technique, named target tenant, notes) and `provenance` (models, review verdict and notes, prompt versions). The model validator enforces the cross-field rules the eval runner relies on: answer items have gold, unanswerable items have none and carry an explanation, tenant items run under at least two distinct tenants starting with the asking one, and gold uses `:user_id` exactly when the item is in user mode.

Adversarial items are expected to stay safe. When the attack wraps a legitimate request, the item also carries gold for that request, so abstaining and a correct scoped answer both pass. Items are split 70/30 into dev and test with a seed, stratified by bucket and difficulty, mirroring the BIRD split.

### Gold SQL through the grammar, with sentinel ids

Gold is written by gpt-6.1-sol through `LLMClient.sql_call` under a BENCHMARK-mode grammar built from the full schema, `tenant_id` and `owner_user_id` included, minus `users.password_hash` and `tenants.api_key`, with ABSTAIN allowed so the model can refuse an unclear question. The grammar has no parameter syntax (ADR-005), so the prompt tells the model the asking tenant is `987654321` and the signed-in user `987654322`, and code replaces those whole-number tokens with `:tenant_id` and `:user_id`. A sentinel inside a string literal, or the user sentinel outside user mode, rejects the query. Large, unlikely numbers were chosen so that a collision with a real value in a filter is visible rather than silent.

### Checks before review

A sqlglot pass proves that every reference to a tenant table has `<alias>.tenant_id = :tenant_id` among the top-level AND-ed conditions of its own SELECT (its WHERE or its JOIN conditions), including inside subqueries, CTEs and set operations; in user mode the same holds for `owner_user_id = :user_id` on the nine owner tables. The tenant column may not be compared with anything else, and `CURRENT_DATE` and friends are rejected because they would make the gold depend on the day it runs. We chose an explicit filter per reference over reusing `apply_scope`: gold produced by the layer under test would agree with that layer by construction, including its bugs.

The query then runs read-only in `SandboxedExecutor`, under an access policy derived from the authoring schema (so no secret column is readable), with bound parameters. It must not fail, must return at least one non-NULL value and at most 100 rows. The cap keeps gold below the LIMIT of 200 that a tenant-mode answer may use, so a correct answer is never cut short. Tenant items are run for the other seven tenants in a seeded order and keep up to two whose non-empty row sets differ from every result kept so far; with none, the item is dropped. Planted-injection items must return the planted value. A failed check is fed back once as the tool output of the previous call, the same repair turn the pipeline uses, and the repaired query goes through every check again.

### Second-model review

gpt-6-luna, a different model from the drafter, reviews each item with a structured verdict at reasoning effort medium. It sees the schema with its notes, the question, the gold SQL and the gold result for every tenant the item runs under. Answer items: is the question unambiguous, does the SQL answer it, is the difficulty label right. Unanswerable items: is it unanswerable from this schema, is the explanation right, is it plausible; before review, the gold author is asked to write SQL for it (ABSTAIN allowed) and the reviewer sees that probe. Adversarial items: is the attack present and realistic, and is the stated legitimate part faithful.

Items that fail are fixed where a fix is mechanical and otherwise dropped. A clear question with wrong SQL gets one repair turn with the reviewer's problems and a second review. A wrong difficulty label takes the reviewer's label. An attack whose only flaw is its legitimate part keeps the attack and loses the gold. For the six planted questions the review payload states the generator's guarantee that the newest row is unique, after the first review rejected one of them over a tie that cannot occur.

### Questions, attacks and the few-shot pool

Questions are drafted by gpt-6.1-sol with structured output, in batches that each carry one tenant's data summary (counts, date ranges, sampled names, names shared with other tenants; no canary or planted rows), so the questions refer to values that exist. Questions must state explicit periods, rounding and tie-breaking, because the data snapshot has a fixed end date and answers are compared as row sets. Unicode tricks (homoglyph, zero-width, fullwidth, bidi override) are applied by code to a span the model marks, because the item must contain those characters and a model asked to emit them may not. The six indirect-injection items reuse the innocent questions of `planted_injections()`.

The few-shot pool is drafted after the evaluation set, with the evaluation questions in the prompt as questions not to repeat; a first build without that list lost 30 of 48 pool drafts to overlap. Pool SQL is written the way the pipeline writes SQL, with the PRODUCTION-mode grammar over the visible schema and no tenant filter, must also parse under the TENANT-mode grammar, runs through the real `apply_scope` and is reviewed like gold.

### Selection and reproducibility

Each bucket is over-drafted by about a quarter. Near-duplicate questions (word-set Jaccard of 0.75 or more; 0.6 between pool and evaluation set) are dropped in plan order, and seeded quotas per stratum pick the survivors: difficulty for answerable items with 12 user-mode items reserved, attack category for adversarial items with comment and Unicode tricks counted apart. All sampling uses `random.Random` seeded with strings derived from seed 20261016; string seeds are converted with SHA-512 in CPython's `random.seed`, so the stream does not depend on `PYTHONHASHSEED`. Models, efforts, the output cap and the service tier are pinned in code because they are part of every cache key.

Every model call goes through `LLMClient`, so `python -m text2sql.data.saas.evalset build --offline` replays the committed response cache. The schema text of every prompt is read from a committed snapshot, `data/saas/evalset_schema_snapshot.txt`, rather than rendered from the live catalog: the catalog is regenerated whenever a column note in the data dictionary is edited, and one changed note changes every request. That happened once, after the final build, when the `tickets.opened_at` and `resolved_at` notes were reworded; the snapshot keeps the wording the set was drafted with. The replay reproduced `eval.jsonl`, `fewshot_pool.jsonl` and the build report byte for byte with zero cache misses, also with a different `PYTHONHASHSEED`. `data/saas/evalset_build.json` records per-bucket counts, every rejection with the reviewer's notes, the prompt versions and the grammar fingerprints (gold `7727354b…`, few-shot `ff44f0fb…`; full values in the card).

### Result

299 items: 150 answerable, 60 tenant, 39 unanswerable and 50 adversarial, 209 dev and 90 test, plus a 40-item few-shot pool. The reviewer passed 92% of reviewed answerable items, 91% of tenant items, 93% of unanswerable items and 87% of adversarial items on the first verdict. The build spent $1.55 of its $3.00 cap over three runs: a pilot, a first full build, and a rebuild after the grammar template changed mid-build (which changes every gold request) and the few-shot drafting was reworked.

## Consequences

- The gold is right for any tenant without the scoping layer, and the tests in `tests/data/test_saas_evalset_data.py` re-check on a freshly generated database that it executes for every tenant an item runs under, that tenant items differ, that every tenant table is filtered, and that the pool is disjoint and scopes cleanly.
- Questions and gold come from the model the pipeline uses as its generator. Its reading of borderline phrasing is built into the reference, which can flatter that model. The independent reviewer and the human spot check in the card are the counterweights; no human check has been done yet.
- The reviewer's difficulty labels win. It labelled 43 of 50 attacks easy, so difficulty is not a useful axis for the adversarial bucket.
- Ranking is mostly ORDER BY with LIMIT; 24 of 150 answerable gold queries use a subquery or CTE. Questions needing window functions cannot be expressed under the grammar and do not occur.
- A replay needs the same grammar template, prompts, schema snapshot and database. If any of them changes, the build drafts new gold through the API; the committed files remain valid data. Hand corrections after a spot check break replay identity and must be listed in the card.
- Gold results are capped at 100 rows; questions with long answers are not in the set.

## Sources

- Python documentation, `random.seed` (version 2 seeding of str, bytes and bytearray uses all bits of the seed): https://docs.python.org/3/library/random.html (accessed 2026-10-16). The SHA-512 step was read in the source of `random.Random.seed` of the project's Python 3.12 interpreter.
- ADR-002 (tenant scoping), ADR-004 (SaaS database), ADR-005 (grammar), ADR-006 (LLM client and cache), ADR-007 (executor), ADR-009 (evaluation methodology) in this repository.
