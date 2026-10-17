# ADR-003: BIRD Mini-Dev data, Arcwise-Plat-SQL and label noise

Status: accepted
Date: 2026-10-16

## Context

The accuracy story rests on BIRD Mini-Dev (SQLite), scored with BIRD's execution accuracy (EX), and on a corrected label set, Arcwise-Plat-SQL, because a large share of Mini-Dev's gold SQL is wrong. Few-shot retrieval later needs BIRD train question/SQL pairs. Everything has to download by script with pinned checksums, and the dev/test split has to be fixed and committed before any tuning starts.

Looking at the actual files turned up four things we had not anticipated.

1. There are three Mini-Dev SQLite question files, not one.
   - The first release, `minidev.zip` on BIRD's Aliyun bucket (Last-Modified 2024-06-20), has 500 rows but only 498 distinct `question_id`s: rows 137 and 138 appear twice, byte-identical.
   - The July 2025 "complete package" (`minidev_0703.zip`, linked from the mini_dev README) replaces the duplicates with two new questions, 119 and 120, and changes the gold SQL of question 1322.
   - The Hugging Face dataset `birdsql/bird_mini_dev`, which the BIRD README calls canonical, was re-uploaded on 2026-01-18 and also changes question 879 (adds `CAST(... AS REAL)` before sorting `fastestLapSpeed`). Questions, evidence, difficulty and `db_id` are identical across all three for the shared ids.
2. There are two copies of the 11 databases with the same schemas but different contents. The Mini-Dev package ships its own `dev_databases/` (byte-identical in the 2024 and 2025 packages); BIRD's `dev.zip` (release `dev_20240627`) ships another. Six of the eleven files are byte-identical. The other five differ:
   - formula_1: the Mini-Dev copy lacks 22 races and their rows in lapTimes (19,845), pitStops (255), qualifying (430) and results (478).
   - thrombosis_prediction: Examination has 106 rows in the Mini-Dev copy and 806 in the Dev copy.
   - toxicology: the Mini-Dev copy lacks 3,222 atoms, 3,223 bonds and 6,446 connected rows.
   - california_schools: 211 `satscores.cds` codes keep their leading zero in the Mini-Dev copy and lose it in the Dev copy, which breaks joins to `frpm.CDSCode` for those schools.
   - european_football_2: `Player.height` is rounded to integers in the Mini-Dev copy (182 rather than 182.88) for all 11,060 players.
   The `database_description` CSVs also differ slightly (card_games set_translations.csv, formula_1 constructors.csv and driverStandings.csv, thrombosis_prediction Examination.csv, and capitalised file names in student_club). Jin et al. note the row difference and evaluate on the Dev databases (Section 4.1).
3. Arcwise-Plat-SQL is not only a gold-SQL fix. It is built on Arcwise's own corrected file, which rewrote 81 questions and 68 evidence strings (counted after collapsing whitespace) as well as SQL; Jin et al. then corrected the SQL of 83 more rows and left Arcwise's questions and evidence alone. "Preserving original ambiguities in the questions and evidence" refers to Arcwise's wording, not BIRD's. Against the canonical Mini-Dev, 125 of the 498 Arcwise-Plat-SQL rows have a different question or evidence, and 179 have different gold SQL text. Running the Arcwise gold against BIRD's original question would be wrong for some rows (question 1500, for example, moves from September 2013 to August 2012).
4. The ranking-change claim we planned to cite is about a different data set. Jin et al.'s −7% to +31% relative EX changes, rank moves of up to nine places, and Spearman correlations of 0.85 against 0.32 come from 100 randomly sampled BIRD Dev examples that they corrected themselves (Section 5), not from Mini-Dev or Arcwise-Plat-SQL. The paper does not report system rankings on Arcwise-Plat-SQL.

## Decision

### Sources

All downloads are pinned by URL (commit-pinned where the host allows it) and SHA-256 in `src/text2sql/data/download.py`, and fetched by `uv run --frozen python -m text2sql.data.download bird` into `data/bird/` (gitignored).

| File | Source | SHA-256 |
| --- | --- | --- |
| `mini_dev_sqlite.json` (500 questions) | huggingface.co/datasets/birdsql/bird_mini_dev, commit f65faf4ae3b638c1fa6df1d3370c8d92c8366301, `data/mini_dev_sqlite-00000-of-00001.json` | 88ceb0710163cae46a256ecea8f0a8c98286599530b60587fda5c3cfe57d45d2 |
| `minidev_databases/` | https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip (800,943,648 bytes); only `minidev/MINIDEV/dev_databases/` is extracted, not the 2 GB MySQL and PostgreSQL dumps | cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f |
| `dev_databases/` | https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (346,207,293 bytes), nested `dev_20240627/dev_databases.zip` | cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630 |
| `arcwise_plat_sql.json` (498 rows) | github.com/uiuc-kang-lab/text_to_sql_benchmarks, commit fe766045c55b6875a43b30e9ac7683df5582f8cf, `data/arcwise_plat_sql_only_with_diff.json` | e7bf76408f99266506ea558d84982c69422e5db3dfecab5f08a3a8d3900e8395 |
| `train_filtered.jsonl` (6,601 pairs) | huggingface.co/datasets/birdsql/bird23-train-filtered, commit 4068469807b255fcfc0816bdd520946fe460d256, `data/train-00000-of-00001.jsonl` | 2ee64aa593e1adc59be7d5b9ce2395372a8ee27fdd94a3fb4d2fe09f3cd34bc8 |

Total download is about 1.15 GB; archives stay in `data/bird/downloads/` so the trees can be rebuilt offline. Not downloaded, but located: Arcwise-Plat (Plat-Full, with questions, evidence and SQL corrected) is `data/arcwise_plat_full_with_diff.json` in the same repository and commit (498 rows, SHA-256 baefe2ca4fbab86c000df72aad9eaa563f7d422e425af2cbff071f656ea4eea8); the repository README says schema issues were fixed for it as well (`data/schemas/`). Arcwise's own corrected file, the base of both, is a Google Drive JSON (id 1iWlYVknwK5wGli5lnwg4stvNzMogjhwj, 498 rows, SHA-256 6cf811789bec89285c7d8c2e15fe967725229c49528653dde2e3651bf6595501). The July 2025 package (`minidev_0703.zip`, Drive id 13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG, SHA-256 aeb211c0e39010bbdae3838bb5e8bd27dc446ed77495b1709f85ccc9bf67f2be) was downloaded once to confirm that its databases are byte-identical to `minidev.zip`'s; the downloader uses the Aliyun copy because Drive needs a confirmation step and is not a stable scripted source.

### Questions and labels

"Original Mini-Dev" means the Hugging Face file at the pinned commit: BIRD's current canonical release, 500 distinct questions (148 simple, 250 moderate, 102 challenging; 11 databases, with the per-database counts in the mini_dev README). Mini-Dev numbers published before July 2025 can only have used the first release, which differs on questions 119, 120, 1322 and 879 (and double-counts 137 and 138), so our numbers are not exactly comparable to those.

BIRD has also published a revised full Dev question file on Hugging Face (`birdsql/bird_sql_dev_20251106`). It is a different set from Mini-Dev and we do not use it.

`text2sql.data.bird.load_minidev()` returns one `BirdExample` per question with the original `question`, `evidence`, `gold_sql`, plus `gold_sql_arcwise`, `question_arcwise` and `evidence_arcwise` joined on `question_id` (Arcwise stores ids as strings and empty evidence as null; both are normalised). Questions 119 and 120 have no Arcwise labels, because they did not exist in the release Arcwise annotated. The Arcwise-Plat-SQL table is therefore over 498 questions and must use the Arcwise question and evidence. `arcwise_inputs_changed` is true for the 125 rows whose inputs differ beyond whitespace; for the other 373 the prediction made for the original table can be reused at no API cost.

### Databases

Original Mini-Dev gold is executed on the Mini-Dev package databases (`bird_db_path(db_id)`, release `"minidev"`), because that is what BIRD ships with these questions. Arcwise-Plat-SQL gold is executed on the BIRD Dev databases (`bird_db_path(db_id, "dev")`), because Jin et al. checked their corrections there. The catalog and the pipeline use the Mini-Dev copy. Executing the same predicted SQL on both copies costs nothing, so the harness can also report original-gold EX on the Dev copy as a sensitivity row.

### Train pairs for few-shot retrieval

The full train set (9,428 pairs) is only distributed inside `train.zip`, 8,919,543,554 bytes including the train databases. BIRD's filtered release on Hugging Face (`bird23-train-filtered`, 6,601 pairs that BIRD kept after a quality check, 2.7 MB, no databases) is the smallest official source and is what we use; `load_bird_train()` returns it with `train_id` = line number. None of its 69 databases overlap the 11 Mini-Dev databases. If the full set is ever needed, `train.json` could be range-read out of the remote zip without fetching the databases; we have not done that.

### Split

`python -m text2sql.data.bird_split` writes `data/splits/bird_minidev_dev.json` (350 questions) and `bird_minidev_test.json` (150), with seed 20261016. Strata are (difficulty, db_id), 33 in all. Each stratum sends floor(0.3 n) questions to test; the remaining 150 − Σfloor slots go one at a time to the stratum whose difficulty and database totals are furthest below 30%. Members are shuffled with `random.Random(20261016)` after sorting by `question_id`. Every stratum gets floor or ceil of its 30% share, and every difficulty and database total is within one question of 30% (test: 44 simple, 75 moderate, 31 challenging). The split is over the 500 canonical questions. Of the two questions without Arcwise labels, 119 is in test and 120 in dev (both financial, moderate), so the Arcwise-Plat-SQL table covers 349 dev and 149 test questions. The test split is used once, at the end.

### Execution accuracy

`text2sql.evals.bird_metric` reimplements `evaluation/evaluation_ex.py` and `evaluation_utils.py` from bird-bench/mini_dev at commit abd11b6db92a1c9f809b32f7564c7c71b34d67f0 (the evaluation files last changed in f9d2750): a prediction scores 1 iff `set(pred_rows) == set(gold_rows)`, which ignores row order and duplicate rows but not column order, compares values with Python equality (`1 == 1.0`, no float tolerance), runs the prediction before the gold on one connection, fetches every row, and gives 0 for any error or timeout. The default timeout is the official `meta_time_out` of 30 s, shared by both statements. Our version opens the file through a `mode=ro` URI and enforces the deadline with a SQLite progress handler; neither changes a score. R-VES follows `evaluation_ves.py`: 100 timing runs, ratios outside mean ± 3σ dropped, reward bands 1.25 / 1 / 0.75 / 0.5 / 0.25, score = mean of √reward × 100.

### Evidence

BIRD's `evidence` field is external knowledge written by annotators, often a near-direct hint at the SQL. The leaderboard convention is to give it to the model, so the headline BIRD rows use it, and every BIRD table also gets a row without it. For the Arcwise table "with evidence" means Arcwise's evidence.

## Consequences

Gold sanity run (`uv run --frozen python -m text2sql.data.bird_gold_check`, local only, 30 s timeout, this machine):

| Gold | Database copy | Errors | Timeouts |
| --- | --- | --- | --- |
| original, 500 | Mini-Dev | 0 | 2 (518, 701) |
| original, 500 | Dev | 0 | 2 (518, 701) |
| Arcwise-Plat-SQL, 498 | Dev | 0 | 2 (518, 701) |
| Arcwise-Plat-SQL, 498 | Mini-Dev | 0 | 2 (518, 701) |

Questions 518 (card_games) and 701 (codebase_community) have the same gold SQL in both label sets and do not finish within the official 30 s here. Run without a limit, 518 took about 45 s (546 rows) and 701 between 5 and 6 minutes (1 row) on either database copy, measured while other jobs shared the machine. On this machine both questions therefore score 0 for every system under BIRD's rule, which caps EX at 99.6% on the original table. We keep the official 30 s so our numbers stay comparable, and the eval report should list these two ids rather than hide them. Caching gold results computed with a longer limit and applying 30 s to predictions only would make them scoreable, at the cost of deviating from the official script.

Of the 496 questions where both golds finish, 132 Arcwise-Plat-SQL gold queries return a different result set from the original gold under BIRD's set comparison, on either database copy (the same 132 ids on both). By database: thrombosis_prediction 21, codebase_community 14, european_football_2 14, california_schools 12, card_games 12, toxicology 12, formula_1 11, superhero 11, debit_card_specializing 9, financial 9, student_club 7. Another 47 rows changed the SQL text without changing the result. The database copy also matters on its own: 23 original gold queries (19 Arcwise) return different results on the Mini-Dev copy than on the Dev copy, all in the five databases listed above.

Why the two tables will differ, in the order we expect it to matter:

- 132 of 498 questions (26.5%) have a different correct answer, so a system that reproduces BIRD's annotation habits (for example `COUNT(T1.id)` over a join that duplicates rows, where Arcwise uses `COUNT(DISTINCT ...)`) is rewarded on the original table and penalised on the corrected one, and vice versa for a system that answers the question as asked.
- 125 questions have different inputs, so the model is asked a somewhat different question.
- Arcwise gold runs on the Dev copy, where 19 of its queries return something different from what they return on the Mini-Dev copy.
- The Arcwise table has 498 questions; 119 and 120 are absent.

The evidence we can cite for the claim that rankings change substantially between the original and the corrected set is Jin et al.'s 100-question corrected Dev subset, not Arcwise-Plat-SQL; the README must say so, and our own comparison is between configurations of one system, not between leaderboard systems.

The label-noise figures to cite, all from Jin et al. (arXiv:2601.08778v3): 263 of 498 Mini-Dev examples (52.8%) have at least one annotation error, counting the first Mini-Dev release with its two duplicates removed and combining their SAR-Agent-assisted expert review with the errors Arcwise reported; Arcwise had reported 161 error examples, and 161 of 498 is the 32.3% the paper compares against; SAR-Agent found 138 of Arcwise's 161 (85.7%); Spider 2.0-Snow has errors in 76 of 121 examples (62.8%). The paper reports no confidence intervals for these rates.

Costs and risks: about 4 GB of disk under `data/bird/` (two database trees of 1.4 GB plus 1.1 GB of archives). If BIRD replaces `minidev.zip` or `dev.zip` in place, the checksum check fails loudly rather than silently changing the benchmark. The Arcwise file and the canonical Mini-Dev JSON are commit-pinned and cannot drift.

## Sources

All accessed 2026-10-16.

- BIRD Mini-Dev repository README and evaluation scripts: https://github.com/bird-bench/mini_dev (commit abd11b6db92a1c9f809b32f7564c7c71b34d67f0), `evaluation/evaluation_ex.py`, `evaluation/evaluation_utils.py`, `evaluation/evaluation_ves.py`, `evaluation/run_evaluation.sh`
- BIRD Mini-Dev on Hugging Face: https://huggingface.co/datasets/birdsql/bird_mini_dev (file listing and commit history via the Hub API)
- BIRD filtered train set: https://huggingface.co/datasets/birdsql/bird23-train-filtered
- BIRD archives: https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip, https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip, https://bird-bench.oss-cn-beijing.aliyuncs.com/train.zip (HTTP HEAD only for the last)
- BIRD Mini-Dev complete package (July 2025): https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view
- Jin, Choi, Zhu, Kang. Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards. arXiv:2601.08778v3, https://arxiv.org/abs/2601.08778 (PDF text read: Sections 1, 4.1, 4.3, 5, 6, 7)
- Code and data for that paper: https://github.com/uiuc-kang-lab/text_to_sql_benchmarks (README and `data/`, commit fe766045c55b6875a43b30e9ac7683df5582f8cf)
- Arcwise's corrected Mini-Dev file, linked from that README: https://drive.google.com/file/d/1iWlYVknwK5wGli5lnwg4stvNzMogjhwj/view
