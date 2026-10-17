# Grammar-constrained vs unconstrained SQL generation (BIRD Mini-Dev dev, 350 questions)

This analysis is of the R11 runs, before the trailing-newline grammar fix (EXPERIMENTS.md, R12). It is the reading that found the fix: after it, the grammar and JSON runs both score 74.3% on dev (RESULTS.md, ablation table).

Question: does constrained decoding help or hurt generation quality? Tam et al. (2024) found that format restrictions can degrade reasoning.

## Runs compared

| Run | Report | Generation | Repair / literal check | EX |
|---|---|---|---|---|
| Grammar ON, reference (preset `best`) | `reports/experiments/20261016-170229-9e6058b-dirty/` | `sql_query` custom tool, CFG from `build_grammar` (full schema, benchmark mode) | on / on | 72.3% (253/350) |
| Grammar ON, no repair | `reports/experiments/20261016-171742-9e6058b-dirty/` | same | off / off | 72.3% (253/350) |
| Grammar OFF (JSON) | `reports/experiments/20261016-171955-9e6058b-dirty/` | same prompt, structured output `{"sql": string}`, the grammar's spelling rules moved into the prompt | off / off | 74.3% (260/350) |

All three runs: commit `9e6058b` (dirty tree), gpt-6.1-sol at medium effort, one `direct_full` candidate per question, evidence on, same prompt versions (`generate_direct@1.0`, `generate_common@1.2`), same validator, scoping and executor.

Repair and the literal check change nothing here. The two grammar runs agree on correctness for all 350 questions (`text2sql compare` 0 vs 0, p = 1.000), and their SQL differs only on Q640, where the literal check changed `'Mornington'` to `'mornington'` (wrong both times). The repair-off grammar run (171742) has the same switches as the JSON run, so grammar vs JSON is the only difference. The tables below use its SQL. For the reference run (170229) the discordant sets are identical.

The JSON arm is not fully unconstrained decoding. The API constrains the JSON envelope with a JSON schema, and only the `sql` string inside it is free. So the ablation compares SQL under a context-free grammar against free SQL text with the same spelling instructions.

## 1. Paired outcome

| | Grammar correct | Grammar wrong | Total |
|---|---|---|---|
| JSON correct | 249 | **11** | 260 |
| JSON wrong | **4** | 86 | 90 |
| Total | 253 | 97 | 350 |

- Delta (JSON minus grammar): +2.0 points (95% CI -0.3 to +4.3), exact McNemar p = 0.118 (11 vs 4). Source: `uv run --frozen text2sql compare reports/experiments/20261016-170229-9e6058b-dirty reports/experiments/20261016-171955-9e6058b-dirty`. The comparison against the repair-off grammar run gives the same numbers.
- 210 of 350 SQL strings are byte-identical across the two arms, and 125 of the 140 that differ have the same correctness.
- The difference is not significant at n = 350, and each arm is one sample, so there is no replicate to measure run-to-run sampling noise.

## 2. Discordant questions

Classes: **(a)** JSON used a construct the grammar forbids (coverage loss); **(b)** both SQL strings are in the grammar's language, but the grammar run wrote something else, here always a visible decoding artifact; **(c)** the grammar run produced no valid tool call; **(d)** noise-like, both readings plausible or the gold is arbitrary; **(s)** a one-token sampling slip, the rest of the query identical.

"JSON SQL in grammar" means `SqlGrammar.accepts` on the raw JSON SQL and on `normalize_sql(sql, schema)`, with the full-schema benchmark grammar (`build_grammar(load_catalog(db_id).schema(), GrammarOptions())`). `GuidanceMatcher` (llguidance) gives the same verdict.

### 2a. JSON right, grammar wrong (11)

| Q | DB | JSON SQL in grammar (raw / normalized) | What differs | Class |
|---|---|---|---|---|
| 194 | financial | yes / yes | Grammar run computes exact age (subtracts 1 if the birthday has not come yet this year); JSON and BIRD gold use the plain year difference. The grammar run's rows equal the Arcwise-Plat-SQL corrected gold. | d |
| 201 | toxicology | yes / yes | The tool input starts with exactly the JSON query, then does not end: `... ON T1.molecule_id = T3.molecule_id OR ROUND(ROUND(ROUND(...` and a growing `ORDER BY` list until `max_output_tokens` (4,096). The truncated input fails the re-parse, so there is no SQL. | c (termination runaway) |
| 253 | toxicology | yes / yes | Same query except the literal `'#'` became `'#159'` (after `#` the grammar allows only `'` or a digit, ADR-005), followed by a tail `ORDER BY T1.element LIMIT 4 OFFSET 1`; 0 rows. | b (literal close) |
| 416 | card_games | yes / yes | Literal `'*'` became `'*9641B9D8-7B04-44A8-B67D-6FF697016C53'` (digit escape again), tail `LIMIT 1 OFFSET 900719`; 0 rows. The other differences (`COUNT(*)` vs `COUNT(T1.id)`) are immaterial. | b (literal close) |
| 578 | codebase_community | yes / yes | Could not close `'Understanding what Dassault iSight is doing?'` after the `?`: it wrote `'... doing? сво'`, `'... doing?title'`, `'... doing?never matches'` and so on as repeated predicates until 4,096 tokens. No SQL. | c (literal close, runaway) |
| 685 | codebase_community | yes / yes | Grammar run takes the user of the latest matching `postHistory` row (`Menno`); JSON and gold take `posts.LastEditorUserId` (`mbq`). "Posted it last time" fits either. | d |
| 760 | superhero | yes / yes | Identical up to `BETWEEN 150 AND 180`, then a junk tail `NOT IN (SELECT 1) = 0 LIMIT 1 OFFSET 00787`; 0 rows. | b (termination tail) |
| 861 | formula_1 | yes / yes | Identical except `LIKE '1:54%'` became `LIKE '1:54%ʼ'` (U+02BC before the closing quote); 0 rows. | b (literal close) |
| 1110 | european_football_2 | yes / yes | Identical except `LIKE '2010-02-22%'` became `LIKE '2010-02-22%け' NOT LIKE 'x'`, which turns the date filter into an always-true one; 6 rows instead of 1. | b (literal close) |
| 1227 | thrombosis_prediction | yes / yes | Grammar run averages per patient (DISTINCT subquery), giving 71.95; JSON and gold average over lab rows, giving 74.69. The grammar run's rows equal the Arcwise corrected gold. | d |
| 1255 | thrombosis_prediction | yes / yes | Grammar run counts distinct patients and drops NULL diagnoses (`SLE`); JSON and gold count lab rows (`RA`). The grammar run's rows equal the Arcwise corrected gold. | d |

Tally: (a) **0**, (b) **5**, (c) **2**, (d) **4**. All seven (b) and (c) cases are the same two decoder failure modes: a string literal that should end in a punctuation character is not closed cleanly (253, 416, 578, 861, 1110), or the query does not end where the model's own query ends (201, 760). None of them depends on the grammar's coverage. The JSON SQL is in the grammar's language in every case. In six of the seven (all but Q416) the grammar run's text is byte-identical to the JSON text up to the point of failure: the closing quote of the literal, or the end of the query.

### 2b. Grammar right, JSON wrong (4)

| Q | DB | JSON SQL in grammar (raw / normalized) | What differs | Class |
|---|---|---|---|---|
| 72 | california_schools | yes / yes | JSON sums the two enrollment rows (375), which is what the Arcwise corrected gold returns; the grammar run and BIRD gold return both rows (40, 335). | d |
| 412 | card_games | yes / yes | JSON filters `T1.type = 'Creature'` (the full type line) instead of `T1.types`; otherwise identical. 0 rows. | s |
| 945 | formula_1 | yes / yes | JSON filters `location = 'Melbourne'` (taken from the evidence) instead of `'Adelaide'`; otherwise identical. | s |
| 1157 | thrombosis_prediction | yes / yes | JSON takes `Diagnosis` from `Examination` (T2) instead of `Patient` (T1); otherwise identical. | s |

No JSON SQL in this set failed validation or execution, used a forbidden construct, or was stopped by the guard. These are ordinary sampling differences.

### Without the decoding artifacts

Remove the seven (b) and (c) questions and the discordant counts are 4 vs 4 (exact McNemar p = 1.0). Grammar EX would be 260/350 = 74.3%, equal to the JSON arm. In other words, the whole 2.0-point gap is the seven decoding failures.

## 3. Does the unconstrained SQL fit the grammar?

| JSON-arm SQL (350) | Count |
|---|---|
| Accepted by the grammar as written (lark Earley, `SqlGrammar.accepts`) | **350** |
| Accepted after `normalize_sql(sql, schema)` | 350 |
| Accepted by llguidance (`GuidanceMatcher`) as written | 350 |
| Not parseable under the grammar | **0** |
| ... of which stopped by validator / scoping / executor | 0 |
| ... of which executed | 0 |
| Validator errors / execution errors / safety events, whole JSON run | 0 / 0 / 0 |

Given the same spelling rules in its prompt, the model never used a window function, `DATETIME`, `GROUP_CONCAT`, a non-allowlisted function, a free-form alias or an unsplit punctuation literal. Every query it wrote is in the grammar's language. On this run the grammar costs no coverage, and widening it would recover nothing.

The safety side is not exercised either. This split has no adversarial questions, and neither arm triggered a validator, scoping or executor stop.

## 4. Decoding artifacts across all 350 questions

Visible artifacts in the grammar run's tool input, found by comparing it with the JSON SQL for the same question: **9 questions** (2.6%). Seven of them are the flips above. The other two, Q197 and Q584, were wrong in both arms:

- Q197: `bond_type = '-'` became `'-3837292.1192142554 49: tool execution not found.4881.0000000000 1: tool result error...'`, the digit escape again.
- Q584: a title ending in `?` became `'... standard deviation? solid? getting?'`.

The artifacts cluster on string literals whose last character is punctuation. Taking every literal in the JSON SQL and looking for it in the grammar run's tool input for the same question:

| Literal in JSON SQL | Occurrences | Same in grammar run | Mangled in grammar run | Not used by the grammar run's query |
|---|---|---|---|---|
| One punctuation character (`'-'`, `'+'`, `'#'`, `'='`, `'*'`) | 42 | 39 | 3 (Q197 `-`, Q253 `#`, Q416 `*`) | 0 |
| Ends in `%` (LIKE prefix patterns) | 13 | 10 | 2 (Q861, Q1110) | 1 (Q129 used `STRFTIME`) |
| Ends in `?` | 2 | 0 | 2 (Q578 runaway, Q584) | 0 |
| Ends in `)` or `!` | 2 | 2 | 0 | 0 |
| Ends in a letter, digit or space | 536 | 519 | 0 | 17 (different query) |

So 7 of 59 punctuation-final literals were mangled, against 0 of 536 others. ADR-005 already describes this trap for one-character literals. Its fix allows only the closing quote or a digit after `" # ( ) * + - . / : = ? [`. In this run the model took the digit branch three times (`'#159'`, `'*9641…'`, `'-3837292…'`). Literals that end in `%` or `?` after other text are not covered by the fix. The ADR reports 6 of 6 correct attempts on Q197 and Q416 after the fix; this run, one sample each, failed both.

Ending the query is the second failure mode. In 13 questions the grammar run's tool input is the JSON query plus extra text, and in 0 the reverse (exact sign test p = 0.0002). Two of those are the junk tails and runaways above (Q201, Q760). The other 11 are well-formed extra clauses that changed no outcome, for example `AND T2.language IS NOT NULL`, `.0` after a trailing number, `, T1.ID` in an `ORDER BY` or a trailing `AS c1`. [INFERENCE] The asymmetry suggests the hosted constrained decoder makes stopping harder than in free text. The server is not observable, so the mechanism is not verified.

The reference run's repair loop and literal check rescued none of the seven. The runaways leave no SQL to repair, and the mangled literals execute without error.

## 5. Cost side

| | Grammar (171742) | JSON (171955) |
|---|---|---|
| Generation input tokens (cached) | 1,997,072 (1,848,754) | 1,599,920 (1,409,780) |
| Output tokens (reasoning) | 49,382 (15,318) | 50,492 (24,360) |
| Calls hitting `max_output_tokens` | 2 (Q201, Q578; 8,192 tokens) | 0 |
| Generation cost at list price | $0.502 | $0.527 |
| Latency p50 / p95 | 4.1 s / 9.4 s | 3.8 s / 7.1 s |

The grammar run used fewer reasoning tokens on 279 of 350 questions (median -13 tokens per question, 37% fewer in total). Outside the seven artifact questions the two arms are 4 vs 4, so this run shows no accuracy effect from the shorter reasoning. Reasoning happens before the tool call and is not itself under the grammar.

## 6. Summary

- **Net effect:** grammar-constrained decoding scored 2.0 points lower than the same prompt with free SQL in a JSON field (72.3% vs 74.3%; 11 vs 4 discordant; p = 0.12, not significant).
- **Coverage cost: 0 questions.** All 350 unconstrained queries parse under the grammar. Widening it (window functions, `GROUP_CONCAT`, `DATETIME`) would change nothing on this run.
- **Decoding cost: 7 questions, which is the whole net gap.** Five are punctuation-final string literals the hosted decoder could not close cleanly (`'#'`, `'*'`, `'1:54%'`, `'2010-02-22%'`, `'...doing?'`). Two are queries that would not end (one runaway to the output limit, one junk tail). These failures sit in the interaction between the grammar and the hosted decoder, not in the grammar's language. ADR-005's literal fix narrows the first mode but leaves an escape (the digit branch) and does not cover `%'` and `?'` endings.
- **Reasoning/format cost: none detectable.** Outside those seven questions the arms trade 4 wins each. The differences are alternative readings or one-token slips: of the 4 non-artifact grammar losses, 3 return the Arcwise-Plat-SQL corrected gold's rows, and 3 of the 4 JSON losses are one-token slips.

**README paragraph (plain language):**

> Does the grammar hurt accuracy? We ran the same prompt and model on the 350 Mini-Dev dev questions twice: once with the SQL constrained by the per-schema grammar, once with the model writing free SQL inside a JSON field. The grammar run scored 72.3% and the free run 74.3%. That 2-point gap is not statistically significant (11 vs 4 discordant questions, McNemar p = 0.12). It is also not a limit of the grammar: every one of the 350 free-form queries parses under it. The whole gap comes from seven questions where the hosted constrained decoder garbled the output. Mostly it failed to close a string literal that ends in a punctuation character (`'#'` became `'#159'`, `'1:54%'` became `'1:54%ʼ'`); twice the query did not stop where it should have. Outside those seven questions the two runs are tied, 4 wins each, so we see no sign that the format restriction degrades the model's reasoning (Tam et al., 2024). We do see a decoder-interaction cost that the grammar rules can work around but have not fully fixed. This is one sample per arm with one model at one effort level, and the safety benefit of the grammar is not tested by this benign benchmark.

## Appendix: SQL of the discordant questions

The grammar-run SQL is the raw tool input from the repair-off run (171742), read from the response cache. Where the run produced no SQL, it is cut after 420 characters.

### JSON right, grammar wrong

**Q194** (financial, moderate). Provide the IDs and age of the client with high level credit card, which is eligible for loans.

```sql
-- gold (BIRD)
SELECT T1.client_id, STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T3.birth_date) FROM disp AS T1 INNER JOIN card AS T2 ON T2.disp_id = T1.disp_id INNER JOIN client AS T3 ON T1.client_id = T3.client_id WHERE T2.type = 'gold' AND T1.type = 'OWNER'
-- JSON run (correct=True)
SELECT DISTINCT T1.client_id, CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.birth_date) AS INTEGER) AS c1 FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN card AS T3 ON T2.disp_id = T3.disp_id WHERE T3.type = 'gold' AND T2.type = 'OWNER'
-- grammar run (correct=False)
SELECT DISTINCT T1.client_id, CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.birth_date) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', 'now') < STRFTIME('%m-%d', T1.birth_date) THEN 1 ELSE 0 END AS c1 FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN card AS T3 ON T2.disp_id = T3.disp_id WHERE T3.type = 'gold' AND T2.type = 'OWNER'
```

**Q201** (toxicology, moderate). What is the percentage of carbon in double-bond molecules?

```sql
-- gold (BIRD)
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.element = 'c' THEN T1.atom_id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T1.atom_id) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '='
-- JSON run (correct=True)
SELECT CAST(SUM(T1.element = 'c') AS REAL) * 100 / COUNT(T1.atom_id) FROM atom AS T1 INNER JOIN (SELECT DISTINCT T2.molecule_id FROM bond AS T2 WHERE T2.bond_type = '=') AS T3 ON T1.molecule_id = T3.molecule_id
-- grammar run (correct=False)
SELECT CAST(SUM(T1.element = 'c') AS REAL) * 100 / COUNT(T1.atom_id) FROM atom AS T1 INNER JOIN (SELECT DISTINCT T2.molecule_id FROM bond AS T2 WHERE T2.bond_type = '=') AS T3 ON T1.molecule_id = T3.molecule_id OR ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(ROUND(RO … [truncated here; the tool input ran to 11,236 characters and hit max_output_tokens = 4,096]
```

**Q253** (toxicology, challenging). List the elements of all the triple bonds.

```sql
-- gold (BIRD)
SELECT DISTINCT T3.element FROM bond AS T1 INNER JOIN connected AS T2 ON T1.bond_id = T2.bond_id INNER JOIN atom AS T3 ON T2.atom_id = T3.atom_id WHERE T1.bond_type = '#'
-- JSON run (correct=True)
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id OR T1.atom_id = T2.atom_id2 INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '#'
-- grammar run (correct=False)
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id OR T1.atom_id = T2.atom_id2 INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '#159' ORDER BY T1.element LIMIT 4 OFFSET 1
```

**Q416** (card_games, challenging). What percentage of cards without power are in French?

```sql
-- gold (BIRD)
SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'
-- JSON run (correct=True)
SELECT CAST(COUNT(CASE WHEN T2.language = 'French' THEN T1.id END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'
-- grammar run (correct=False)
SELECT CAST(COUNT(CASE WHEN T2.language = 'French' THEN 1 END) AS REAL) * 100 / COUNT(*) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*9641B9D8-7B04-44A8-B67D-6FF697016C53' LIMIT 1 OFFSET 900719
```

**Q578** (codebase_community, moderate). Which user made a post titled 'Understanding what Dassault iSight is doing?' and how much is the reputation of the user?

```sql
-- gold (BIRD)
SELECT T1.DisplayName, T1.Reputation FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T2.Title = 'Understanding what Dassault iSight is doing?'
-- JSON run (correct=True)
SELECT T2.DisplayName, T2.Reputation FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Title = 'Understanding what Dassault iSight is doing?'
-- grammar run (correct=False)
SELECT T2.DisplayName, T2.Reputation FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Title = 'Understanding what Dassault iSight is doing? сво' AND T1.Title = 'Understanding what Dassault iSight is doing? ' OR T1.Title = 'Understanding what Dassault iSight is doing? and' AND T1.Title = 'Understanding what Dassault iSight is doing?title' AND T1.Title = 'Understanding what Dassault iSight is  … [truncated here; the tool input ran to 16,203 characters and hit max_output_tokens = 4,096]
```

**Q685** (codebase_community, moderate). Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.

```sql
-- gold (BIRD)
SELECT T2.ViewCount, T3.DisplayName FROM postHistory AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id INNER JOIN users AS T3 ON T2.LastEditorUserId = T3.Id WHERE T1.Text = 'Computer Game Datasets'
-- JSON run (correct=True)
SELECT DISTINCT T1.ViewCount, T3.DisplayName FROM posts AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.PostId INNER JOIN users AS T3 ON T1.LastEditorUserId = T3.Id WHERE T2.Text = 'Computer Game Datasets'
-- grammar run (correct=False)
SELECT T2.ViewCount, T3.DisplayName FROM postHistory AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id INNER JOIN users AS T3 ON T1.UserId = T3.Id WHERE T1.Text = 'Computer Game Datasets' ORDER BY T1.CreationDate DESC LIMIT 1
```

**Q760** (superhero, challenging). In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?

```sql
-- gold (BIRD)
SELECT CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.height_cm BETWEEN 150 AND 180
-- JSON run (correct=True)
SELECT CAST(SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T2.id) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.height_cm BETWEEN 150 AND 180
-- grammar run (correct=False)
SELECT CAST(SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T2.id) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.height_cm BETWEEN 150 AND 180 NOT IN (SELECT 1) = 0 LIMIT 1 OFFSET 00787
```

**Q861** (formula_1, simple). What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?

```sql
-- gold (BIRD)
SELECT T2.number FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 903 AND T1.q3 LIKE '1:54%'
-- JSON run (correct=True)
SELECT T1.number FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 903 AND T2.q3 LIKE '1:54%'
-- grammar run (correct=False)
SELECT T1.number FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 903 AND T2.q3 LIKE '1:54%ʼ'
```

**Q1110** (european_football_2, moderate). Tell the build Up play passing class for "FC Lorient" on 2010/2/22.

```sql
-- gold (BIRD)
SELECT t2.buildUpPlayPassingClass FROM Team AS t1 INNER JOIN Team_Attributes AS t2 ON t1.team_api_id = t2.team_api_id WHERE t1.team_long_name = 'FC Lorient' AND t2.`date` LIKE '2010-02-22%'
-- JSON run (correct=True)
SELECT T2.buildUpPlayPassingClass FROM Team AS T1 INNER JOIN Team_Attributes AS T2 ON T1.team_api_id = T2.team_api_id WHERE T1.team_long_name = 'FC Lorient' AND T2.date LIKE '2010-02-22%'
-- grammar run (correct=False)
SELECT T2.buildUpPlayPassingClass FROM Team AS T1 INNER JOIN Team_Attributes AS T2 ON T1.team_api_id = T2.team_api_id WHERE T1.team_long_name = 'FC Lorient' AND T2.date LIKE '2010-02-22%け' NOT LIKE 'x'
```

**Q1227** (thrombosis_prediction, moderate). What is the average age of the male patient with high cholesterol?

```sql
-- gold (BIRD)
SELECT AVG(STRFTIME('%Y', date('NOW')) - STRFTIME('%Y', T1.Birthday)) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-CHO` >= 250 AND T1.SEX = 'M'
-- JSON run (correct=True)
SELECT AVG(CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.`T-CHO` >= 250
-- grammar run (correct=False)
SELECT CAST(SUM(CAST(STRFTIME('%Y', CURRENT_DATE) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) AS REAL) / COUNT(T1.ID) FROM Patient AS T1 INNER JOIN (SELECT DISTINCT T3.ID FROM Laboratory AS T3 WHERE T3.`T-CHO` >= 250) AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M'
```

**Q1255** (thrombosis_prediction, moderate). For the patients with an abnormal Ig M level, what is the most common disease they are diagnosed with?

```sql
-- gold (BIRD)
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGM NOT BETWEEN 40 AND 400 GROUP BY T1.Diagnosis ORDER BY COUNT(T1.Diagnosis) DESC LIMIT 1
-- JSON run (correct=True)
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGM <= 40 OR T2.IGM >= 400 GROUP BY T1.Diagnosis ORDER BY COUNT(T1.Diagnosis) DESC LIMIT 1
-- grammar run (correct=False)
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T2.IGM <= 40 OR T2.IGM >= 400) AND T1.Diagnosis IS NOT NULL GROUP BY T1.Diagnosis ORDER BY COUNT(DISTINCT T1.ID) DESC LIMIT 1
```

### Grammar right, JSON wrong

**Q72** (california_schools, moderate). How many students from the ages of 5 to 17 are enrolled at the State Special School school in Fremont for the 2014-2015 academic year?

```sql
-- gold (BIRD)
SELECT T1.`Enrollment (Ages 5-17)` FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.EdOpsCode = 'SSS' AND T2.City = 'Fremont' AND T1.`Academic Year` BETWEEN 2014 AND 2015
-- JSON run (correct=False)
SELECT SUM(T2.`Enrollment (Ages 5-17)`) FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.EdOpsCode = 'SSS' AND T1.City = 'Fremont' AND T2.`Academic Year` = '2014-2015'
-- grammar run (correct=True)
SELECT T1.`Enrollment (Ages 5-17)` FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.EdOpsCode = 'SSS' AND T2.City = 'Fremont' AND T1.`Academic Year` = '2014-2015'
```

**Q412** (card_games, moderate). What is the foreign name of the card in French of type Creature, normal layout and black border color, by artist Matthew D. Wilson?

```sql
-- gold (BIRD)
SELECT name FROM foreign_data WHERE uuid IN ( SELECT uuid FROM cards WHERE types = 'Creature' AND layout = 'normal' AND borderColor = 'black' AND artist = 'Matthew D. Wilson' ) AND language = 'French'
-- JSON run (correct=False)
SELECT T2.name FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T2.language = 'French' AND T1.type = 'Creature' AND T1.layout = 'normal' AND T1.borderColor = 'black' AND T1.artist = 'Matthew D. Wilson'
-- grammar run (correct=True)
SELECT T2.name FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T2.language = 'French' AND T1.types = 'Creature' AND T1.layout = 'normal' AND T1.borderColor = 'black' AND T1.artist = 'Matthew D. Wilson'
```

**Q945** (formula_1, simple). How many circuits are there in Adelaide, Australia?

```sql
-- gold (BIRD)
SELECT COUNT(circuitId) FROM circuits WHERE location = 'Adelaide' AND country = 'Australia'
-- JSON run (correct=False)
SELECT COUNT(T1.circuitId) FROM circuits AS T1 WHERE T1.location = 'Melbourne' AND T1.country = 'Australia'
-- grammar run (correct=True)
SELECT COUNT(T1.circuitId) FROM circuits AS T1 WHERE T1.location = 'Adelaide' AND T1.country = 'Australia'
```

**Q1157** (thrombosis_prediction, simple). For patients with severe degree of thrombosis, list their ID, sex and disease the patient is diagnosed with.

```sql
-- gold (BIRD)
SELECT DISTINCT T1.ID, T1.SEX, T1.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.Thrombosis = 2
-- JSON run (correct=False)
SELECT DISTINCT T1.ID, T1.SEX, T2.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.Thrombosis = 2
-- grammar run (correct=True)
SELECT DISTINCT T1.ID, T1.SEX, T1.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.Thrombosis = 2
```

## Reproduction

- Paired stats: `uv run --frozen text2sql compare <grammar report> <json report>` (both grammar runs give 4 vs 11, p = 0.118; the two grammar runs give 0 vs 0).
- Grammar membership: per question, `g = build_grammar(load_catalog(db_id).schema(), GrammarOptions())`, then `g.accepts(sql)`, `g.accepts(normalize_sql(sql, g.schema))` and `GuidanceMatcher(g.definition).accepts(sql)`.
- Raw tool inputs: `llm.responses` spans in `runs/traces/20261016T171742-1d0b2a.jsonl` give the `request_hash` per question; the payload is in `cache/llm/responses.sqlite` (zlib JSON, `custom_tool_call.input`).
- Discordant queries were re-executed read-only on `bird_db_path(db_id)` to get the result values quoted above.
