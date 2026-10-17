# Review of round 0 (baseline) failures — BIRD Mini-Dev dev

Run `reports/experiments/20261016-145044-333f6b8-dirty/` (config `baseline`: one `direct_full` candidate, gpt-6.1-sol, full schema, grammar on, no retrieval, no repair). EX 241/350 = 68.9%; 109 failures.

## Sample rule

Failures sorted by `(db_id, int(question_id))`; take index `floor(i * 109 / 30)` for `i = 0..29` (stride ≈ 3.63): indices 0, 3, 7, 10, 14, 18, 21, 25, 29, 32, 36, 39, 43, 47, 50, 54, 58, 61, 65, 69, 72, 76, 79, 83, 87, 90, 94, 98, 101, 105. All 11 databases are covered (2–5 items each). For every item I ran the original gold, the prediction and the Arcwise gold on the read-only SQLite file (full results, no row cap, set comparison as in `bird_metric.results_match`) and read the question, evidence, both SQLs and the catalog entries of the columns involved.

## Items

`auto` = `failure_label.label` in the record (gpt-6-luna classifier). `suspect` = record's `gold_suspect`. `=Arcwise` = prediction's result set equals the Arcwise gold's.

| # | idx | qid | db | difficulty | my label | auto | agree | suspect | =Arcwise | justification |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 17 | california_schools | simple | `extra_or_missing_output_columns` | `extra_or_missing_output_columns` | yes | no | no | Adds `sname` and omits `AvgScrWrite` + rank that gold returns; the rank column needs `RANK() OVER`, which the grammar forbids (gold not in grammar); Arcwise rewrote the question to ask for score and rank. |
| 2 | 3 | 27 | california_schools | moderate | `wrong_join_path` | `wrong_join_path` | yes | no | no | INNER JOIN satscores drops schools with no SAT row (813 vs 8,574 rows); both golds LEFT JOIN from schools ("if there is any"). |
| 3 | 7 | 340 | card_games | simple | `other` | `extra_or_missing_output_columns` | **no** | no | no | Self-imposed `LIMIT 1000 OFFSET 0` truncates a 25,061-row answer, so it fails whatever the column; also returns `name` where gold returns `id` (Arcwise rewrote the question to "card ids"). |
| 4 | 10 | 349 | card_games | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | no | Original gold never counts rulings (ranks promo artists by distinct cards); pred counts rulings per printing. Fails Arcwise too: `LIMIT 1` drops the tied second printing of Teferi's Protection. |
| 5 | 14 | 415 | card_games | challenging | `wrong_filter_value` | `wrong_filter_value` | yes | no | no | Copied evidence casing `status = 'legal'`; DB (and schema samples) hold `'Legal'`, so result is NULL. |
| 6 | 18 | 484 | card_games | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Gold returns English `cards.name` for every Italian row and never keeps only the max CMC; pred returns Italian names at max CMC = Arcwise. |
| 7 | 21 | 563 | codebase_community | moderate | `date_handling` | `date_handling` | yes | no | no | Copied evidence literal `'2014/4/23 20:29:39.0'`; stored format is `'2014-04-23 20:29:39.0'` (shown in schema samples) → 0 rows. |
| 8 | 25 | 595 | codebase_community | moderate | `gold_label_suspect` | `wrong_table_or_column` | **no** | yes | no | Evidence says `Views >= 1000` (users.Views) but gold filters `posts.ViewCount` and counts distinct history types, not "one history per post"; Arcwise rewrote question, evidence and threshold. (Pred's any-post reading is also loose.) |
| 9 | 29 | 685 | codebase_community | moderate | `wrong_table_or_column` | `wrong_table_or_column` | yes | no | no | "User who posted it last time" is `posts.LastEditorUserId`; pred took the latest postHistory row carrying the title text (Menno vs mbq). |
| 10 | 32 | 1482 | debit_card_specializing | challenging | `gold_label_suspect` | `gold_label_suspect` | yes | yes | no | Gold ignores the EUR filter, divides by 2012 against the evidence, and returns three unlabeled numbers instead of biggest/lowest; Arcwise rewrote question and evidence. |
| 11 | 36 | 1525 | debit_card_specializing | simple | `gold_label_suspect` | `wrong_table_or_column` | **no** | yes | **yes** | Gold counts transaction rows, not customers; pred's distinct-customer percentage (2.70) = Arcwise. |
| 12 | 39 | 1531 | debit_card_specializing | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | no | Gold picks the top customer from one yearmonth row and uses SUM(Price/Amount) against the evidence; pred follows evidence and picks Arcwise's customer (13665), but Arcwise computes SUM(Price*Amount)/SUM(Amount), so it fails both. |
| 13 | 43 | 1092 | european_football_2 | simple | `wrong_aggregation_or_grouping` | `wrong_aggregation_or_grouping` | yes | no | no | Four leagues tie at the max match count; `ORDER BY … LIMIT 1` (prompt convention 3) returns one, both golds return all four. |
| 14 | 47 | 1136 | european_football_2 | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Gold counts Player_Attributes rows (3), not players; pred's COUNT(DISTINCT player_api_id) (2) = Arcwise. |
| 15 | 50 | 116 | financial | challenging | `float_or_rounding` | `wrong_aggregation_or_grouping` | **no** | no | no | Same value: 430.4545454545455 vs gold 430.45454545454544; pred writes `/ den * 100`, gold `* 100 / den`. |
| 16 | 54 | 168 | financial | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | no | no | Question says "opened their accounts in the district" (account.district_id, as pred joins); gold uses client.district_id, and Arcwise rewrote the question to fit it. |
| 17 | 58 | 902 | formula_1 | simple | `gold_label_suspect` | `wrong_table_or_column` | **no** | no | no | Evidence "track number less than 10 refers to position < 20" does not say which `position`; results.position (pred) is as plausible as driverStandings.position (gold); Arcwise had to name the table in the evidence. |
| 18 | 61 | 945 | formula_1 | simple | `wrong_filter_value` | `wrong_filter_value` | yes | no | no | Evidence wrongly says Melbourne; pred obeyed it over the question's "Adelaide"; 'Melbourne' does not exist in circuits.location. |
| 19 | 65 | 978 | formula_1 | simple | `gold_label_suspect` | `wrong_aggregation_or_grouping` | **no** | no | no | Question asks "how many times" plus location/coordinates; pred returns count + both, gold omits the count; Arcwise deleted "how many times" from the question. |
| 20 | 69 | 1338 | student_club | moderate | `extra_or_missing_output_columns` | `extra_or_missing_output_columns` | yes | no | no | Rows match, but adds `expense_description`; gold returns only `approved`. |
| 21 | 72 | 1399 | student_club | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | no | Gold has no event filter and returns one YES/NULL per attendance row (14 rows); pred answers 'Yes' once. Fails Arcwise only on 'Yes' vs 'YES'. |
| 22 | 76 | 726 | superhero | moderate | `grammar_limitation` | `extra_or_missing_output_columns` | **no** | yes | no | Rows and the name/height columns equal gold; only the `RANK() OVER` column is missing, and the grammar/prompt forbid window functions (gold not in grammar). |
| 23 | 79 | 766 | superhero | moderate | `wrong_filter_value` | `wrong_filter_value` | yes | yes | no | Copied evidence casing `'strength'`; stored value is `'Strength'`, which the 5-value schema sample omits (6 distinct) → 0 rows. |
| 24 | 83 | 1149 | thrombosis_prediction | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Question asks which group is larger and the deviation; gold returns only the ratio, pred both = Arcwise. |
| 25 | 87 | 1227 | thrombosis_prediction | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Gold averages over joined lab rows (patients repeated); pred deduplicates patients = Arcwise (71.95). |
| 26 | 90 | 1242 | thrombosis_prediction | challenging | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Evidence defines age from the current year; gold uses the exam year; pred follows evidence = Arcwise. |
| 27 | 94 | 1254 | thrombosis_prediction | moderate | `gold_label_suspect` | `gold_label_suspect` | yes | yes | **yes** | Gold uses BETWEEN (inclusive), `> '1990'` and counts joined rows, against the evidence; pred = Arcwise (140). |
| 28 | 98 | 1302 | thrombosis_prediction | challenging | `gold_label_suspect` | `wrong_join_path` | **no** | yes | **yes** | Gold counts Laboratory×Examination joined rows (7); pred counts distinct patients (1) = Arcwise. |
| 29 | 101 | 207 | toxicology | challenging | `gold_label_suspect` | `wrong_join_path` | **no** | yes | **yes** | Gold pairs each atom with any double bond in its molecule via molecule_id; pred joins through connected.bond_id = Arcwise (5 elements). |
| 30 | 105 | 245 | toxicology | moderate | `wrong_join_path` | `wrong_join_path` | yes | no | no | `connected` stores every bond in both directions (18,312/18,312 rows mirrored), so `atom_id = … OR atom_id2 = …` double-counts → 2.0 vs 1.0. |

## Counts (sample of 30)

| Label | mine | auto |
|---|---|---|
| `gold_label_suspect` | 17 | 11 |
| `wrong_filter_value` | 3 | 3 |
| `extra_or_missing_output_columns` | 2 | 4 |
| `wrong_join_path` | 2 | 4 |
| `date_handling` | 1 | 1 |
| `wrong_table_or_column` | 1 | 4 |
| `wrong_aggregation_or_grouping` | 1 | 3 |
| `float_or_rounding` | 1 | 0 |
| `grammar_limitation` | 1 | 0 |
| `other` | 1 | 0 |
| `null_handling` | 0 | 0 |
| `evidence_ignored` | 0 | 0 |

**Agreement with the automatic label: 21/30 = 70%.** All 11 items the classifier called `gold_label_suspect` I agree with. The 9 disagreements:

- 6 where the classifier names a model error but the gold is the problem: 207, 1302 (`wrong_join_path`), 1525, 595, 902 (`wrong_table_or_column`), 978 (`wrong_aggregation_or_grouping`). In 207, 1302 and 1525 the prediction already equals the Arcwise result.
- 116: `wrong_aggregation_or_grouping` for a result that differs only in the last float digit.
- 726: `extra_or_missing_output_columns` for a column (`RANK() OVER`) the grammar cannot produce.
- 340: `extra_or_missing_output_columns` (name vs id); the binding error is the self-imposed `LIMIT 1000` on a 25,061-row answer.

`gold_suspect` flag vs my labels: 14 of my 17 `gold_label_suspect` items are flagged. The other 3 (168, 902, 978) are not flagged because Arcwise fixed the question or evidence and kept the SQL. Of the 16 flagged items, 2 (726, 766) are real model or grammar errors.

## Arcwise gold

**9 of the 30 predictions are correct under the Arcwise gold** (484, 1525, 1136, 1149, 1227, 1242, 1254, 1302, 207). 1399 would be too except for 'Yes' vs Arcwise's 'YES'. Across all 109 failures, 33 predictions equal the Arcwise result. Five of the nine (1136, 1227, 1254, 1302, 1525) share one pattern: the original gold counts or averages joined rows, and the model deduplicates entities as Arcwise does. Do not tune prompts toward the original gold's row-counting.

## Most actionable patterns

### 1. Ground string and date literals in stored values (4/30 in sample; 8/109 overall)

The model copies the evidence's literal even when the database stores a different spelling. Prompt convention 2 says "Follow the evidence literally":
- casing: 415 `'legal'`→`'Legal'`, 766 `'strength'`→`'Strength'`, and 769 `'durability'` outside the sample;
- date format: 563 `'2014/4/23 …'`→`'2014-04-23 …'`, and 1350 `'2019-8-20'` outside the sample;
- a value that is not stored: 945 `'Melbourne'` (the evidence is wrong; the question says Adelaide);
- outside the sample, 584 and 1113 have literals corrupted during constrained decoding (`'…deviation?` response? must proper string'`, `'2015-09-10%ၛ'`).

Swapping in the stored spelling makes 415, 563, 766, 769, 1350, 945 and 1113 correct against the original gold (tested; all but 766 are also correct under Arcwise). Fixes to try, cheapest first:
1. After generation, check each literal in `col = 'x'`, `col IN (…)` and `col LIKE 'x%'` with `SELECT 1 FROM t WHERE col = 'x' LIMIT 1`. If it is missing, look it up case-insensitively and with dates normalised to `YYYY-MM-DD`. Rewrite the literal, or send it to one repair turn with the nearest stored values. This catches all 8 above, the decoder garbage included.
2. Turn on matched-value retrieval for words in the question **and the evidence**, with case folding and date normalisation.
3. Rewrite convention 2 as: "Evidence decides columns and formulas. For literals, use the stored spelling, case and format shown in the schema or matched values. If the evidence names a value that contradicts the question or is not stored, follow the question."
4. In the schema renderer, list every value of columns with ≤ 10 distinct values. `attribute.attribute_name` has 6 values and its 5-value sample leaves out `Strength`.

### 2. Percentages: multiply before dividing (1/30 in sample; 6/109 overall)

Convention 9 yields `CAST(x AS REAL) / y * 100`. In 44 of the 45 percentage golds among the 350 questions, the gold writes `CAST(x AS REAL) * 100 / y`. The prediction divided first in 24 of them, and 14 of those failed. Six failures differ only in the last float digit: 85, 116, 743, 760, 954, 1148. Reordering to `* 100 /` makes all six correct (tested; five also under Arcwise). Fix: change convention 9 to "write percentages as `CAST(num AS REAL) * 100 / den`". A deterministic AST rewrite `X / Y * 100` → `X * 100 / Y` would also work; it risks 1 currently correct question whose gold divides first.

### 3. Score and classify against the gold's known faults (17/30 are `gold_label_suspect`)

More than half the sampled failures are gold problems, and the classifier misses 6 of them. Next round:
- Report EX under the Arcwise gold next to the original.
- Before calling the LLM classifier, apply two deterministic pre-labels: prediction equals the Arcwise result → `gold_label_suspect`; result equal after rounding floats to ~1e-9 → `float_or_rounding`. These would have resolved 4 of the 9 disagreements (207, 1302, 1525, 116).
- Leave these items out when choosing prompt changes.

### Smaller, lower-priority items

- **Output columns** (sample: 17, 1338). Overall, projecting the prediction's columns gives the gold in 9/109 (87, 125, 978, 989, 1338, 829, 1149, 231, 268), and 2 more differ only in column order (1405, 1225). About half are multi-part questions ("which X … and the difference") where Arcwise sometimes agrees with the prediction (1149, 978), so a blanket "fewer columns" rule is risky. Target helper columns only: no name, description or identifier column the question does not name (989, 125, 1338). Use the existing `user_requested_outputs` block to fix column order.
- **Ties under `ORDER BY … LIMIT 1`** (1092; 930 outside the sample). Convention 3 pushes LIMIT 1 even when the gold returns ties. A post-execution check could flag it: if row 2 has the same sort key as row 1, rerun with `= (SELECT MAX …)`. Only 2/109.
- **LIMIT as a row cap** (340; 902 harmless). `limit_optional` says "n is at most 1000", and the model sometimes appends `LIMIT 1000`. In benchmark mode, say "add LIMIT only for an explicit top-N".
- **Grammar**: 726 (and part of 17) need `RANK() OVER`. Three of the four out-of-grammar golds (17, 41, 726) failed. Either allow `RANK()/DENSE_RANK() OVER (ORDER BY …)` in the grammar or accept the loss of these 3 questions.
- **Symmetric link tables**: in 245 the model joined `connected` on `atom_id OR atom_id2`. That table stores each bond in both directions, so a catalog note on it would prevent the double count.

## Notes

- Gold of question 701 (outside the sample) did not finish within the 15 s I allowed per query; no other execution problems.
- Ages based on `NOW` (1227, 1242) depend on the run date. Gold and prediction were evaluated on the same date, so the comparison holds.
