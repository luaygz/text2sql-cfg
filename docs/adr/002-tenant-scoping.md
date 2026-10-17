# ADR-002: Tenant scoping by guarded derived tables

Status: Accepted
Date: 2026-10-16

## Context

In tenant mode the system answers questions over the synthetic SaaS database (ADR-004) for one
tenant, and optionally one user, at a time. The tenant id must never pass through the model:
the system injects it, and the model has no way to supply or choose its own. One option is to
rewrite the SQL with sqlglot to add `tenant_id = :tenant_id` to every scoped table reference;
the other is per-request temporary views. We compared the two before deciding.

The rewrite has to stay correct wherever a scoped table can appear: inner and outer joins,
self-joins, `IN`/`EXISTS`/scalar subqueries (correlated or not), CTEs, set operations and
aggregates. Outer joins are where the obvious implementation breaks. Appending
`T2.tenant_id = :tenant_id` to the WHERE clause of `accounts T1 LEFT JOIN deals T2 ON ...`
discards the NULL-extended rows, silently turning the outer join into an inner one. Moving the
predicate into the ON clause fixes the right side, but the same trick on the preserved side
(`... ON T2.account_id = T1.id AND T1.tenant_id = :tenant_id`) filters nothing: every tenant's
accounts come back, each with NULLs. Predicate placement therefore depends on join position,
and a mistake leaks.

The scoping layer also has to fit the read-only executor (ADR-007), which opens SQLite with
`mode=ro`, sets `PRAGMA query_only = ON`, and installs an authorizer that allows only reads of
listed columns and calls to allowlisted functions. And it must be checkable on its own: safety
layer 4 re-parses the final SQL and proves that every scoped reference carries its filter.

## Spike

Both approaches were implemented against a throwaway fixture: 5 tenants, 250 users, 10,000
accounts and 50,000 deals, with indexes on `tenant_id`. The workload was 8 query shapes (an
aggregate, a GROUP BY, an inner join, a LEFT JOIN with an extra ON condition, an `IN`
subquery, a join with GROUP BY and ORDER BY, a CTE joined back to a base table, and a UNION),
each run for 3 identities (two tenants and one user-mode identity). Both approaches returned
identical result multisets for all 24 pairs.

Approach B, per-request temporary views (`CREATE TEMP VIEW deals AS SELECT <visible columns>
FROM main.deals WHERE tenant_id = 7`) shadowing the base tables, showed four problems:

1. On a connection with `query_only = ON`, `CREATE TEMP VIEW` fails with "attempt to write a
   readonly database". Under a read-only authorizer it fails with "not authorized". The
   executor would have to run privileged DDL for each request before locking the connection
   down, and could never reuse a connection across tenants without first dropping and
   re-checking the views.
2. Views cannot hold bound parameters ("parameters are not allowed in views"), so the tenant id
   has to be formatted into DDL text. That is safe for an integer, but it breaks the rule that
   identities reach SQLite only as bound parameters.
3. The protection rests on SQLite searching the temp schema before main for unqualified names.
   `SELECT COUNT(*) FROM main.deals` bypassed the view in the spike: 50,000 rows instead of
   10,000. Only the validator's ban on schema qualifiers stood between the model and the base
   table. `sqlite_temp_master` also exposes the view text, tenant id included.
4. Nothing in the query text shows that it is scoped; correctness is a property of connection
   state. Layer 4 could not be a check on the SQL.

Approach A, as finally implemented, does not add predicates to the model's WHERE or ON clauses.
It replaces each reference to a scoped table with a guarded derived table:

```sql
-- model SQL
SELECT T1.name, T2.name FROM accounts AS T1 LEFT JOIN deals AS T2 ON T2.account_id = T1.account_id LIMIT 50
-- executed SQL (tenant mode)
SELECT T1.name, T2.name
FROM (SELECT "account_id", "owner_user_id", "name", ... FROM "accounts"
      WHERE "accounts"."tenant_id" = :tenant_id) AS T1
LEFT JOIN (SELECT "deal_id", "owner_user_id", "account_id", "name", ... FROM "deals"
           WHERE "deals"."tenant_id" = :tenant_id) AS T2
  ON T2.account_id = T1.account_id LIMIT 50
```

Because the guard stands in for the table itself, the filter holds wherever the table appears,
and join semantics are those of a database that holds only the caller's rows. Approach B gives
the same semantics, but through connection state instead of query text.

Three details came out of the spike.

- Guards project the visible columns explicitly. The authorizer checks every column a statement
  touches, and SQLite expands `SELECT *` inside a subquery even when the outer query reads only
  one column: with a `SELECT *` guard, `SELECT u.name FROM (SELECT * FROM users WHERE ...) u`
  was denied for reading `users.password_hash`. A useful side effect is that `tenant_id` is
  unreachable outside the guard. Even with the validator bypassed,
  `SELECT title FROM deals WHERE tenant_id = 2 OR 1 = 1` fails with "no such column".
- The guard is spliced into the original text at the table identifier's source span, which
  sqlglot records. Regenerating SQL from the AST would change what runs; for example, sqlglot's
  SQLite generator prints `SUBSTR` as `SUBSTRING`, which the executor's function allowlist does
  not include. With splicing, everything outside the replaced identifiers is byte-for-byte what
  the validator accepted. Guard internals use canonical double-quoted names from the schema, not
  the model's spelling of the table, so odd spellings such as SQLite's single-quoted identifiers
  (`FROM 'deals'`) do not leak into the guard.
- SQLite flattens the guards. `EXPLAIN QUERY PLAN` for the join shapes showed
  `SEARCH deals USING INDEX ix_deals_t (tenant_id=?)`, not a scan of a materialized subquery.

Latency over 720 runs (30 repetitions of the 24 pairs; i7-1255U, Python 3.12.12, SQLite
3.50.4), with connection opening excluded for both approaches:

| | per-request setup p50 / p95 | execution p50 / p95 |
| --- | --- | --- |
| A: rewrite + proof (two sqlglot parses, splice) | 1.11 / 1.88 ms | 0.88 / 3.74 ms |
| B: three `CREATE TEMP VIEW` statements | 0.12 / 0.20 ms | 0.70 / 3.43 ms |

A costs about a millisecond more per query. Next to a model call that takes seconds, that does
not matter. These numbers come from a one-off spike script that was not kept; they show order
of magnitude only.

| Criterion | A: guarded derived tables | B: temporary views |
| --- | --- | --- |
| Correctness | Same semantics as B; holds in every position by construction | Correct while every name resolves through temp; `main.` bypasses it |
| Proof | Static check of the final SQL (`verify_scope`) | None in the SQL; depends on connection state |
| Executor | Unchanged: one statement plus bound params; needs `tenant_id` readable | Needs privileged per-request DDL before `query_only` and the authorizer |
| Parameters | Bound (`:tenant_id`, `:user_id`) | Integer formatted into DDL |
| Testability | Pure function from string to string; DB needed only for semantic checks | Needs a live connection per test |
| Latency | +1 ms per query | +0.1 ms per query |

## Decision

Use approach A, as guarded derived tables spliced into the model's text, followed by an
independent proof.

- `text2sql.safety.apply_scope(sql, policy, ctx, *, schema)` guards every reference to a table in
  `ScopePolicy.tenant_tables`. In user mode (`ctx.user_id` set), references to
  `owner_tables` also get `owner_user_id = :user_id`. `schema` is the full database schema; guards
  project every column the policy does not hide. The function returns
  `ScopedQuery(sql, params)`, where `params` holds exactly the parameters the SQL uses, taken
  from `ScopeContext` (whose fields must be `int`; `bool` and strings raise `TypeError`).
  `apply_scope` calls `verify_scope` on its own output before returning.
- `text2sql.safety.verify_scope(sql, policy, *, user_mode)` re-parses the SQL and fails with
  `ScopeViolation` unless:
  - every table node naming a scoped table is the bare, sole FROM source of a SELECT that
    projects plain, non-hidden columns and whose WHERE is exactly `<table>.tenant_id =
    :tenant_id`, plus `<table>.owner_user_id = :user_id` for owner tables in user mode; no
    literals, ORs, extra conjuncts or parentheses are accepted;
  - no CTE is named like a scoped table;
  - no bind parameter appears outside a guard;
  - SQLite's `expr IN table` form, which reads a table without a FROM clause, does not appear.
- The model never sees the tenant column. `ScopePolicy.visible_schema` drops it, along with
  `hidden_columns` such as `users.password_hash` and `tenants.api_key`, and the grammar and prompt
  are built from that schema. The validator rejects the tenant column (`hidden_column`) and any
  bind parameter (`placeholder`), so the model cannot write `:tenant_id` either.
- The owner column stays visible. It is an ordinary foreign key to `users` that questions like
  "open deals per account manager" need. In user mode the guard already limits owner tables to
  the caller's rows, so naming the column can only narrow a result.
- `SELECT *` is rejected in tenant mode, both by the validator and by the grammar. The guards
  would make `*` expand to visible columns of scoped tables, but global tables are not wrapped,
  and listing columns keeps results stable when the schema grows.
- The executor needs the tenant column readable for scoped queries:
  `AccessPolicy(readable=policy.readable_columns(full_schema))` gives the visible columns plus the
  tenant column, and nothing in `hidden_columns`.
- Approach B survives as the test oracle. The scoping tests compare each scoped result with the
  result of the unmodified SQL on a database that contains only the identity's rows, which is
  what B's views emulate.

## Consequences

- Scoping is a deterministic, checkable property of each query, and both layer-4 checks are pure
  functions. The tests assert result equality with the identity oracle for 25 hand-written
  cross-tenant attacks across 6 identities and for 400 generated queries per run (hypothesis),
  on plain read-only `sqlite3` connections; the hand-written attacks run again through
  `SandboxedExecutor` under its authorizer. A canary test on the real SaaS database, also through
  the executor, checks every tenant's canary tokens.
- The executor stays generic: it receives one statement and its bound parameters.
- `apply_scope` needs the full schema to build projections. A schema change changes the guard
  text, but there is no per-connection state that could go stale.
- Executed SQL is longer than the model's SQL. Logs should record both.
- The splice relies on sqlglot's identifier source spans. If a span were wrong, the result would
  not parse or would fail the proof; the failure is closed either way.
- Rows of a scoped table that SQLite reads without sqlglot seeing a table reference would not be
  guarded. `expr IN table` is the one such form found; the validator and `verify_scope` both
  reject it. Views over scoped tables would be another: the SaaS database has none (checked on
  `data/saas/crm.sqlite`), and `introspect_sqlite` lists only tables, so the validator rejects view
  names as unknown. If views are ever added, they must be listed in the policy as scoped or
  removed from the schema.
- Whether parsing and execution agree depends on sqlglot and SQLite reading the same text the
  same way. The validator rejects the known differentials (comments, non-ASCII outside literals,
  `IN table`, `$name` parameters), and the executor's authorizer does not depend on sqlglot at
  all.

## Sources

All accessed 2026-10-16.

- SQLite, Database Object Name Resolution (temp is searched before main):
  https://www.sqlite.org/lang_naming.html
- SQLite, Compile-Time Authorization Callbacks (column reads checked at prepare time):
  https://www.sqlite.org/c3ref/set_authorizer.html
- SQLite, PRAGMA query_only: https://www.sqlite.org/pragma.html#pragma_query_only
- SQLite, SQL Language Expressions, section 8 (the right-hand side of IN may be a table name,
  read as `(SELECT * FROM name)`) and section 4 (`?NNN`, `:AAAA`, `@AAAA`, `$AAAA` parameters):
  https://www.sqlite.org/lang_expr.html
- SQLite, SQL Keywords (single-quoted names accepted as identifiers where a string literal is not
  allowed): https://www.sqlite.org/lang_keywords.html
- SQLite, The Query Optimizer Overview, section 11 (subquery flattening):
  https://www.sqlite.org/optoverview.html
- sqlglot 30.23.0 source, `sqlglot/optimizer/scope.py`, read from the installed package (no URL).
- Observed in this run, not taken from documentation: the "parameters are not allowed in views"
  and "attempt to write a readonly database" errors, the `main.` bypass, the authorizer denial of
  `SELECT *` guards, `SUBSTR` printed as `SUBSTRING`, and the query plans above.
