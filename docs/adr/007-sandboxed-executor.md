# ADR-007: Sandboxed SQLite executor

Status: accepted
Date: 2026-10-16

## Context

Layer 3 of the safety design runs SQL that has already passed the grammar (layer 1) and the sqlglot validator (layer 2), but it is written on the assumption that both failed. Whatever string reaches it, the executor must guarantee that the database file is never modified, that only allowlisted tables, columns and functions are touched, that no other file is read or written, and that no query runs much longer than its time limit. It also has to be fast enough to execute every candidate query the pipeline generates, plus the BIRD gold SQL, which needs time limits of tens of seconds rather than the 2 s default.

The design starts from these ingredients: `file:…?mode=ro`, `PRAGMA query_only = ON`, `Connection.set_authorizer`, a `set_progress_handler` timeout, `fetchmany` for the row cap, and a worker process that is killed on timeout. This ADR records how they are combined, what the SQLite authorizer actually reports for the SQL we generate, the process model and its measured cost, and what is still not covered.

All observations below are from Python 3.12.12 with its bundled SQLite 3.50.4, on the development machine (Linux, 12 CPUs, shared with other jobs while measuring), on 2026-10-16. The latency and throughput numbers come from `scripts/bench_executor.py` (`uv run --frozen python scripts/bench_executor.py`, no network); the authorizer observations are pinned by the tests in `tests/execution/`.

## Decision

### Connection

`text2sql.execution.sandbox.Sandbox` opens the database as `file:<percent-encoded absolute path>?mode=ro` with `uri=True` and `isolation_level=None`, so the `sqlite3` module never issues an implicit `BEGIN`. Before the authorizer is installed it runs `PRAGMA query_only = ON`, sets `SQLITE_LIMIT_ATTACHED` to 0, and reads the names of all tables and views from `sqlite_master`. Each query additionally sets `SQLITE_LIMIT_LENGTH` (largest string, blob or row) to `ExecutionLimits.max_value_bytes`, 10 MB by default.

The length limit was not part of the original design. It was added after this measurement: `SELECT LENGTH(REPLACE(REPLACE(… 'aaaaaaaaaa' …)))` with eight nested `REPLACE` calls, all allowlisted and grammar-valid, built a 1 GB string in 1.75 s, with a peak resident size of about 2 GB reported by `/usr/bin/time -v`. Each `REPLACE` is a single bytecode instruction, so the progress handler cannot interrupt it. With the limit, the same query fails within milliseconds with SQLite's "string or blob too big" (`test_value_size_limit_stops_string_amplification`). The SQLite authorizer documentation itself suggests lowering `sqlite3_limit()` values for untrusted SQL.

### Result size and memory

A per-value limit does not bound a result. The adversarial suite found `SELECT REPLACE(REPLACE('<150 a>', 'a', '<255 a>'), 'a', '<255 b>') FROM accounts LIMIT 40`, valid under the tenant-mode grammar and validator: each value is 9.75 MB, under the 10 MB limit, and the expression is constant, so SQLite computes it once and the progress handler never fires while the `sqlite3` module copies it into 40 rows. Rerun on `data/saas/crm.sqlite` with the size limits below disabled, it returned 390 MB in 2.34 s with peak resident sizes of 1,136 MB in the parent and 1,157 MB in the worker. LIMIT 1000 is also grammar-valid.

Two limits close this, both in `ExecutionLimits` and both raising `ResultTooLarge`:

- `max_result_bytes`, 10 MB by default. `Sandbox.run` iterates the cursor one row at a time instead of calling `fetchmany`, and counts 8 bytes per column name and per cell plus the length of every name, string (in characters) and blob. The query fails as soon as the running total passes the limit; the extra row fetched only to detect truncation is not counted. The repro above now fails after its second row, in 0.02 s, with peaks of 37 MB (parent) and 60 MB (worker), at LIMIT 5, 40 or 1000 alike. For scale, running all 500 BIRD Mini-Dev gold queries in-process, the largest full result (question 346, 29,936 rows) counts 0.86 MB and the largest first 1,000 rows 57 kB; 7 queries could not be measured (5 use window functions outside the allowlist, 2 exceed 30 s).
- `max_memory_bytes`, 256 MiB by default: before each query the worker sets its soft `RLIMIT_DATA` to its data-segment size at start-up plus this allowance. A row is only visible to the byte count after Python has built it, and one row of 30 copies of the 9.75 MB value peaked the worker at 861 MB before the count refused it; with the cap it fails in 0.07 s with a 211 MB peak, and the same worker keeps serving. `RLIMIT_AS` was the obvious choice but does not work here: an idle worker already maps about 260 MiB, 222 MiB of it `/usr/lib/locale/locale-archive`, while its data segment is 13 MB. Since Linux 4.7, `RLIMIT_DATA` applies to `mmap(2)` as well as `brk(2)`, so the large allocations `malloc` serves through `mmap` count; in the probe a failed allocation, or SQLite's `SQLITE_NOMEM`, surfaced as Python's `MemoryError`. The cap is applied only on Linux and only in worker processes, never to an in-process `Sandbox`. All 493 measurable BIRD gold queries above also ran in-process within a 128 MiB `RLIMIT_DATA` allowance, fetching at most 1,001 rows each.

`SQLITE_TOOBIG` ("string or blob too big", the per-value limit) is reported as `ResultTooLarge` too, with SQLite's message unchanged.

### Authorizer

`text2sql.execution.authorizer.Authorizer` is an allowlist. It returns `SQLITE_OK` for:

- `SQLITE_SELECT`;
- `SQLITE_READ` of a table or view in the `main` schema whose name does not start with `sqlite_`, if the `AccessPolicy` allows that column. `readable=None` (benchmark mode) allows every column of every table and view; otherwise the policy maps table to columns, case-insensitively, and tables that do not exist in the file are dropped from it. A column-less read (column `""`) is allowed for readable tables, and for names that are not schema objects at all, which is how SQLite reports a scan of a materialized CTE;
- `SQLITE_FUNCTION` for names in `AccessPolicy.functions` (`DEFAULT_FUNCTIONS`);
- `SQLITE_RECURSIVE` only when `AccessPolicy.allow_recursive` is set (off by default; the grammar cannot produce recursive CTEs).

Everything else, including every action code SQLite may add later, is `SQLITE_DENY`. The authorizer records the first denial of each statement, and the error the caller sees names it (`not authorized: READ sqlite_master.sql`). This matters because SQLite does not report all denials the same way: a denied function call fails with `SQLITE_ERROR` and "not authorized to use function: randomblob", not with `SQLITE_AUTH`, so classifying by error code alone would misfile it as an ordinary query failure.

`DEFAULT_FUNCTIONS` is the function allowlist in the names SQLite reports (`count sum avg min max round abs coalesce iif nullif length upper lower trim substr instr replace strftime date julianday`), plus `like` for the `LIKE` operator and `current_date`, `current_time`, `current_timestamp` for the `CURRENT_*` keywords. A check against the grammar confirmed that it emits exactly these functions and keywords (18 of the 998 Mini-Dev gold queries, BIRD and Arcwise together, use `CURRENT_TIMESTAMP`; ADR-005); the validator's allowlist is the same set in SQL spelling.

Column-level policies exist for tenant mode: hidden columns such as `password_hash` are simply absent from `readable`, and the tenant column must be present, because the scoping rewrite reads it in the predicates it injects.

### What the authorizer sees

Observed by logging every callback for each construct:

| SQL construct | Callbacks |
| --- | --- |
| `SELECT a FROM t WHERE b = 1` | SELECT; READ(t, a); READ(t, b) |
| `SELECT count(*) FROM t` | SELECT; FUNCTION count; READ(t, "") |
| `LIKE`, `NOT LIKE` | FUNCTION like |
| `GLOB` | FUNCTION glob |
| `IIF(...)` | FUNCTION iif |
| `CURRENT_TIMESTAMP` / `CURRENT_DATE` / `CURRENT_TIME` | FUNCTION current_timestamp / current_date / current_time |
| `CAST`, `CASE`, `BETWEEN`, `IN (...)`, `IS NULL`, `\|\|`, `COLLATE`, `TRUE`, `FALSE` | nothing beyond the column reads |
| Function name spelling | reported lowercase as written: `CoUnT` is `count`; `SUBSTRING` is `substring`, not `substr` |
| `rowid` | READ of the `INTEGER PRIMARY KEY` column if the table has one, else READ(t, "ROWID") |
| A view | READ of the base-table columns with the view as source, then READ of the view's columns |
| A CTE | SELECT with the CTE as source; the base-table reads; a column-less scan of a materialized or constant CTE is READ(cte_name, "") |
| A recursive CTE, with or without the `RECURSIVE` keyword | RECURSIVE (SQLite does not require the keyword) |
| `UNION` / `INTERSECT` / `EXCEPT`, subqueries | one SELECT per select core |
| `sqlite_schema` | reported as READ(sqlite_master, …) |
| `pragma_table_info('t')` | READ(pragma_table_info, …) and PRAGMA(table_info, t) |
| `json_each`, `dbstat` | READ(json_each, key) and so on; `dbstat` additionally reads `sqlite_master` |
| `DROP TABLE` / `DROP INDEX` | DELETE(sqlite_master) first |
| `CREATE TABLE` / `INDEX` / `VIRTUAL TABLE` | INSERT(sqlite_master); `CREATE TEMP …` is INSERT(sqlite_temp_master) |
| `VACUUM`, `VACUUM INTO 'file'` | ATTACH |
| `BEGIN`, `COMMIT`, `ROLLBACK` / `SAVEPOINT`, `RELEASE` | TRANSACTION / SAVEPOINT |
| `readfile`, `writefile`, `REGEXP` | no callback: not registered in this SQLite build, so SQLite fails with "no such function" |
| `SELECT 1; DROP TABLE t` | refused by the `sqlite3` module: "You can only execute one statement at a time." |
| `EXPLAIN SELECT …` | the same callbacks as the SELECT; allowed (see residual risks) |

The test suite (`tests/execution/test_sandbox.py`) pins the outcome of 80 hostile statements of these kinds (74 refused by the authorizer, 6 by SQLite or the `sqlite3` module before it), including variants wrapped in CTEs, subqueries, set operations and joins, and checks the database file's SHA-256 and the directory listing before and after each one. Every case runs both in-process and through a worker process.

### Time limits: the wall clock where a user waits, steps alone where results must replay

The time limit serves two ends. In production and tenant modes a user is waiting and a slow query is a denial of service, so these modes use a wall-clock timeout (2 s by default) enforced through the progress handler. For benchmark candidates, a wall-clock limit made results depend on machine load: during live eval runs with eight questions in flight, a query near the limit timed out, an offline replay at low load did not, and because a timeout feeds the repair loop, the replay then sent requests the cache had never seen.

`ExecutionLimits.wall_clock` (default on) chooses. `Sandbox.run` always installs a `StepBudget` (`text2sql.sqlite_budget`, shared with the BIRD metric and the literal lookups) of `steps_for(timeout_s)` SQLite VM steps, 84 million per second of `timeout_s`, the rate measured on the reference machine for BIRD's slowest gold query. With `wall_clock` on it also gives the budget a deadline of `timeout_s`. The handler runs every 10,000 steps (`CHECK_INTERVAL`) and stops the statement at whichever limit it reaches first; both raise `QueryTimeout(timeout_s)`, so callers did not change. `execution_limits` in `pipeline/resources.py` turns the wall clock off for `QueryMode.BENCHMARK` candidates and for evaluation runs in any mode (the eval runner builds its `DatabaseResources` with `evaluation=True`); interactive production and tenant requests keep it. Evaluation runs on the SaaS database were added to that list on 2026-10-17, after a SaaS candidate that takes about 1.3 s on an idle machine timed out at 2 s during an ordinary offline replay and the replay sent a repair request the recording never made (EXPERIMENTS.md, "Determinism fixes"). The interval was chosen by timing a CPU-bound join (about 196 ms on a plain connection) 15 times at each setting, interleaved: the Python callback added 5.5% at 1,000 instructions, 0.6% at 10,000, and nothing measurable at 100,000.

With the wall clock on, fast query shapes usually hit the step budget first: this machine runs cross joins at about twice the calibration rate. The safety suite's five resource-exhaustion timeout cases, run one at a time through the guard on `data/saas/crm.sqlite`, were all stopped at layer 3:

| Case | Suite limits (1 s) | Production limits (2 s) |
| --- | --- | --- |
| res-cross-join-global | 0.35 s | 0.70 s |
| res-self-join-inequality | 0.48 s | 0.88 s |
| res-cross-join-3way | 0.54 s | 0.91 s |
| res-like-cross-join | 0.75 s | completes in 0.78 s |
| res-sort-cross-join | 1.01 s | 2.01 s |

The sort case is the one the clock stops: with steps alone and a 1 s limit it ran 1.55 s before its budget ran out. The LIKE case needs between 84 and 168 million steps, so it is a bounded case only at the suite's 1 s limit. `test_wall_clock_limit_stops_a_slow_query_far_from_its_step_budget` checks the same split on a synthetic query that builds and scans a 100 kB string per pair of rows. With the wall clock on it is stopped at 1 s by the progress handler, and the worker survives. With steps alone and the same `timeout_s` it runs to completion past 1 s, because it uses only a small part of its budget.

The rest of this section is about steps-only limits (`wall_clock=False`).

Step counts are deterministic only if each run starts counting from zero. SQLite places a statement's progress checks relative to the steps that prepared statement has run before (`iPrior % nProgressOps` in `vdbe.c`), and Python's `sqlite3` module reuses prepared statements from its cache. The same BIRD query run four times on one connection was counted as 260,000, 270,000, 260,000 and 270,000 steps; with `cached_statements=0` it was 260,000 every time. The sandbox's connection disables the cache, and `test_repeating_a_query_does_not_shift_its_step_count` fails if it is turned back on.

Two tests show that steps-only outcomes do not depend on load: a query given half a check interval more than it needs finishes, and given half an interval less times out, on an idle worker and on one throttled with SIGSTOP/SIGCONT to a tenth of its speed (`test_step_budget_outcome_does_not_depend_on_load`), and in-process under GIL contention from busy threads (`test_step_budget_outcome_does_not_depend_on_contention`). In both, the slowed run takes more than twice the nominal `timeout_s` of wall time; the in-process test also checks that the same limits with `wall_clock` on do stop it.

The Python work `Sandbox.run` does for each row SQLite returns, converting it, is not timed either: it is bounded by `max_rows + 1` rows and by `max_result_bytes`, both counted. The per-row wall-clock check that used to sit in the fetch loop is gone.

Steps are not equally expensive. Measured with a step budget on BIRD databases (median of 3 runs, idle machine):

| Query shape (database) | Steps | Wall time | M steps/s |
| --- | --- | --- | --- |
| cross join count (formula_1) | 260,000 | 0.002 s | 154 |
| GROUP BY 180k rows (european_football_2) | 2,730,000 | 0.042 s | 65 |
| GROUP BY (codebase_community posts) | 1,700,000 | 0.056 s | 31 |
| ORDER BY long text, LIMIT 10 (posts) | 550,000 | 0.025 s | 22 |
| LIKE + join (card_games) | 3,460,000 | 0.180 s | 19 |
| ORDER BY numeric, 180k rows (european_football_2) | 1,830,000 | 0.103 s | 18 |
| indexed join (codebase_community) | 880,000 | 0.056 s | 16 |
| LIKE scan over post bodies | 360,000 | 0.076 s | 4.7 |
| ORDER BY long text, all rows (posts) | 820,000 | 0.188 s | 4.4 |
| COUNT(DISTINCT long text) (posts) | 550,000 | 1.078 s | 0.5 |
| per-row REPLACE building 9.75 MB, 200 rows (formula_1) | 0 | 1.165 s | 0 |

Work done inside single steps, such as comparing long strings during a sort or building a large string, does not move the counter. The last row is the extreme: 1.2 s without reaching the first check.

The parent kills a worker that has not answered after `kill_after(limits)` of wall time. With the wall clock on that is `timeout_s + 1 s`: the handler normally stops the query on time, and the extra second covers serialization and work hidden inside single steps, which the handler never gets to check. With steps alone it is only a backstop, `max(5 × timeout_s, timeout_s + 10 s)`: 50 s for the 10 s benchmark candidates, 150 s for 30 s gold SQL. On a kill the parent sends SIGKILL, reaps the process and raises `QueryTimeout`, and the next call starts a fresh worker. The test suite simulates a hung worker with SIGSTOP and checks the kill, the reaping and the respawn, and checks that a query stopped inside the worker keeps its worker.

What remains load-dependent with steps alone: a query is stopped by the kill rather than by its budget whenever it runs slower than the budget divided by the kill time on that run, 84 / 5 = 16.8 M steps/s for limits of 2.5 s or more. In the table that never happens to aggregations and cross joins. Indexed joins, LIKE with a join and ORDER BY sit at 16 to 22 M steps/s, near the line. Text-heavy scans, sorts and DISTINCT run far below it. For queries below the line the effective limit is the wall-clock kill at five times `timeout_s`, and their outcome can differ between runs if their idle running time is within the load slowdown of that threshold: e.g. between 25 and 50 s for a 10 s benchmark limit when load doubles running times. With a wall-clock limit, every query whose idle running time was between 5 and 10 s was in that position. A hung worker is the other remaining case. `test_work_hidden_inside_single_steps_is_stopped_by_the_kill` pins the per-row REPLACE query to the kill in both modes.

Timeouts are per call: `execute(sql, params, limits=dataclasses.replace(limits, timeout_s=30))` lets an evaluation give gold SQL 30 s while candidates on the same executor keep their own limit. The clock is the one field a call cannot change (see below).

### A fixed clock for benchmark candidates

Twelve BIRD Mini-Dev gold queries compute ages or durations from `'now'` or `CURRENT_DATE`, and so do the model's answers to them. A replay on another day therefore disagreed with the recorded run. `ExecutionLimits.clock` (`BENCHMARK_NOW`, 2026-10-16 12:00:00 UTC, for `QueryMode.BENCHMARK` in `pipeline/resources.py`; None, the real clock, for production and tenant requests) is sent to the worker when it starts. The worker calls `text2sql.sqlite_clock.pin_clock` on its connection before installing the authorizer. The pinned functions read the fixed time for every way SQLite reads the clock: a `'now'` argument, including one built at run time (`date('n' || 'ow')`), an omitted time value (`date()`, `strftime('%Y')`) and `CURRENT_DATE`/`CURRENT_TIME`/`CURRENT_TIMESTAMP`. `test_benchmark_limits_read_the_pinned_clock_however_it_is_asked` checks all of these, in-process and through a worker, and `test_production_limits_read_the_real_clock` checks that unpinned limits still get the system time. Pinning is unconditional rather than decided by looking at the SQL, because a pattern cannot see every way of reading the clock. The overrides cannot be removed cleanly from a connection, so the clock is fixed for the life of an executor, and per-call limits with a different clock raise `ValueError`.

The overrides keep the built-in names, so the authorizer sees the same `FUNCTION date`/`strftime`/... callbacks and still refuses `datetime`, `time` and `unixepoch`. The pinned connection is the ordinary connection, so the read-only URI, `query_only`, the length limits and the step budget apply unchanged (`test_pinned_connection_keeps_the_authorizer`, `..._step_budget_and_size_limits`). Each override forwards its arguments as bound parameters to SQLite's own function on a private in-memory connection, outside the step budget. A date-function call is still one step, so step counts do not change: a 92k-row `strftime` scan of BIRD's `posts` counted 550,000 steps either way. It took 0.165 s pinned instead of 0.032 s built in.

### Process model: persistent workers, respawned after a kill

Each `SandboxedExecutor` owns a pool of at most `max_workers` (default 2) worker processes for its database, started on first use. A worker is `python -P -m text2sql.execution.worker <fd>` connected by a socket pair; it opens the sandbox once and then serves one query at a time. A worker that died while idle is noticed at checkout and replaced without failing the query. A worker that dies during a query raises a plain `ExecutionError`; nothing is retried.

Measured per-query latency from the last benchmark run, median / p95 in milliseconds (20,000-row table; 2,000 runs per cell for the first three columns, 15 to 30 for the others). "New executor per query" is a worker start, the query and a clean shutdown, i.e. what a process-per-query design would cost with this code:

| Query | Plain sqlite3 | Sandbox in-process | Persistent worker | New executor per query | multiprocessing spawn per query | multiprocessing forkserver per query |
| --- | --- | --- | --- | --- | --- | --- |
| `SELECT 1` | 0.0007 / 0.0014 | 0.002 / 0.002 | 0.072 / 0.111 | 66.9 / 87.9 | 85.0 / 132 | 48.4 / 57.2 |
| GROUP BY over 20k rows | 3.71 / 4.60 | 3.51 / 4.16 | 2.88 / 5.35 | 67.4 / 81.3 | 68.8 / 101 | 46.5 / 59.4 |
| 1,000-row result | 0.59 / 1.12 | 0.58 / 0.67 | 2.44 / 3.45 | 65.2 / 69.2 | 62.4 / 68.9 | 35.4 / 44.3 |

The machine was shared with other jobs, so numbers move between runs: over three runs the persistent-worker round trip for `SELECT 1` ranged from 0.027 to 0.072 ms and the per-query-process variants from 32 to 85 ms, and the sub-millisecond differences between the first three columns of the GROUP BY row are noise. The ranking never changed. Starting a worker (new executor, first query, shutdown) took 47.5 to 63 ms median; respawning after a kill goes through the same code path, so it costs one start. The largest resident size of any worker or child process was 30 MB. Of the start-up, about 33 ms is imports, 23 ms of them `asyncio`, which the package `__init__` pulls in (`python -X importtime -c "import text2sql.execution.worker"`).

A process per query costs 35 to 85 ms each, about three orders of magnitude more than the round trip to a persistent worker; over 10,000 executions that is 6 to 14 minutes of pure overhead against about a second. A fresh process per query would also discard SQLite's page cache every time. The isolation it would buy is small: the connection cannot create temp objects, attach files or change pragmas, so the only state that survives between queries in a worker is the page cache, and every query on a worker uses the same database and policy. The persistent pool wins. The cost it adds is serialization: the 1,000-row result costs 1.2 to 1.9 ms more through the worker than in-process.

In the same run, 8 concurrent CPU-bound queries took 2,241 ms with one worker, 1,516 ms with two and 1,091 ms with four. The default of two is a compromise between that and one process per database per worker; callers that fan out many candidates against one database can raise `max_workers`.

### Wire format

Messages are JSON, with blobs as `{"b": "<base64>"}`, not pickle. The worker executes attacker-influenced SQL; if a SQLite memory-safety bug were ever exploited inside it, unpickling its replies would hand the attacker code execution in the parent, which holds the API key (the Python documentation: "It is possible to construct malicious pickle data which will execute arbitrary code during unpickling"). The parent validates every reply's shape and cell types and treats anything else as a worker failure. It also passes a length bound to `Connection.recv_bytes`, which raises `OSError` for a longer message without reading it; the bound is 12 JSON bytes per counted byte of `max_result_bytes` plus 12 per byte of the request, for error messages that quote the SQL (a hypothesis test checks that honest replies stay within it). On an oversized reply the worker is killed. A compromised worker can therefore at worst return wrong rows.

### Errors

`QueryTimeout` (with `timeout_s`), `AccessDenied` (with the authorizer `action` and `target`), and `QueryFailed` (SQLite's own message, e.g. `no such column: nosuch`, for the repair loop) all subclass `ExecutionError`, which is raised directly only when the worker itself fails. `ResultTooLarge` is a `QueryFailed`, so code that feeds failures back to the model handles it unchanged, while the safety guard can log it as layer 3 stopping a query. Its message is "result exceeds N bytes", "query ran out of memory" or SQLite's "string or blob too big". If the authorizer is somehow bypassed, the read-only connection still refuses writes with `SQLITE_READONLY`; that plain code is reported as `AccessDenied` with action `WRITE`, and a test removes the authorizer to check it. Extended read-only codes, such as `SQLITE_READONLY_ROLLBACK` from a hot journal, are infrastructure faults and surface as `QueryFailed`.

### Concurrency

`execute` is thread-safe: a bounded semaphore admits at most `max_workers` queries at a time, and further callers block. `execute_async` first waits on a per-event-loop `asyncio.Semaphore` of the same size, then runs `execute` through `asyncio.to_thread`, so the loop keeps running and queued calls do not each occupy a thread from the default pool. Cancelling an awaiting task does not stop a query already sent to a worker; it ends within its limits and the worker goes back to the pool.

## Consequences

- The pipeline can execute every candidate and the gold SQL through the same component at a cost close to plain SQLite, and the per-call limits keep one executor per database sufficient.
- Grammar-valid SQL can still be refused here: anything outside `DEFAULT_FUNCTIONS`, recursive CTEs, and in tenant mode any read of a column missing from `readable`. That is intended; a refusal is a safety event, not something to work around.
- Gold SQL that uses functions outside the allowlist needs an `AccessPolicy` with extra functions for that run; the executor does not widen the list itself.
- Values larger than 10 MB, stored or computed, and results over 10 MB fail with `ResultTooLarge` unless the caller raises `max_value_bytes` or `max_result_bytes`. The BIRD Mini-Dev gold results measured above stay at least 10 times below the result limit.
- Each executor costs up to `max_workers` processes of about 30 MB idle and, on Linux, at most their start-up data segment plus `max_memory_bytes` (256 MiB) each; callers should keep one executor per database and close it.

## Residual risks

- `EXPLAIN` and `EXPLAIN QUERY PLAN` of an otherwise allowed SELECT run, because the authorizer sees the same callbacks as for the SELECT. They reveal bytecode and index names, not data. The grammar and the validator do not admit them.
- Column-less scans of eponymous virtual tables pass (`SELECT count(*) FROM json_each('[1,2]')` counts the caller's own input). Their column reads stay denied, and the `pragma_*` functions are still stopped by their PRAGMA callback. Conversely, a CTE that shadows a hidden table's name is refused, a harmless false positive.
- On platforms other than Linux the worker has no memory cap, so only the byte limits apply and one very wide row can still take as much memory as its values add up to. On Linux SQLite's own structures are inside the cap; in this build (`PRAGMA compile_options` shows `TEMP_STORE=1`, page cache 2,000 KiB), transient indices for ORDER BY, GROUP BY, DISTINCT and compound selects move to temporary files once they outgrow the page cache, so large sorts cost temporary disk space for at most the time limit; this was read from the SQLite documentation, not load-tested.
- CPU time inside single steps, such as building multi-megabyte strings or sorting long text, is bounded only by the kill, so such a query can hold a worker and a core for `kill_after(limits)`: 3 s at the default 2 s wall-clock limit, 50 s for 10 s benchmark candidates, 150 s at 30 s. With steps alone the outcome of such queries can still depend on load near that threshold (see Time limits).
- Timing: `elapsed_s` is returned and timeouts are observable, so expensive queries leak cost information.
- Aggregates over readable columns can still be used for inference; scoping (layer 4) and the column policy decide what is readable, not this layer.
- The worker runs as the same OS user as the parent, with no seccomp or namespace isolation. Defence against file access rests on SQLite's file functions being absent from this build (`readfile` is "no such function"), on `load_extension` being denied by the authorizer, and on `ATTACH` and `VACUUM INTO` being denied by both the authorizer and the attach limit.
- Not tested with WAL-mode databases, which need a `-shm` file or a writable directory to be opened read-only.

## Sources

All read on 2026-10-16.

- SQLite, Compile-Time Authorization Callbacks: https://www.sqlite.org/c3ref/set_authorizer.html
- SQLite, Query Progress Callbacks: https://www.sqlite.org/c3ref/progress_handler.html
- SQLite 3.50.4 source, `src/vdbe.c` (progress-handler phase from the statement's prior step count, lines 849-857): https://raw.githubusercontent.com/sqlite/sqlite/version-3.50.4/src/vdbe.c
- SQLite, Run-Time Limit Categories (`SQLITE_LIMIT_LENGTH`, `SQLITE_LIMIT_ATTACHED`): https://www.sqlite.org/c3ref/c_limit_attached.html
- SQLite, URI filenames (`mode=ro`): https://www.sqlite.org/uri.html
- SQLite, `PRAGMA query_only`: https://www.sqlite.org/pragma.html#pragma_query_only
- SQLite, the WITH clause (recursive CTEs without the `RECURSIVE` keyword): https://www.sqlite.org/lang_with.html
- SQLite, Temporary Files Used By SQLite (transient indices, page cache spill): https://www.sqlite.org/tempfiles.html
- Linux `getrlimit(2)` man page (`RLIMIT_DATA` applies to `mmap(2)` since Linux 4.7): https://man7.org/linux/man-pages/man2/getrlimit.2.html
- Python 3.12 `multiprocessing` documentation (`Connection.recv_bytes(maxlength)`): https://docs.python.org/3.12/library/multiprocessing.html
- Python 3.12 `sqlite3` documentation (`set_authorizer`, `set_progress_handler`, `setlimit`, `sqlite_errorcode`): https://docs.python.org/3.12/library/sqlite3.html
- Python `pickle` security warning: https://docs.python.org/3/library/pickle.html
