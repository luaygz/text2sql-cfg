# ADR-005: Grammar design: one canonical SQLite SELECT per schema, sized for the API budget

Status: accepted
Date: 2026-10-16

## Context

Every SQL string the system executes comes out of the `sql_query` custom tool, whose input is constrained by a Lark grammar built per request from the schema (`text2sql.grammar.build_grammar`). The grammar is safety layer 1: it should make DDL, DML, second statements, comments, non-allowlisted functions and identifiers outside the schema impossible to emit. It also has to express the gold SQL of the benchmark (the target is at least 95% coverage of dev gold SQL after normalization), validate offline with `lark` and `llguidance`, and be accepted by the API.

Two facts from ADR-001 shaped almost everything below. The API runs the grammar through LLGuidance, whose lexer is greedy and does not backtrack. And the API rejects grammars above a fixed compilation budget (`Invalid lark grammar. regex construction fuel exhausted`) that the local `llguidance` 1.9.1 package does not reproduce, so the budget had to be measured against the live API.

## Decision

### Shape

The grammar is 13 rules. A query is an optional `WITH` list (CTE names `cte1`..`cte5`), one or more `SELECT` cores joined by `UNION`, `UNION ALL`, `INTERSECT` or `EXCEPT`, an optional `ORDER BY` and a `LIMIT`. A core is `SELECT [DISTINCT] items [FROM source (JOIN source [ON expr])*] [WHERE expr] [GROUP BY items] [HAVING expr]`, where `JOIN` is plain, `INNER`, `LEFT [OUTER]` or `CROSS`. Sources are schema tables, CTE names or parenthesised subqueries, aliased only as `T1`..`T9`. Subqueries appear in `FROM`, `WHERE` and the select list through one `paren` rule, which also serves `IN (...)` lists and `EXISTS(...)`.

Expressions are flat: `term (OPERATOR term)*`, where one `OPERATOR` terminal holds `AND`, `OR`, comparisons, arithmetic (`+ - * / %`), `||`, `[NOT] LIKE` and `[NOT] BETWEEN`. A term is `NOT`/unary minus prefixes, a primary, and optionally `IS [NOT] NULL` or `[NOT] IN (...)`. Primaries are column references, numbers, strings, constants, parenthesised expressions or subqueries, `EXISTS(...)`, function calls, `CAST(x AS INTEGER|REAL|TEXT|NUMERIC)` and both forms of `CASE`. One `items` rule (`expr [AS alias | ASC | DESC]`, comma separated) serves select lists, `GROUP BY`, `ORDER BY`, `IN` lists and call arguments.

Functions are exactly the allowlist: `COUNT SUM AVG MIN MAX ROUND ABS COALESCE IIF NULLIF LENGTH UPPER LOWER TRIM SUBSTR INSTR REPLACE STRFTIME DATE JULIANDAY`, plus `CAST` and `CASE`. No scalar function was added. The constants `NULL`, `TRUE`, `FALSE`, `CURRENT_DATE`, `CURRENT_TIME` and `CURRENT_TIMESTAMP` are allowed; 18 of the 998 Mini-Dev gold queries (BIRD and Arcwise together) use `CURRENT_TIMESTAMP`, and the executor allowlists the three `current_*` functions SQLite reports for them. Window functions, `GROUP_CONCAT`, `DATETIME`, `GLOB`, `ESCAPE`, `USING`, `NATURAL`, `RIGHT`/`FULL` joins, `NULLS FIRST/LAST` and `WITH RECURSIVE` are not in the grammar.

The flat expression grammar is a deliberate superset: `x BETWEEN 1`, `ORDER BY a AS c1` or `ROUND(*)` parse but SQLite rejects them when preparing the statement, which sends the candidate to the repair loop. Nothing in the superset adds a statement, a comment, a function or an identifier. The precedence tower it replaced cost about 30 columns' worth of the API budget (below).

Modes: `BENCHMARK` makes the top-level `LIMIT` optional; `PRODUCTION` and `TENANT` require it. In every mode `LIMIT` is a regex for the integers 1..`max_rows` without leading zeros, and `OFFSET` takes at most six digits; `LIMIT` inside a subquery stays optional and does not satisfy the top-level requirement. `TENANT` also drops `*` and `T1.*` projections, because a star expands into columns the tenant schema hides (`COUNT(*)` stays). No mode uses parameter placeholders, because tenant scoping is applied by rewriting the parsed query (ADR-002), not by the model.

`allow_abstain` adds `start: query | abstain` with `abstain: "ABSTAIN: " REASON`, where `REASON` is 1 to 300 non-control characters. No SQL statement starts with `ABSTAIN:`, and `SqlGrammar.parse` returns `GrammarOutput(kind="abstain", text=<reason>)`.

### Whitespace and spelling

There is exactly one spelling of each query: upper-case keywords, one space between tokens, `, ` between list items, no space after `(` or before `)`, no newlines or tabs inside the query. The input may end with one newline (see "The trailing newline" below); `SqlGrammar.parse` drops it. The spaces are part of the keyword lexemes (`" FROM "`, `" AND "`), so no keyword lexeme can overlap an identifier, and the format is what sqlglot prints by default, which keeps gold normalization mechanical. Models adapt to the single-space rule without trouble because the decoder masks every other choice, and `SqlGrammar.description` (used as the tool description) spells the conventions out.

### Identifiers and the exact guarantee

Two regex terminals enumerate identifiers. `SOURCE` holds the schema's tables plus `cte1`..`cte5`; `COLUMN` holds every column name of every table plus the computed-column aliases `c1`..`c9`. Names are spelled by `grammar.conventions.sql_identifier`: bare when they match `[A-Za-z_][A-Za-z0-9_]*` and are neither one of SQLite's 147 keywords nor an all-caps word the grammar uses (a column called `DATE` would otherwise lex as a function call), and in backticks otherwise, as BIRD gold SQL does. `catalog.schema.quote_identifier` delegates to it, so the schema text in prompts and the grammar match byte for byte. Both terminals are prefix-factored (`(?:ab(?:c|d)|x)`), which is what makes them affordable (below).

Qualified references go only through `T1.`..`T9.` or `cte1.`..`cte5.`; `frpm.CDSCode` is not expressible and normalization rewrites it to an alias. A column alias (`AS ...`) must itself be a `COLUMN` member, so it is either a schema column name or `c1`..`c9`, and a free-form alias like `AS total` cannot be written. That is what keeps alias references (`ORDER BY c1`, `T3.c1` on a derived table, `SELECT c1 FROM cte1`) inside the enumeration.

The guarantee, relative to the schema the grammar was built from (full or linked): every name in table position is one of its tables or a CTE name, and every name in column position is a column name that exists in at least one of its tables, or one of `c1`..`c9`. A hallucinated column or table cannot be emitted. Builds fail with `ValueError` if a table is named like an alias (`t1`, `cte2`, any case) or a column is exactly `T1`..`T9` or `cte1`..`cte5`.

Residual gaps, closed by layers 2 to 4:

- The guarantee is at the level of names, not of `(table, column)` pairs. `T1.amount` proves that some table has `amount`, not that `T1`'s table does. If a column is hidden in one table (tenant mode removes `tenant_id` and owner columns from the schema before building) but visible in another, `T1.tenant_id` stays expressible against the table where it is hidden. The AST validator resolves every column against its table and the allowlist (ADR-002).
- `c1`..`c9` are accepted anywhere a column is. If a real table had a hidden column with one of those names, the grammar could name it. The builder cannot see hidden columns; the validator resolves them.
- In `BENCHMARK` and `PRODUCTION` mode, `SELECT *` expands to every column of a table at execution time.
- The grammar does not check that an alias is bound, that a CTE exists, or types. SQLite reports those at prepare time.

### Literals

Numbers are `[0-9]{1,18}(\.[0-9]{0,18})?([eE][+-]?[0-9]{1,3})?`; negative numbers use the unary minus. Strings use single quotes, `''` as the only escape, no backslash, no `;`, no control characters, at most 255 characters (the longest gold literal is 85). A string that starts with one of `" # ( ) * + - . / : = ? [` is either that character alone or the character followed by a digit (`'-1 day'`, `'+5'`); the reason is the next section but one.

An earlier version excluded `--` and `/*` anywhere. Inside a string literal they are now allowed. A regex that excludes them (a small DFA over `-`, `/` and the other characters) was measured: it cost as much of the API budget as about 33 sixteen-character column names, and with it the first template fit no columns at all. Inside a literal both sequences are data: the grammar's lexer, SQLite's tokenizer and sqlglot all agree on where a literal ends, because there are no backslash escapes, and a comment outside a literal cannot be produced. The validator detects comments on tokens, not raw text, so `'a--b'` passes it.

### One-character punctuation literals and the hosted decoder

Runaway tool inputs showed up on three Mini-Dev questions whose gold compares with a one-character literal: Q218 `label = '+'`, Q197 `bond_type = '-'`, Q416 `power = '*'`. gpt-6.1-sol wrote `'+ за' AND T1.label = '+ final' AND ... '+ done'`, `'*bogus'`, `'*$'`, `'-攈'` and so on until the output limit, in every attempt and every strategy: it could never close the quote right after the single character, while it closed after two characters (`'*+'`, `'*$'`) or after a letter. Locally, lark and llguidance with the `o200k_base` tokenizer both accept `= '+'`, and the llguidance mask after `= '+` includes the closing quote.

The probes (`docs/adr/data/literal_trap_probes.json`, 90 calls, about $0.04) narrowed it down:

- It is not our grammar's follow sets or whitespace. A two-line grammar `start: "x = " STRING` reproduces it on gpt-6-luna (`x = '+ '`, `x = '*’'`), as do variants with the space optional, with the space inside the string lexeme, with the closing quote as a separate lexeme, with or without the `''` escape, with bounds `{0,8}` or `*`, and with the literal at the start of the input. One-letter literals (`'f'`) close fine in all of them.
- In `o200k_base`, ` '+'`, ` '-'`, ` '*'`, ` ':'`, ` '.'`, ` '='`, ` '#'` and nine more are single tokens that include the preceding space. Every failing literal is one whose natural tokenization is such a token (or `+')` in `IN ('+')`); every literal that closed has its closing quote in a token of its own or in a token like `+'` that does not reach back to the opening quote. Our reading, unverified because the server is not observable: the hosted decoder does not offer the whole-literal token, the model falls back to ` '+` and then, being off its usual tokenization, almost never picks the lone closing quote.
- When the closing quote is the only byte the grammar allows after `'+` (a test regex `'[+*a-z]'`), the close always happens.

So the fix makes the close nearly forced: after one of the characters above, only the closing quote or a digit may follow. With the new regex gpt-6.1-sol answered Q218, Q197 and Q416 correctly in 6 of 6 attempts, and in 4 of 4 more with the tool description's new sentence removed, so the grammar change alone does it. Before the change it failed 2 of 2 on Q218 with the same request shape; a description-only workaround (`IN ('+')`) fixed Q197 but not Q218.

The cost is expressiveness of single literals, not of values. In the Mini-Dev databases 24 text columns hold values that start with one of these characters followed by a non-digit (`'(none)'` in `card_games.cards.originalType`, `'*+1'` and `'*²'` in `toughness`, card names in double quotes, post titles in parentheses, long text fields). Such a value is written as a concatenation, `('(' || 'none)')`, which the tool description tells the model, and `normalize_sql` rewrites gold literals the same way. No gold query in Mini-Dev or Arcwise-Plat-SQL needs it. Lone `'%'` and `'_'` keep the trap, because `%` and `_` start LIKE patterns and strftime formats (`'%Y'` appears 145 times in gold), as does lone `','` (`', '` is a common separator). The set is tied to `o200k_base`; a different API tokenizer would need a new probe.

### The trailing newline

The grammar-vs-JSON ablation on the 350 dev questions (`docs/research/grammar-vs-json.md`: grammar 72.3%, JSON 74.3%, every JSON query inside the grammar's language) traced the whole gap to seven decoding failures of gpt-6.1-sol at medium effort. Five were string literals ending in punctuation that did not close cleanly: `'#'` became `'#159'`, `'*'` became `'*9641B9D8-…'`, `'1:54%'` became `'1:54%ʼ'`, `'2010-02-22%'` became `'2010-02-22%け'`, and `'...doing?'` ran away to the output limit. Two were queries that would not stop where the model's own query ended (Q201 ran to the limit with `OR ROUND(ROUND(...`, Q760 added ` NOT IN (SELECT 1) = 0 LIMIT 1 OFFSET 00787`). In 13 questions the grammar run's input was the JSON query plus extra text, never the reverse. The fix in the previous section had left a way out (the digit after `'#`) and did not cover endings like `%'` or `?'`.

Every one of the garbled literals was the last token of the query. Over the 350 JSON queries, 6 of the 22 punctuation-final literals at the end of the query were mangled in the grammar run, 0 of the 37 elsewhere, and 0 of the 141 letter- or digit-final literals at the end. That pointed at how the input ends rather than at the literal. The probes (`docs/adr/data/literal_end_probes.json`, gpt-6.1-sol unless noted):

- The copy task "call sql_query with exactly this input" reproduces it at effort low with the current grammar: `x = '#'` 2 of 3 correct, `'*'` 1 of 3, `'...doing?'` 0 of 3, `'ratio:'` 0 of 3, `'Smith,'` 0 of 3, `'2010-02-22%'` 2 of 3 (gpt-6-luna gets all of these right). Dropping the `''` escape does not help (0 of 6 on `?`).
- With one optional `"\n"` after the query, the same 18 copies were all correct, and all 18 ended with a newline. On the real Q760 and Q253 requests the model ended with a newline in 6 of 6 calls.
- In `o200k_base` the natural last tokens of such queries are `%'\n`, `'\n`, `)'\n`, `.'\n`; after `180` it is `\n` alone. Our reading, not verifiable on the server: the model ends a tool input with a newline, the grammar forbade it, and the masked ending sent the model off its usual path, which hurt most where the closing quote would merge with the newline after a punctuation character, and occasionally made it keep writing.

So the grammar now allows one trailing newline (`start: (query | abstain) "\n"?`), and `SqlGrammar.parse` removes it, so nothing downstream sees it. No other line break is accepted. On the exact best-preset requests of the seven questions (rebuilt from the run's cache, `direct_full`, medium effort, `max_output_tokens` 600 for new samples), the old grammar had a garbled literal, a tail or a runaway in 10 of 29 samples (the run's own sample plus three more each, four more for Q760) and 17 correct answers; with the newline 0 of 21 (three samples each) and 19 correct, every input ending in a newline. The two misses are Q861 picking `qualifying.number`, a reading error also seen before the change.

An alternative was measured and not kept: forcing the close after a leading punctuation character (no digit), after `?`, and after a `%` that follows a letter or digit, with longer values split into concatenations. It also gave 0 artifacts in 36 samples over the same nine questions (Q197 and Q584 included), but it restricts values (`'-1 day'`, `'50% off'` and any `?` inside a title need `||`), needs a prompt rule, and does not address queries that run on. The newline change has none of these costs. The first-character rule from the previous section stays: it was also measured only on literals at the end of the query, so it is probably the same failure, but removing it has not been tested.

### lark and llguidance differences

LLGuidance's lexer is greedy and does not backtrack. Measured locally with a byte-level vocabulary: with lexemes `" IS "` and `" IS NOT "` allowed at the same point, `x IS NULL` is rejected, because after `" IS "` the `N` extends `" IS NOT "`, which then fails on `U`. lark accepts the same string. The builder therefore keeps one rule: no lexeme may be a proper prefix of another lexeme allowed at the same position when what follows the shorter one can begin with the longer one's next byte. `" IS NULL"`/`" IS NOT NULL"` are one regex, `UNION`/`UNION ALL` are one regex followed by a space, `COUNT(` takes `*` as a separate token, and so on.

lark's LALR front end has the opposite problem. Its lexer tries terminals in a fixed order (by maximum width) and takes the first match rather than the longest, so `NULLIF(` lexed as the constant `NULL` followed by garbage. `SqlGrammar.parse` therefore uses lark's Earley parser with the dynamic lexer, which accepts exactly the grammar's language. Any string llguidance can produce is in that language, so the local re-parse never rejects a valid tool call. Earley costs 12 ms per gold query on average and 90 ms at most.

`validate_grammar_offline` still builds the LALR(1) table, in strict mode, and fails on any shift/reduce or reduce/reduce conflict; a grammar that passes is unambiguous. Lark's own `strict=True` additionally checks regex collisions through `interegular`, which took over a minute on the first string regex, so the table is analysed directly with `LALR_Analyzer`. The tests also parse the whole positive corpus with Earley in `ambiguity="explicit"` mode and find no ambiguous node. The same function asks llguidance to compile the grammar and fails on any error or warning.

`GuidanceMatcher` replays strings byte by byte through an `LLMatcher` with a 257-token byte vocabulary. A rejected token leaves an `LLMatcher` in a permanent error state that `reset()` does not clear, so it checks with `validate_tokens` first. Over the test corpus and the 998 normalized Mini-Dev gold queries, lark and llguidance agree on every string.

### The API grammar budget

All probes went through `LLMClient.grammar_accepted` (gpt-6-luna, reasoning effort none, 16 output tokens, flex), which caches verdicts by grammar fingerprint: 345 probes, 167 accepted and billed, 178 rejected and not billed, $0.016 in total. Before the client existed, 11 raw SDK probes sent the first grammar for each Mini-Dev database; all were rejected, also unbilled. Raw results, the synthetic grammar templates and thresholds are in `docs/adr/data/grammar_budget_probes.json`.

The first template (a precedence tower of 30-odd rules, 32 literal lexemes, 23 regex terminals, string regex excluding `--` and `/*`) was rejected for every Mini-Dev database, including `toxicology` with 7 columns. Binary searches on synthetic grammars, each varying one feature against a column list of 16-character names, showed what the budget counts:

- Each symbol written in a rule body costs about as much as 18 to 24 characters of a regex terminal. 55 extra references to one existing literal cost 52 columns' worth; the lexeme inventory of the first template used once in a single flat rule cost about 130, while the same lexemes spread over the real rules cost about 250.
- Inside regex terminals the cost follows the regex size: about one unit per literal character or character class and about four per `|` branch. A bounded repetition costs no more than an unbounded one (`{0,255}` and `*` gave the same limit).
- It does not depend on lexemes sharing first bytes, nor on how many contexts a terminal appears in beyond the symbols those contexts add.
- Prefix-factoring the identifier alternation helps a lot: 288 flat names fit in the minimal grammar against 1,429 factored ones. On real schemas factoring cuts `european_football_2`'s 185 column names from 2,167 regex atoms to 894.

The resulting template (flat expressions, merged operators, one `items` and one `paren` rule, factored identifiers, no `NULLS` ordering) has 86 rule symbols (87 with the trailing newline). It accepts 215 random 16-letter column names (rejects 216), 376 of 8 letters and 123 of 30 letters. Every full-schema Mini-Dev grammar and the SaaS tenant grammar with abstain was accepted, before and again after the string-literal and trailing-newline changes below:

| Grammar | Chars | Regex atoms | Est. load | API |
| --- | --- | --- | --- | --- |
| european_football_2 (7 tables, 185 columns) | 3,352 | 1,275 | 0.64 | accepted |
| card_games | 3,016 | 1,126 | 0.57 | accepted |
| california_schools | 2,936 | 1,049 | 0.56 | accepted |
| SaaS crm, tenant mode, abstain, max_rows 200 | 3,062 | 1,134 | 0.58 | accepted |
| toxicology (smallest) | 2,011 | 396 | 0.41 | accepted |

The other six databases fall between these (`reports/grammar_coverage_dev.md` lists all of them). For the largest Mini-Dev schema, `european_football_2`, the benchmark-mode grammar is 3,352 characters with 13 rule definitions (119 productions after lark's EBNF expansion), 44 terminals (24 literals, 20 regexes), 1,275 regex atoms, 235 regex branches and 87 rule symbols.

`GrammarSize.api_load` estimates the share of the budget used: `(regex atoms + 4.14 x regex branches + 24 x rule symbols) / 6748`. It was fitted on this template's three thresholds, which it reproduces to within 0.1%. It is less accurate for other shapes: on eleven of the synthetic test grammars the measured limit fell between 0.77 and 0.93 of the estimate, and on a deeply factored alternation at 1.56. `fits_api_budget` uses 0.85 as the cutoff, leaving room for real names that differ from the random ones it was fitted on. When a grammar does not fit, `build_grammar` logs `grammar_exceeds_api_budget` with a hint to fall back to the linked-schema grammar. `LLMClient.grammar_accepted` stays the ground truth, and a rejected grammar is remembered by fingerprint so it is never sent twice.

### Normalization of gold SQL

`normalize_sql(sql, schema=None)` parses with sqlglot 30.23 (dialect `sqlite`) and prints in the grammar's spelling. sqlglot's own SQLite printer could not be used as is: it maps `CAST(x AS NUMERIC)` and `DECIMAL` to `REAL` and prints `CAST(x AS DATE)` as `DATE(x)`, both of which change results, because SQLite decides a CAST by the affinity of the type name (`CAST('2020-01-05' AS DATE)` is the number 2020). The printer subclass casts to the affinity name instead (`INTEGER`, `TEXT`, `REAL`, `NUMERIC`, per SQLite's rules), writes `SUBSTR` rather than `SUBSTRING`, and quotes with backticks.

Rewrites, all meant to keep the result: CTEs become `cte1`..; every source gets a `Tn` alias by the name it is visible under (existing `Tn` aliases keep their number; one new name per old name keeps every qualifier bound to the same source in every scope, so no scope analysis is needed); qualifiers follow. With a schema, identifier case and quoting follow the schema, select-list aliases that are not schema column names become `c1`..`c9`, and a double-quoted name that resolves to nothing becomes the string literal SQLite would have read it as. Without a schema, column aliases and identifier case are left alone. Executing each gold query and its normalized form on the Mini-Dev databases gave identical row multisets for all 994 gold queries that finish within 30 seconds; the gold queries of questions 518 and 701 do not finish within 30 seconds in either gold set.

### Coverage

`uv run --frozen python -m text2sql.grammar.coverage --dataset bird --split dev --check-results` (and `--split minidev` for all 500) builds the full-schema grammar per database in benchmark mode, normalizes each gold query, parses it with lark and llguidance and writes `reports/grammar_coverage_<split>.{md,json}`.

| Gold SQL | Dev split (350) | All Mini-Dev (500) |
| --- | --- | --- |
| BIRD Mini-Dev | 346, 98.9% | 494, 98.8% |
| Arcwise-Plat-SQL (498 relabelled questions) | 345 of 349, 98.9% | 492 of 498, 98.8% |

Remaining failures over all 500: window functions (`RANK`, `DENSE_RANK`) in 5 BIRD and 4 Arcwise queries, `DATETIME()` in 1 BIRD query, `GROUP_CONCAT` and `NULLS LAST` in 1 Arcwise query each. All are outside the allowlist; window functions would also need the validator and executor allowlists to change, and with 9 of 998 queries they are not worth the budget. The grammar was shaped while looking at all 500 gold queries, test split included. No model output was involved, but that makes grammar coverage on the test split not a held-out number, and the grammar could raise test EX if it admits a construct only test gold needed. That effect was not measured; it is probably small, because on dev the JSON run without the grammar scored the same as the grammar run and all 350 JSON queries parse under the grammar.

## Consequences

- Full-schema grammars fit for every Mini-Dev database, so the full-schema strategy is available everywhere. This contradicts the expectation in ADR-001 that databases with a couple of hundred columns would not fit; it held for the first template, not for this one. Larger schemas still need the linked-schema grammar: the measured limit is 215 random 16-letter column names, more when names share prefixes, fewer when they are long.
- The model must use `T1`..`T9`, `c1`..`c9` and `cte1`..`cte5`, single spaces and upper-case keywords. Prompts should show the schema with `sql_identifier` spellings and pass `SqlGrammar.description` as the tool description.
- Some syntactically invalid SQL is grammar-valid and fails at execution; the repair loop handles it.
- String literals may contain `--` and `/*`; anything that re-tokenizes SQL must treat literals as opaque.
- A literal such as `'(none)'` reaches the database as `('(' || 'none)')`. The validator and executor see an ordinary concatenation.
- Tool inputs may end with a newline; consumers must use `GrammarOutput.text` (or `SqlGrammar.parse`), not the raw input, as the SQL.
- Layers 2 to 4 remain necessary for per-table column resolution, hidden columns, star expansion in non-tenant modes, and alias binding.
- The grammar adds input tokens to every uncached call: the 14 final full-schema probes averaged about 1,400 input tokens each, tool description and probe prompt included. It is stable per database and mode, so it sits in the cacheable prefix.
- Any change to the template must be re-probed: the cost model is fitted to this template, and the probe is cheap.

## Sources

- LLGuidance Lark syntax and lexer notes: https://github.com/guidance-ai/llguidance/blob/main/docs/syntax.md (read 2026-10-16)
- SQLite keywords (147-word list used by `sql_identifier`): https://www.sqlite.org/lang_keywords.html (read 2026-10-16)
- SQLite type affinity rules, section 3.1: https://www.sqlite.org/datatype3.html (read 2026-10-16)
- SQLite CAST expressions (result follows the affinity of the type name): https://www.sqlite.org/lang_expr.html (read 2026-10-16)
- ADR-001 for the API surface and the first measurements of the size limit.
- Probe data: `docs/adr/data/grammar_budget_probes.json`. Coverage reports: `reports/grammar_coverage_dev.md`, `reports/grammar_coverage_minidev.md`.
