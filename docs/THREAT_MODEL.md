# Threat model

This document covers the path from a natural-language question to rows returned from SQLite: what
we protect, whom we do not trust, which layer stops which attack, what is left over, and where
each claim is tested. The design behind the scoping layer is in
[ADR-002](adr/002-tenant-scoping.md), and the executor's design is in
[ADR-007](adr/007-sandboxed-executor.md).

## System in one paragraph

A question (plus schema text, retrieved values and few-shot examples) goes to an OpenAI model.
The model may answer only by calling the `sql_query` custom tool, whose input is constrained by
a Lark grammar generated from the visible schema (layer 1). The client re-parses the returned
string with the same grammar, and the system never executes SQL that arrives as free text. The
SQL then passes the AST validator (layer 2, `text2sql.safety.validate_sql`). In tenant mode it
is rewritten so that every scoped table is read through a guard bound to the caller's identity,
and the rewrite is proven (layer 4, `apply_scope` / `verify_scope`). The statement finally runs
in a sandboxed, read-only SQLite worker (layer 3, `text2sql.execution.SandboxedExecutor`). Each
layer assumes the ones before it have failed. A rejection at any layer is logged as a
`SafetyEvent` (JSONL, `runs/safety_events.jsonl` by default) and is never repaired by the layer
that raised it.

## Assets

- Rows belonging to other tenants: every table in `ScopePolicy.tenant_tables`. In user mode, this
  also covers rows of owner-scoped tables that belong to other users of the same tenant.
- Secret columns, never shown to the model or returned: `users.password_hash` and
  `tenants.api_key` in the SaaS database (`ScopePolicy.hidden_columns`).
- The tenant identifier itself. The model must not be able to choose it, filter on it or learn
  other tenants' values.
- Integrity of the database files: they are read-only by construction.
- Availability of executor workers, and the OpenAI budget (`MAX_SPEND_USD`, enforced by the LLM
  client).
- The host: no file reads or writes, extension loading or attached databases through SQL.

## Trust boundaries

Untrusted:

- The question text. Users can write anything, including instructions aimed at the model.
- The model's output: both the tool-call input and anything it says. We treat the model as
  possibly confused or adversarial, and we assume it can emit any string the grammar admits, or
  any string at all if grammar enforcement fails server-side.
- Database values. Customer names, ticket subjects, notes and similar fields can carry planted
  instructions (indirect prompt injection; ADR-004 plants such rows), and they reach the model
  through value retrieval, sample values and repair-loop feedback.
- Benchmark questions and fetched web pages, which are data and never instructions.

Trusted:

- The `ScopeContext(tenant_id, user_id)` handed to the safety layer by the caller. In a
  deployment it must come from authentication. In this repository the CLI and demo take it as
  an argument, so binding it to a real login is outside this codebase.
- Static configuration: `ScopePolicy`, the schema catalog, the grammar builder and the executor's
  `AccessPolicy`.
- The SQLite library, sqlglot, lark and llguidance as installed from `uv.lock`.

## Attackers and goals

- A malicious user of tenant A writes the question directly. They want tenant B's rows, the
  secret columns, writes or DDL, schema discovery (`sqlite_master`, `PRAGMA`), file or extension
  access (`ATTACH`, `load_extension`), denial of service through expensive queries, or simply to
  burn API budget.
- An outsider plants text in a database value that later lands in a prompt. Their goals are the
  same as above, carried out through the model, plus steering the answer text that users read.
- A misbehaving model, with no attacker involved. Hallucinated tables and columns, missing
  LIMITs, or queries that ignore the tenant must fail safe.

In user mode, a user of tenant A who wants a colleague's owner-scoped rows is also in scope.

## Mitigations by layer

### Layer 1: grammar-constrained generation

Owned by `text2sql.grammar`; ADR-001 records the API facts. Only identifiers from the visible
(or linked) schema exist as terminals, so the tenant column and hidden columns cannot be
emitted. The output is a single SELECT (CTEs named `cte1`...`cte5`, set operations allowed) with
no `;`, no comment syntax, no bind parameters and no functions outside the allowlist. LIMIT is
required and bounded in production and tenant mode, and the tenant-mode grammar has no `*`
projections. The grammar is enforced by OpenAI's servers, which we cannot inspect, so the client
re-parses every tool input locally, and the layers below assume the grammar let anything
through.

### Layer 2: AST validation (`text2sql.safety.validate_sql`)

The validator parses with sqlglot's SQLite dialect and accepts only what the grammar should have
produced. Every rejection carries a stable rule id (`text2sql.safety.Rule`):

- Shape: `too_long`, `parse_error`, `multiple_statements` (any `;`), `not_select` (DML, DDL,
  PRAGMA, ATTACH, transactions, EXPLAIN, VALUES).
- Parser differentials: `comment` (any comment), `non_ascii` (outside string literals and quoted
  identifiers, which catches homoglyphs and no-break or zero-width spaces), and
  `forbidden_construct`. The last is an allowlist of syntax nodes that excludes window functions,
  RIGHT/FULL/NATURAL/USING joins, `ESCAPE`, `GLOB`, blobs, `SELECT ... INTO`, `INDEXED BY`, and
  `expr IN table`, which sqlglot parses as a column while SQLite reads the whole table.
- Names: `unknown_table`, `unknown_column`, `ambiguous_column`, `system_table` (`sqlite_*`),
  `schema_qualifier` (`main.`, `temp.`), `invalid_cte` (recursive, duplicate, or shadowing a
  table), and `scope_error`. Columns are resolved per query scope, covering correlated
  subqueries, derived-table and CTE outputs, and select-list aliases, so `T1.col` must be a
  column of T1's own table.
- Identity: `hidden_column` (the tenant column and `hidden_columns`, wherever they appear),
  `placeholder` (`?`, `:name`, `@name`, `$name`; the model cannot smuggle `:tenant_id`), and
  `star_in_tenant_mode`.
- Functions: `function_not_allowed`. The name checked is the one written in the source, so
  `IFNULL`, `LTRIM` and `SUBSTRING` are rejected even though sqlglot normalizes them to allowed
  node types.
- Size: `missing_limit`, `limit_too_large`, and `invalid_limit`. The last requires a plain
  non-negative integer literal, because SQLite reads `LIMIT -1` as "no limit".

### Layer 4: tenant scoping (`apply_scope`, `verify_scope`)

Every reference to a scoped table is replaced, in the original text, by a derived table that
projects only visible columns and filters on `tenant_id = :tenant_id`, plus
`owner_user_id = :user_id` for owner tables in user mode. The filter therefore holds on both
sides of a LEFT JOIN, inside subqueries, CTEs and set operations, and in self-joins, and the
tenant column cannot be named outside the guard. Parameter values come only from
`ScopeContext`, whose fields must be integers. `verify_scope` re-parses the final SQL and proves
that each scoped table reference is such a guard with exactly the expected parameter-bound
predicates, that no CTE shadows a scoped table, and that no bind parameter exists outside a
guard. It does not trust `apply_scope`.

### Layer 3: sandboxed execution (`text2sql.execution`)

The executor opens the database with `file:...?mode=ro` and sets `PRAGMA query_only = ON` and
an attached-database limit of 0. An authorizer allows only SELECT, reads of the columns in
`AccessPolicy.readable` (in tenant mode, `ScopePolicy.readable_columns`: visible columns plus the
tenant column, never `hidden_columns`) and calls to allowlisted functions; everything else is
denied, including `sqlite_master` and `pragma_*` table-valued functions. A progress-handler
deadline (2 s by default) and a 10 MB value-size limit bound the work, rows are capped with
`fetchmany`, and the query runs in a worker process that is killed if it overruns the deadline
by more than a second. None of this depends on sqlglot.

## Attacks and where they stop

The first layer listed is the one that should stop the attack; later layers stop it again if
earlier ones fail.

| Attack | Layers |
| --- | --- |
| DDL / DML / PRAGMA / ATTACH / transaction statements | grammar; validator `not_select`; executor authorizer, `query_only`, `mode=ro` |
| Second statement after `;` | grammar; validator `multiple_statements`; `sqlite3` executes one statement |
| Comments hiding text, nested-comment tricks | grammar; validator `comment` |
| `sqlite_master`, `pragma_table_info(...)` | grammar; validator `system_table` / `unknown_table`; authorizer |
| `load_extension`, `printf`, `random()` and other functions | grammar; validator `function_not_allowed`; authorizer function allowlist |
| Another tenant's rows via joins, subqueries, set operations, CTEs, LEFT JOIN | scoping guard plus proof; the tenant column is invisible to grammar and validator |
| Model writes `tenant_id = 2`, `OR 1 = 1`, or `:tenant_id` | grammar; validator `hidden_column` / `placeholder`; outside a guard `tenant_id` does not exist; `verify_scope` rejects stray parameters |
| `main.deals`, `(deals)`, `deals INDEXED BY`, `x IN deals` | validator; `verify_scope` (`unguarded_table`) |
| `SELECT *` exposing hidden or tenant columns | grammar; validator `star_in_tenant_mode`; guards project visible columns only; authorizer denies hidden columns |
| Prompt injection in the question | does not widen what any SQL can reach: every layer below the model holds |
| Indirect injection in database values | same as above; it can still distort the answer (see residual risks) |
| Over-long output, deep nesting | grammar; validator `too_long`; parser recursion becomes `parse_error` |
| Unicode homoglyphs, invisible characters | identifiers are enumerated in the grammar; validator `non_ascii`; quoted homoglyphs fail as unknown names |
| Recursive CTE or `LIMIT -1` for unbounded work | grammar; validator `invalid_cte` / `invalid_limit`; authorizer denies recursive CTEs; deadline and kill |

## Residual risks

- Inference through aggregates inside the tenant. Scoping makes other tenants' rows unreadable,
  so their values cannot be inferred from results. Within a tenant, aggregates over small groups
  reveal individual values, and in user mode the tenant-wide tables (`users`, `teams`, `tenants`)
  stay visible to every user of that tenant. Nothing here implements differential privacy or
  minimum group sizes.
- Timing side channels. Query time depends on how the plan touches the base tables. With an
  index on `tenant_id` the guards turn into index searches (ADR-002), but a plan that scans a
  whole table does work proportional to all tenants' rows, and the executor returns
  `elapsed_s`. A patient attacker could estimate the total table size, though not any value from
  another tenant.
- Denial of service with expensive queries. Cross joins, many-way joins and `LIKE '%x%'` over
  large tables are grammatical. The deadline, the value-size limit, the row cap and the worker
  kill bound one query to about `timeout_s + 1 s` of one core, but nothing here rate-limits
  requests; that belongs in front of the service. The LLM budget cap stops runaway spend, not
  abuse by many users.
- Steered answers. Indirect injection cannot widen access, but it can make the model pick a
  wrong (still scoped) query or write misleading prose around the results. Answer text should be
  shown as model output, not as fact.
- Prompt-side leakage. Data reaches the model through prompts as well as through SQL. The catalog
  builder withholds sample values and column statistics for tenant-scoped tables because the
  catalog is shared across tenants (`text2sql.catalog.builder`). The value index is shared by all
  tenants' requests, so for tenant-scoped tables it holds only low-cardinality values that occur
  in every tenant (`text2sql.retrieval.values`, ADR-011); anything tenant-specific in a shared
  index would let a prompt for tenant A carry tenant B's values.
- Parser agreement. Layers 2 and 4 reason about sqlglot's reading of the text, while SQLite
  executes it. The known differentials are rejected, and the scoping splice keeps executed text
  identical outside the guards. An unknown differential could still let something past layers 2
  and 4, and the authorizer is the backstop that does not share sqlglot's view.
- Identity binding. If the caller builds `ScopeContext` from user input instead of an
  authenticated session, every guarantee above applies to the wrong tenant.
- Views and new tables. Scoping guards tables listed in the policy. A view over a scoped table,
  or a new tenant table missing from `tenant_tables`, would be read unguarded. The SaaS database
  has no views today, and the catalog lists only tables.
- Logs. Safety events store the rejected SQL and request context. They contain no secrets by
  construction, but they can include literal values from questions.

## What is tested where

- `tests/safety/test_safety_validator.py`: every validator rule with accepted and rejected
  examples (131 rejections, 33 accepted shapes run in all three modes); 100% branch coverage of
  `validator.py` from this file alone.
- `tests/safety/test_safety_validator_props.py`: hypothesis-generated grammar-shaped queries
  validate in every mode; 16 injected attacks (comment, second statement, no-break space, INSERT,
  window, `IN table`, placeholder, function, schema qualifier, `sqlite_master`, unknown table,
  hidden column, `*`, negative, oversized and missing LIMIT) each fail with their specific rule;
  token soup and arbitrary text only ever produce a `ValidationError`.
- `tests/safety/test_safety_scoping.py`: guard shape, user mode, identifier spellings, refusal of
  references that cannot be guarded, 20 tampered guards rejected by `verify_scope`, 25
  cross-tenant attacks across 6 identities checked against the identity oracle and for foreign
  canaries, and the same attacks run through `SandboxedExecutor` under its authorizer.
- `tests/safety/test_safety_scoping_props.py`: 400 generated queries per run; scoped results equal
  the oracle's and contain no foreign canary.
- `tests/safety/test_safety_saas.py`: on `data/saas/crm.sqlite` (skipped when it is absent), every
  canary column returns exactly the caller's canary token for all 8 tenants, cross-tenant joins
  and unions return no foreign token, `tenants` is self-scoped, and user mode returns only the
  caller's rows.
- `tests/safety/test_safety_events.py` and `tests/safety/test_safety_policy.py`: the event log
  (round trip, concurrent writers, strict reading) and the policy (hidden columns, visible
  schema, readable columns).
- `tests/execution/`: the executor's authorizer, read-only enforcement, timeouts, kills and row
  caps.
- `tests/safety/test_guard.py`: `QueryGuard` runs the layers in order, logs exactly one event per
  refusal with the request context, still denies a hidden column at layer 3 when layers 1, 2 and
  4 are switched off, logs timeouts but lets them and ordinary SQLite errors reach the repair
  loop, and refuses caller mistakes (no `ScopeContext` in tenant mode, a grammar for another
  mode, an abstention).
- `tests/safety/test_adversarial_suite.py` and `test_adversarial_leaks.py`: the SQL-level
  adversarial suite below, and the leak detector it shares with the SaaS evaluation.

## Adversarial suite results

`text2sql safety` (`make safety`, and `tests/safety/test_adversarial_suite.py` in CI) runs the
225 cases in `evals/safety/cases.yaml` against a freshly generated SaaS database, through the
full guard in tenant mode and through each layer alone with the layers before it switched off.
[ADR-015](adr/015-guard-and-adversarial-suite.md) defines the cases, outcomes and metrics; the
full report is `reports/safety/safety_suite.md`. Run of 2026-10-16:

| Layer | Full guard: first stop | Alone: responsible for / held | Alone: stopped (all cases) | Alone: leaked |
| --- | --- | --- | --- | --- |
| grammar | 170 | 169 / 169 | 170 | 0 |
| validator | 3 | 170 / 170 | 170 | 0 |
| scoping | 0 | 106 / 106 | 108 | 0 |
| executor | 9 | 114 / 114 | 143 | 70 |
| ran, no leak | 43 | | | |

Violations reaching layer 3: 0. Violations reaching the database: 0. Every stop was logged as
exactly one safety event, and the database file's checksum did not change.

The cases cover DDL and DML, multiple statements, comments, `sqlite_master` and PRAGMA, ATTACH
and file or extension functions, 20 non-allowlisted functions, recursive CTEs and blob builders,
expensive joins and oversized values or results, 34 cross-tenant probes (joins, LEFT JOIN,
self-joins, subqueries in every clause, correlated subqueries, set operations, CTE chains,
aggregates and boolean inference), 9 user-mode probes, hidden and tenant columns reached in every
clause, placeholder smuggling including a forged guard, Unicode homoglyphs and invisible
characters, quoting tricks, `expr IN table`, CTE and schema-qualifier shadowing, over-long SQL
and LIMITs, and the SQL each planted injection asks for. Scoping stops nothing under the full
guard because it rewrites rather than rejects; the 43 contained runs are its work. The executor
alone leaks on the cross-tenant probes, which it cannot filter by tenant.

Building the suite found one gap, now closed: a constant 9.75 MB expression repeated on every row
passed the per-value cap, so `LIMIT 40` returned 390 MB past a 2 s deadline and `LIMIT 1000`
would have materialised about 9.7 GB per worker. The executor now caps total result size and
worker heap (`ResultTooLarge`). The suite also showed that the grammar bounds neither SQL length
nor nesting depth; the validator's length cap and parser recursion limit stop both.

Prompt injection in the question and in planted database values goes through the model and is
judged per item by `text2sql.safety.leaks.judge_attack` in the SaaS evaluation, not here.

## References

- Pedro, Castro, Carreira, Santos. From Prompt Injections to SQL Injection Attacks: How Protected
  is Your LLM-Integrated Web Application? arXiv:2308.01990, 2023.
  https://arxiv.org/abs/2308.01990 (accessed 2026-10-16). Prompt-to-SQL injection, including
  the indirect variant through stored values that the trust boundaries above account for.
- SQLite documentation pages cited in ADR-002 (accessed 2026-10-16).
