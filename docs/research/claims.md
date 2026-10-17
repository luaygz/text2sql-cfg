# Claims for the README, checked against their sources

Every external claim we planned to state in the README, checked on 2026-10-16 against the primary source. For each: the verdict, the wording we can defend, and the evidence (verbatim quotes, table numbers, URLs). Reference numbers in brackets point to [docs/references.md](../references.md).

## 1. XiYan-SQL reached 75.6% EX on the BIRD test set in December 2024

Verdict: confirmed. The exact figure is 75.63% test EX (dev 73.34%, R-VES 71.41%), on the leaderboard entry dated 17 Dec 2024.

Wording: "Multi-candidate pipelines reached 75.63% execution accuracy on the BIRD test set (XiYan-SQL, December 2024) [16, 17]."

Evidence:
- BIRD leaderboard, overall EX table: `Dec 17, 2024 | XiYan-SQL Alibaba Cloud [Yifu Liu et al. '24] | … | 73.34 | 75.63` (Dev, Test). https://bird-bench.github.io/
- arXiv:2411.08599 v2 (17 Dec 2024) abstract: "Overall, our proposed XiYan-SQL achieves the state-of-the-art execution accuracy of 75.63% on Bird benchmark, 89.65% on the Spider test set, 69.86% on SQL-Eval, 41.20% on NL2GQL." v1 (13 Nov 2024) reported only dev (72.23%). https://arxiv.org/html/2411.08599v2
- arXiv:2507.04701 §I: "For the well-known and challenging BIRD benchmark, we achieve an execution accuracy of 75.63%. This result established a new SOTA performance on the BIRD leaderboard upon our submission on December 17, 2024." https://arxiv.org/html/2507.04701

Nuance: XiYan-SQL is now the 30th row of the overall table. Contextual-SQL (27 Feb 2025) ties it at 75.63.

## 2. Agentar-Scale-SQL: headline number, and gains concentrating on hard questions

Headline verdict: confirmed. 81.67% test EX, 74.90% dev, R-VES 77.00%. The paper's #1 claim is dated 27 Nov 2025; it is the 5th row of the leaderboard today.

Hard-question verdict: partly. The paper says this explicitly for oracle pass@k as the candidate count grows, not for the selected answer. The per-difficulty ablation of the full system is mixed.

Wording: "Agentar-Scale-SQL (81.67% test EX) scales generation and selection at test time; its pass@k curve grows fastest on challenging questions, with most of the gain by 8 candidates [19]."

Evidence (arXiv:2509.24403 v6, https://arxiv.org/html/2509.24403):
- Abstract: "Agentar-Scale-SQL achieves SOTA performance on the BIRD benchmark, reaching 81.67% execution accuracy on the test set and ranking first on the official leaderboard". Footnote in §1: "The rankings are dated November 27, 2025."
- §4.5: "increasing the number of candidates consistently boosts the Pass@k rate across all difficulty levels. The improvement is most significant for challenging queries and is most substantial when increasing the candidates up to 8, after which the gains diminish." The values exist only in Fig. 6 (an SVG with text rendered as glyphs; not extractable).
- Table 2, BIRD dev ablation (simple / moderate / challenging / total):

  | Configuration | Simple | Moderate | Challenging | Total |
  | --- | --- | --- | --- | --- |
  | Full system | 79.35 | 69.40 | 64.14 | 74.90 |
  | without ICL generator | 75.89 | 66.38 | 55.86 | 71.12 |
  | without reasoning generator | 74.92 | 63.79 | 58.62 | 70.01 |
  | without selection scaling (majority vote instead) | 77.95 | 66.59 | 62.76 | 73.08 |
  | without iterative refinement | 78.92 | 68.75 | 63.45 | 74.38 |

  Removing the ICL generator costs challenging questions the most (−8.28); replacing the tournament with majority vote costs moderate questions the most (−2.81).
- §4.4: "the reasoning generator holds an edge on simple and moderate tasks, while the ICL generator proves more effective in challenging problems."
- BIRD test by difficulty (Appendix B, Table 3): simple 86.83 (949 questions), moderate 78.20 (555), challenging 71.23 (285).

What we check in our own N-sweep: pass@N and EX per difficulty, so we can say whether both or only pass@N concentrate on hard questions.

## 3. ReViSQL-BIRD reports human-level accuracy on verified BIRD subsets

Verdict: confirmed, with conditions that the README must keep.

Wording: "ReViSQL-BIRD [21], an RL-fine-tuned Kimi-K2.6 trained on 2.5k expert-corrected BIRD training examples, reports 93.8% (greedy) on Arcwise-Plat-Full and 93.0% (16-sample self-consistency) on Arcwise-Plat-SQL, two corrected versions of the 498-question BIRD Mini-Dev. The authors call this human-level because BIRD's reported human accuracy on the test set, 92.96%, falls inside their 95% confidence intervals."

Evidence (arXiv:2603.20004 v4, 21 Aug 2026, https://arxiv.org/html/2603.20004):
- §1: "With greedy decoding, ReViSQL-BIRD-K2.6 achieves 93.8% accuracy on Arcwise-Plat-Full and 91.4% accuracy on Arcwise-Plat-SQL. With self-consistency over 16 candidates, ReViSQL-BIRD-K2.6 reaches 94.2% and 93.0% respectively."
- §5.2: "the human-level accuracy of 92.96% … lies within the 95% confidence interval. In contrast, every prior system we evaluate falls significantly below the human proxy (e.g., OpenSearch at 82.9%/88.2%, p<10^-4)."
- §1: "our pipeline-free results match the proxy human-level performance (92.96%) measured on BIRD Test". Appendix C uses a one-sided exact binomial test and a Wilson interval.
- Training data: "BIRD-Platinum", 2.5k BIRD train instances corrected over 2–4 expert rounds. Self-consistency is plain majority voting over samples at temperature 1.

Cautions: the human figure was measured on BIRD test, not on these sets. Greedy decoding on Arcwise-Plat-SQL (91.4%) is below 92.96. Version 1 of the paper (20 Mar 2026, titled "ReViSQL: Achieving Human-Level Text-to-SQL") used a Qwen3-235B model, a dataset called "BIRD-Verified" and reported 93.2%; quote v4. ReViSQL does not appear on the BIRD leaderboard.

## 4. Annotation errors in BIRD Mini-Dev (Jin et al.) and the corrected sets

Verdict: the numbers are confirmed. The ranking claim needs rewording: the ranking analysis was run on a 100-question BIRD Dev sample, not on Mini-Dev.

Wording: "Jin et al. [20] find annotation errors in 52.8% of BIRD Mini-Dev examples (263 of 498), up from the 32.3% (161) Arcwise reported in 2024 [28]. On a 100-question BIRD Dev sample they corrected, agent rankings moved by up to 9 places, and the Spearman correlation with the full-Dev ranking fell from 0.85 to 0.32. We report results on original Mini-Dev and on their Arcwise-Plat-SQL set."

Evidence (arXiv:2601.08778 v3, https://arxiv.org/html/2601.08778; PVLDB 19(5)):
- §4.3: "we identify annotation errors in 263 of the 498 (52.8%) BIRD Mini-Dev examples, including 161 examples reported in prior work ([Arcwise, 2024])". §1: "which is 20.5% higher than the previously reported rate of 32.3% ([Arcwise, 2024])."
- §4.1: the 500-question Mini-Dev minus "two duplicate examples, leaving 498 unique examples".
- Abstract: "performance changes range from -7% to 31% (in relative terms) and rank changes range from -9 to +9 positions. … the rankings of agents on the uncorrected subset correlate strongly with those on the full Dev set (Spearman's r_s=0.85, p=3.26e-5), whereas they correlate weakly with those on the corrected subset (Spearman's r_s=0.32, p=0.23)." §5.3: "CHESS … increases from 62% to 81% after corrections and moves to 1st place."
- §6 names the releases: "(1) Arcwise-Plat-SQL: we only corrected the SQL annotations, preserving original ambiguities in the questions and evidence; (2) Arcwise-Plat: we resolved both incorrect SQL annotations and underlying ambiguities." ReViSQL [21] calls the second one "Arcwise-Plat-Full".
- Arcwise's sheet (CSV export of https://docs.google.com/spreadsheets/d/1IGm9Otruey60ujUnl8AOkepY3qgWHdFJHnX7hQGUeCw/edit) has 498 rows with 161 labelled corrections, which matches 32.3%.
- Data: https://github.com/uiuc-kang-lab/text_to_sql_benchmarks, files `data/arcwise_plat_sql_only_with_diff.json` and `data/arcwise_plat_full_with_diff.json` (JSON arrays of BIRD-style records with `question_id`, `question`, `evidence`, `SQL`, `db_id`, plus `original_*` fields where a correction was made), and corrected column descriptions under `data/schemas/<db_id>/database_description/`. The full file has 498 records with 134 `original_SQL`, 88 `original_question`, 98 `original_evidence`; ReViSQL's Table 2 reports 132 / 88 / 97 for the same set (difference unexplained).

Related: the BIRD team released a cleaned dev split, `bird-sql-dev-1106`, on 13 Nov 2025 (leaderboard news).

## 5. Maamari et al. (2024): full schema vs schema linking

Verdict: confirmed, with scope. The experiments use a 10% per-database sample of BIRD dev and 2024 models.

Wording: "Maamari et al. [15] found that for strong models, schema linking removed needed columns more often than it removed confusion: their pipeline lost 4.8–11.6 points of EX with schema linking on ft:GPT-4o, and they concluded that schema linking is unnecessary when the schema fits in context."

Evidence (arXiv:2408.07702 v2, https://arxiv.org/html/2408.07702):
- Abstract: "newer models are adept at utilizing relevant schema elements during generation even in the presence of large numbers of irrelevant ones. As such, our Text-to-SQL pipeline entirely forgoes schema linking in cases where the schema fits within the model's context window".
- §4.2: "As the model's SQL generation capability improves, the benefit of schema linking diminishes. In some cases, this can result in a net reduction in accuracy due to missing required columns for generation."
- Table 2 (EX on the dev sample; ft:GPT-4o / Gemini 1.5 Pro / Llama 3.1-405b): full schema 67.35 / 60.54 / 59.18; with table-level linking 62.58 / 55.78 / 56.46; with column-level linking 55.78 / 55.10 / 54.42.
- §5: "For state-of-the-art models, if the schema fits within the context length – yes. However, for smaller or prior generation models, the accuracy gains from schema linking often justify the potential loss."

Counterpoint worth stating next to it: CHESS v3 §3.3 says the same trade-off ("when schema sizes are relatively small and the available LLMs are highly capable, the inclusion of the Schema Selector (SS) agent may introduce a precision-recall trade-off that can negatively impact accuracy"), but reports a 2-point gain from schema selection on a synthetic 4,337-column schema. XiYan-SQL (2507.04701, Table V) reports +1.4 to +2.2 EX from its high-recall column selection, averaged over three generators.

For this project the question turned out not to be forced: ADR-001 first found the API rejecting grammars with a few hundred literal identifiers, but the compact grammar of ADR-005 fits every Mini-Dev schema, so the full schema is always available. Our own measurement (EXPERIMENTS.md, R2) agrees with Maamari et al.: linking as a filter lost 2.3 points.

## 6. Tam et al. (2024): format restrictions and reasoning

Verdict: confirmed, with nuances that cut both ways.

Wording: "Whether constrained decoding hurts reasoning is contested. Tam et al. [8] found JSON-mode and strict schemas degraded reasoning on older models (while helping classification); JSONSchemaBench [26] re-ran their reasoning tasks and found constrained decoding improved accuracy by up to 4%. Our grammar-off ablation measures it for SQL."

Evidence:
- Tam et al., abstract (arXiv:2408.02442 v3): "Surprisingly, we observe a significant decline in LLMs' reasoning abilities under format restrictions. Furthermore, we find that stricter format constraints generally lead to greater performance degradation in reasoning tasks."
- §4.1: "100% of GPT 3.5 Turbo JSON-mode responses placed the "answer" key before the "reason" key, resulting in zero-shot direct answering instead of zero-shot chain-of-thought reasoning." The NL-to-Format two-step setting performs "nearly identical" to unrestricted text.
- Conclusion: "Format restrictions, particularly constrained decoding (JSON-mode), can hinder reasoning abilities while enhancing classification task accuracy. Looser format restrictions generally improve performance and reduce variance in reasoning tasks."
- Models tested: gpt-3.5-turbo-0125, claude-3-haiku, gemini-1.5-flash, LLaMA-3-8B-Instruct, Gemma-2-9B-IT. No reasoning models.
- JSONSchemaBench §1 (arXiv:2501.10868 v3): "Constrained decoding consistently improves the performance of downstream tasks up to 4%, even for tasks with minimal structure like GSM8k." §6 attributes Tam et al.'s drop to "inadequate prompting, insufficient contextual information, and poorly crafted schemas".
- Grammar-Aligned Decoding [25], abstract: grammar-constrained decoding "can distort the LLM's distribution, leading to outputs that are grammatical but appear with likelihoods that are not proportional to the ones given by the LLM".

Why our setup differs from Tam et al.'s failure case [INFERENCE]: the reasoning model reasons in its own (unconstrained) reasoning items before the tool call, and only the SQL string is constrained (ADR-001 observed reasoning items preceding `custom_tool_call`). Their JSON-mode failure was the model skipping reasoning by emitting the answer key first. That argument is a hypothesis to test, not a result.

## 7. OpenAI guidance on few-shot examples for reasoning models

Verdict: partly. OpenAI's docs say reasoning models often do not need examples and that examples misaligned with the instructions can produce poor results. They do not say flatly that examples hurt.

Wording: "OpenAI's reasoning guide advises trying reasoning models zero-shot first and warns that examples which do not match the instructions can produce poor results; its GPT-5.6 prompting guide reports that trimming instructions and examples improved internal evals. We measure few-shots as a switch rather than assume either way."

Evidence:
- Reasoning best practices, "How to prompt reasoning models effectively" (https://developers.openai.com/api/docs/guides/reasoning-best-practices.md): "Try zero shot first, then few shot if needed: Reasoning models often don't need few-shot examples to produce good results, so try to write prompts without examples first. If you have more complex requirements for your desired output, it may help to include a few examples of inputs and desired outputs in your prompt. Just ensure that the examples align very closely with your prompt instructions, as discrepancies between the two may produce poor results." The same section: "Some prompt engineering techniques, like instructing the model to "think step by step," may not enhance performance (and can sometimes hinder it)." The page is framed around o-series models.
- Prompting guidance for GPT-5.6 Sol (https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6.md): "Removing repeated instructions and examples and simplifying tool descriptions can improve task performance and token efficiency. In a sample of internal coding-agent eval runs, configurations with leaner system prompts improved evaluation scores by roughly 10–15% while reducing total tokens by 41–66% and cost by 33–67%." Its trim list includes "examples that do not change behavior".
- Reasoning models guide, "Advice on prompting" (https://developers.openai.com/api/docs/guides/reasoning.md): "Reasoning-capable GPT-5 models usually work best when you give them a clear goal, strong constraints, and an explicit output contract without prescribing every intermediate step."
- The GPT-6 model guide (https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md) says nothing about few-shot examples.

Implication for the prompts: the divide-and-conquer and query-plan methods (CHASE-SQL) are themselves taught through long worked demonstrations; with a reasoning model we describe the method in the instructions and test the demos as a switch (ADR-008).

## 8. BIRD leaderboard snapshot, 2026-10-16

Source: https://bird-bench.github.io/ (static HTML, parsed 2026-10-16). Tables: overall EX, R-VES, Mini-Dev EX, single-model EX. The overall table is sorted by test EX.

Overall EX, top rows (all with oracle knowledge, i.e. the `evidence` field):

| Date | System | Dev EX | Test EX |
| --- | --- | --- | --- |
| — | Human performance (data engineers and DB students) | — | 92.96 |
| Sep 26, 2026 | GrainSQL (Purdue University) | 77.77 | 82.95 |
| Sep 07, 2026 | DataGallery-Text2SQL (Huawei 2012 Labs) | 78.10 | 82.39 |
| Aug 22, 2026 | SiriusAI-SQL (Tencent) | 77.77 | 82.28 |
| Dec 16, 2025 | AskData + GPT-4o (AT&T) | 77.64 | 81.95 |
| Sep 25, 2025 | Agentar-Scale-SQL (Ant Group) | 74.90 | 81.67 |

A second human row reads 72.37 with the oracle-knowledge cell empty (its checkmark sits in the Size column), which reads as human accuracy without evidence; the page does not label it further.

Rows for the systems in our reference list: CHASE-SQL + Gemini 76.02 test (Apr 16, 2025; an earlier Nov 3, 2024 entry has 74.06), XiYan-SQL 75.63, OpenSearch-SQL v2 + GPT-4o 72.28, Distillery + GPT-4o (Maamari et al.) 71.83, CHESS (IR+CG+UT) 71.10, MCS-SQL + GPT-4 65.45, MAC-SQL + GPT-4 59.59, DAIL-SQL + GPT-4 57.41, DIN-SQL + GPT-4 55.90.

Single-model table (systems scored without multi-model pipelines; a Self-Consistency column marks Few 1–7, Many 8–32, Scale >32 candidates): top is Gemini-SQL2 (Google, Jun 3, 2026) at 80.04 test with "Many". OpenAI's own entry, GPT-5.5-xhigh (Apr 28, 2026), scores 72.55 test with no self-consistency.

Mini-Dev EX table (SQLite / MySQL / PostgreSQL): human 93.00 / 91.20 / 90.08; top system Jitto Build (Sep 22, 2026) 75.60 on SQLite; TA + GPT-4 58.00; GPT-4 47.80. These are original-label Mini-Dev numbers, so they are the comparison row for our original Mini-Dev table.
