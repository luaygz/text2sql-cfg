# Prompts and mechanisms from the papers

Research notes behind the pipeline stages described in [ADR-008](../adr/008-pipeline-design.md). Everything here was read on 2026-10-16 from the papers (arXiv HTML/PDF, venue camera-ready where newer) and the authors' repositories. Each section names the URL or repository file it came from. Full citations are in [docs/references.md](../references.md); the numeric claims we plan to quote in the README are in [claims.md](claims.md).

## How to read these notes

- "verbatim" or [V]: copied from paper text, an HTML listing, or a raw repository file. Typography is kept as rendered, including curly quotes and the `‘name‘` backtick artifacts that LaTeX leaves in the CHASE-SQL PDF. Placeholders such as `{QUESTION}` and doubled braces `{{ }}` are as in the source (Python `str.format` escaping).
- [T]: transcribed by hand from a figure image; small transcription risk.
- [INFERENCE]: my reading of code or text, not something the authors state.
- `[... N examples omitted ...]`: long few-shot demonstrations were cut. Instruction text is never cut.
- First-person remarks ("I did not read …") record what was and was not checked in this pass.

These prompts were written for GPT-4-era, Claude 3.5 and Gemini 1.5 models that returned SQL as free text (fenced blocks, JSON fields, `<FINAL_ANSWER>` tags). This project never takes SQL from text: every candidate comes out of the forced `sql_query` grammar tool (ADR-001). When adapting a prompt, keep the method text and drop the output-format instructions; ADR-008 says which parts we reuse.

## Provenance at a glance

| System | Official code | Where the prompts below come from |
| --- | --- | --- |
| CHESS | github.com/ShayanTalaei/CHESS | Repo `templates/*.txt`; the paper's appendix figures show older JSON prompts that survive as `generate_candidate_three` and `revise_two`. The Unit Tester exists only in arXiv v3 and in repo code from 2024-11-13 on. |
| CHASE-SQL | none released | Paper appendix (camera-ready A.8–A.13): one worked demo each for divide-and-conquer and query-plan, plus the full synthetic-example, fixer and pairwise-selection prompts. The full divide-and-conquer and query-plan instruction templates exist only in the CHESS repo (a CHASE co-author's), where they are not labelled as CHASE code. |
| MCS-SQL | none released | Paper Appendix B (identical in arXiv v1 and COLING 2025). |
| DIN-SQL | github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting | Repo `DIN-SQL.py`, `DIN-SQL_BIRD.py`; generic self-correction prompt transcribed from the paper figure. |
| MAC-SQL | github.com/wbbeyourself/MAC-SQL | Repo `core/const.py`. |
| DAIL-SQL | github.com/BeachWang/DAIL-SQL | Paper listings and repo prompt classes; paper and code differ (distance metric, threshold, prefix text). |
| XiYan-SQL | github.com/XGenerationLab/M-Schema (renderer); XiYan-SQL repo has a README only | M-Schema from code; generator, selection and refiner prompts transcribed from the preview paper's figures. Schema-filter prompts were never published. |
| OpenSearch-SQL | github.com/OpenSearch-AI/OpenSearch-SQL | Paper listings and repo `src/llm/all_prompt.py`; several alignment prompts in the repo are in Chinese. |
| Agentar-Scale-SQL | github.com/antgroup/Agentar-Scale-SQL (partial release) | Paper Appendix F listings (decoded from the HTML). The revisor prompt and two of the three ICL prompt styles are unpublished. |

## Stage index

Where to find the source material for each pipeline stage.

| Pipeline stage | Sections below |
| --- | --- |
| Keyword and literal extraction | Part 1 §1 (CHESS keyword prompt); Part 3 §4.3 (Agentar task understanding: literals plus question skeleton); Part 3 §3.2 (OpenSearch extraction) |
| Value retrieval (exact, MinHash LSH, embeddings) | Part 1 §1 (CHESS LSH parameters and retrieval cascade); Part 2 §1f (CHASE, which defers to CHESS); Part 3 §2.2 (XiYan value retriever); Part 3 §3.1 (OpenSearch value alignment) |
| Schema linking | Part 1 §2 (CHESS schema selector, precision and recall per step); Part 2 §2a (MCS shuffled multi-prompt union); Part 3 §2.2 (XiYan iterative column selection); Part 1 §7 (MAC-SQL selector) |
| Schema rendering for prompts | Part 3 §2.1 (M-Schema, with DDL vs M-Schema numbers); Part 3 §4.2 (Agentar light schema); Part 3 §1.3–1.4 (DAIL code representation); Part 2 §2b (MCS: sample rows as CSV) |
| Few-shot retrieval with masked questions | Part 3 §1.1–1.2 (DAIL masking and selection); Part 2 §2b (MCS masking prompt); Part 3 §4.3 (Agentar skeleton prompt); Part 3 §3.1 (OpenSearch query-CoT-SQL examples) |
| Divide-and-conquer CoT | Part 2 §1a; Part 1 §7 (MAC-SQL decomposer); Part 3 §4.3 (Agentar CoT generator) |
| Query-plan CoT | Part 2 §1b |
| Online synthetic examples | Part 2 §1c |
| Execution repair | Part 2 §1d (CHASE fixer, β = 3); Part 1 §3 (CHESS revise); Part 1 §6 (DIN-SQL generic and gentle self-correction); Part 1 §7 (MAC-SQL refiner); Part 3 §2.3, §3.2, §4.3 (XiYan, OpenSearch, Agentar fixers) |
| Result clustering and voting | Part 2 §2c (MCS confidence filter); Part 3 §3.1 (OpenSearch vote with fastest-query tie-break); Part 3 §1.4 (DAIL self-consistency) |
| LLM judge selection | Part 2 §1e (CHASE pairwise, both orders); Part 2 §2d (MCS multiple choice); Part 3 §2.4 (XiYan candidate reorganisation); Part 3 §4.1, §4.3 (Agentar round-robin tournament) |
| Unit-test selection | Part 1 §4 (CHESS v3 unit tester) |
| Consistency alignment | Part 3 §3.1–3.2 (OpenSearch info, agent, function and style alignment) |

## Part 1. CHESS, DIN-SQL, MAC-SQL


Templates marked "verbatim" were copied from raw GitHub files; `{X}` placeholders and doubled `{{ }}` are as in the source (Python `str.format` escaping).

---

### 0. CHESS version history: what changed
- **v1 (27 May 2024)** and **v2 (27 Jun 2024)** have the same abstract. They describe a **3-stage pipeline**: "entity and context retrieval, schema selection, and SQL generation" (v1 §3: https://arxiv.org/html/2405.16755v1). There is **no Unit Tester**: grepping v2's HTML for "unit test" gives 0 hits (https://arxiv.org/html/2405.16755v2). In v1/v2, revision uses "self-consistency to select the SQL query that appears most consistently across three samples" (v1 §3.3).
  > v1 abstract: "…we have developed an adaptive schema pruning technique that adjusts based on the complexity of the problem and the model's context size. … Our method achieves new state-of-the-art performance on the cross-domain challenging BIRD dataset." (https://arxiv.org/abs/2405.16755v1)
- **v3 (25 Nov 2024)** reframes CHESS as a **4-agent framework**: Information Retriever (IR), Schema Selector (SS), Candidate Generator (CG), and **Unit Tester (UT)**.
  > v3 abstract: "…the Candidate Generator (CG) generates high-quality candidates and refines queries iteratively, and the Unit Tester (UT) validates queries through LLM-based natural language unit tests. … CHESS achieves 71.10% accuracy on the BIRD test set, within 2% of the leading proprietary method, while requiring approximately 83% fewer LLM calls." (https://arxiv.org/abs/2405.16755v3)
- **Repo history** (GitHub API commits list, https://api.github.com/repos/ShayanTalaei/CHESS/commits). Initial commit 2024-06-20. Last pre-agent commit `fc6f0b7ef3` on 2024-09-08. Commit `3d6e835f85` on **2024-11-13** "Add the agentic framework code" adds `src/workflow/agents/unit_tester/*` and the `templates/template_*` names used below.
  - The v1-era tree at `fc6f0b7ef3` has `src/pipeline/*.py` and the templates `template_keyword_extraction.txt`, `template_column_filtering*.txt`, `template_table_selection.txt`, `template_column_selection.txt`, `template_candidate_generation.txt`, `template_finetuned_candidate_generation.txt`, `template_revision.txt`. It has **no unit-test files** (https://api.github.com/repos/ShayanTalaei/CHESS/git/trees/fc6f0b7ef3?recursive=1).

---

### 1. CHESS: Information Retriever (IR)

#### Mechanism
- Tools: `extract_keywords`, `retrieve_entity`, `retrieve_context` (v3 §3.1, https://arxiv.org/html/2405.16755v3).
- **Repo file paths** (https://github.com/ShayanTalaei/CHESS):
  - `src/workflow/agents/information_retriever/information_retriever.py`
  - `src/workflow/agents/information_retriever/tool_kit/extract_keywords.py`
  - `src/workflow/agents/information_retriever/tool_kit/retrieve_entity.py`
  - `src/workflow/agents/information_retriever/tool_kit/retrieve_context.py`
  - LSH build: `src/database_utils/db_values/preprocess.py`. LSH query: `src/database_utils/db_values/search.py`.
  - Vector DB build: `src/database_utils/db_catalog/preprocess.py`. Vector DB query: `src/database_utils/db_catalog/search.py`.
  - Preprocess entry point: `src/preprocess.py`, `run/run_preprocess.sh`.
  - Templates: `templates/template_extract_keywords.txt`.
- **Keyword extraction**: a single few-shot LLM call. In config `run/configs/CHESS_IR_CG_UT.yaml` and `CHESS_IR_SS_CG.yaml` it runs as `engine_name: 'gpt-4o-mini'`, `temperature: 0.2`, `parser_name: 'python_list_output_parser'` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/run/configs/CHESS_IR_CG_UT.yaml). The v1-era `run/run_main.sh` used `gpt-3.5-turbo-0125` at temperature 0.2 (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/run/run_main.sh). The keyword template is **byte-identical** between v1-era `template_keyword_extraction.txt` and current `template_extract_keywords.txt` (I fetched both raw files and diffed them).

##### Entity retrieval (MinHash LSH → edit distance → embedding)
- **Preprocessing / index** (`src/database_utils/db_values/preprocess.py`, https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/database_utils/db_values/preprocess.py):
  - Distinct values are taken only from **TEXT columns that are not primary keys**.
  - Columns are skipped if the name contains any of `"_id", " id", "url", "email", "web", "time", "phone", "date", "address"` or ends with `"Id"`.
  - A column's distinct values are fetched if `("name" in column.lower() and sum_of_lengths < 5000000) or (sum_of_lengths < 2000000 and average_length < 25) or count_distinct < 100`.
  - Shingles are **character n-grams**: `string[i:i + n_gram]`, `MinHash(num_perm=signature_size)`.
  - Index: `MinHashLSH(threshold=threshold, num_perm=signature_size)`, keyed `f"{table_name}_{column_name}_{id}"`.
  - Pickles are written to `<db_dir>/preprocessed/{db_id}_lsh.pkl`, `{db_id}_minhashes.pkl`, `{db_id}_unique_values.pkl`.
- **Parameters actually passed** (`run/run_preprocess.sh`, https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/run/run_preprocess.sh): `signature_size=100` (num_perm), `n_gram=3` (shingle size), `threshold=0.01` (LSH Jaccard threshold). The same three values appear in the v1-era script (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/run/run_preprocess.sh).
  - Caution: the argparse default in `src/preprocess.py` is `--signature_size 20` (`n_gram` 3, `threshold` 0.01). The shell script overrides it to 100 (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/preprocess.py).
- **Query** (`src/database_utils/db_values/search.py::query_lsh`, defaults `signature_size=100, n_gram=3, top_n=10`): MinHash the keyword, call `lsh.query`, re-rank candidates by MinHash Jaccard estimate, and keep the top 10 (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/database_utils/db_values/search.py).
- **Retrieval cascade** (`retrieve_entity.py`, https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/information_retriever/tool_kit/retrieve_entity.py):
  1. Search strings for each keyword:
     - the whole keyword;
     - for every space position, the prefix and the suffix (`keyword[:i]`, `keyword[i+1:]`);
     - if the keyword contains `=`, the right-hand side.
  2. `query_lsh(keyword=substring, signature_size=100, top_n=10)`.
  3. Edit-distance filter: `difflib.SequenceMatcher(None, substring.lower(), value.lower()).ratio() >= 0.3` (`self.edit_distance_threshold = 0.3`).
  4. Embedding filter: `OpenAIEmbeddings(model="text-embedding-3-small")`, dot product between substring and value embeddings `>= 0.6` (`self.embedding_similarity_threshold = 0.6`).
  5. Per (table, column), keep values with `edit_distance_similarity >= 0.9*max` and then `embedding_similarity >= 0.9*max`.
  6. The result goes to `state.schema_with_examples`, rendered as `-- examples:` comments in the schema.
  - The v1-era `src/pipeline/entity_retrieval.py` has the same `0.3` / `0.6` thresholds, `text-embedding-3-small`, and `query_lsh(..., signature_size=100, top_n=10)` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/src/pipeline/entity_retrieval.py).
  - Paper description (v3 App. A.1, https://arxiv.org/html/2405.16755v3):
    > "Our approach involves using LSH queries to retrieve the top 10 similar values, after which we compute the edit distance and semantic similarity between the keyword and these values to further refine the results. … we first identify the top 10 values closest to each keyword based on cosine similarity between their embedding vectors (obtained using OpenAI text-embedding-3-small) and the keyword's embedding vector. We then filter out values that fall below a specific threshold. Finally, for each keyword and column, we retain only the value that has the smallest edit distance."

    The paper also reports a speedup "from 5 minutes to 5 seconds" vs. computing edit distance over all values. [INFERENCE] The code's order (edit distance first, then embedding, then a relative 0.9×max cut) differs slightly from the paper prose.
- **Column-name matching** (also in `retrieve_entity.py::_get_similar_column_names`):
  - Keywords, their `=`-LHS, parenthesised substrings and split words are compared to every column name using `difflib` ratio `>= 0.9`, after lowercasing, removing spaces and `_`, and `rstrip("s")`.
  - Matches go to `state.similar_columns` and are force-added to the tentative schema by the SS tools (`state.add_columns_to_tentative_schema(state.similar_columns)` in `filter_column.py` and `select_tables.py`).

##### Context retrieval (vector DB over catalog descriptions)
- **Build** (`src/database_utils/db_catalog/preprocess.py`, https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/database_utils/db_catalog/preprocess.py):
  - For each (table, column) in BIRD `database_description/*.csv`, one `Document` is created per non-empty field among `column_name` (the expanded name), `column_description` and `value_description`. Metadata holds all three plus `table_name` and `original_column_name`.
  - Store: `Chroma.from_documents(docs, OpenAIEmbeddings(model="text-embedding-3-large"), persist_directory=<db_dir>/context_vector_db)`.
  - The v1-era code also uses `text-embedding-3-large` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/src/database_utils/db_catalog/preprocess.py).
  - The paper says "utilizing ChromaDB" (v3 App. A.2). It cites OpenAI embeddings and names `text-embedding-3-small` only in A.1 (values).
- **Query** (`retrieve_context.py`, https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/information_retriever/tool_kit/retrieve_context.py, and `db_catalog/search.py`):
  - For each keyword, two queries are run: `f"{question} {keyword}"` and `f"{evidence} {keyword}"`. Each is `similarity_search_with_score(query, k=top_k)` with `top_k: 5` (config).
  - Results are merged per (table, column), keeping the entry with the higher `score`. [INFERENCE] Chroma's score is a distance, so "higher wins" may favour worse matches; the code does exactly this.
  - Output: `state.schema_with_descriptions`.

#### Prompt: keyword extraction (verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_extract_keywords.txt (identical to the v1-era `templates/template_keyword_extraction.txt` at `fc6f0b7ef3`).
```
Objective: Analyze the given question and hint to identify and extract keywords, keyphrases, and named entities. These elements are crucial for understanding the core components of the inquiry and the guidance provided. This process involves recognizing and isolating significant terms and phrases that could be instrumental in formulating searches or queries related to the posed question.

Instructions:

Read the Question Carefully: Understand the primary focus and specific details of the question. Look for any named entities (such as organizations, locations, etc.), technical terms, and other phrases that encapsulate important aspects of the inquiry.

Analyze the Hint: The hint is designed to direct attention toward certain elements relevant to answering the question. Extract any keywords, phrases, or named entities that could provide further clarity or direction in formulating an answer.

List Keyphrases and Entities: Combine your findings from both the question and the hint into a single Python list. This list should contain:

Keywords: Single words that capture essential aspects of the question or hint.
Keyphrases: Short phrases or named entities that represent specific concepts, locations, organizations, or other significant details.
Ensure to maintain the original phrasing or terminology used in the question and hint.

Example 1:
Question: "What is the annual revenue of Acme Corp in the United States for 2022?"
Hint: "Focus on financial reports and U.S. market performance for the fiscal year 2022."

["annual revenue", "Acme Corp", "United States", "2022", "financial reports", "U.S. market performance", "fiscal year"]

Example 2:
Question: "In the Winter and Summer Olympics of 1988, which game has the most number of competitors? Find the difference of the number of competitors between the two games."
Hint: "the most number of competitors refer to MAX(COUNT(person_id)); SUBTRACT(COUNT(person_id where games_name = '1988 Summer'), COUNT(person_id where games_name = '1988 Winter'));"

["Winter Olympics", "Summer Olympics", "1988", "1988 Summer", "Summer", "1988 Winter", "Winter", "number of competitors", "difference", "MAX(COUNT(person_id))", "games_name", "person_id"]

Example 3:
Question: "How many Men's 200 Metres Freestyle events did Ian James Thorpe compete in?"
Hint: "Men's 200 Metres Freestyle events refer to event_name = 'Swimming Men''s 200 metres Freestyle'; events compete in refers to event_id;"

["Swimming Men's 200 metres Freestyle", "Ian James Thorpe", "Ian", "James", "Thorpe", "compete in", "event_name", "event_id"]

Task:
Given the following question and hint, identify and list all relevant keywords, keyphrases, and named entities.

Question: {QUESTION}
Hint: {HINT}

Please provide your findings as a Python list, capturing the essence of both the question and hint through the identified terms and phrases. 
Only output the Python list, no explanations needed.
```

#### Numbers (IR)
- Ablation, "w/o retrieve_entity & _context": 59.86 vs 64.62 all tools (**−4.76**) on the Subsampled Dev Set (SDS: 147 BIRD-dev questions = 81 simple / 54 moderate / 12 challenging).
  > "In the configuration without entity and context retrieval, we retrieved a random example and included column descriptions for all columns. This approach highlights the significant impact of our selective retrieval, which outperforms naive context augmentation by 4.76% in execution accuracy."

  Source: v3 Table 4 + §4.3 (https://arxiv.org/html/2405.16755v3). Same numbers in v1 Table 3 (https://arxiv.org/html/2405.16755v1).

---

### 2. CHESS: Schema Selector (SS)

#### Mechanism
- Tools: `filter_column` (per-column binary LLM relevance), `select_tables`, `select_columns` (v3 §3.1).
- Repo:
  - `src/workflow/agents/schema_selector/schema_selector.py`
  - `tool_kit/filter_column.py`, `tool_kit/select_tables.py`, `tool_kit/select_columns.py`
  - Templates: `templates/template_filter_column.txt`, `template_select_tables.txt`, `template_select_columns.txt`
- **filter_column** (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/schema_selector/tool_kit/filter_column.py):
  - One LLM call per column, run in parallel via `async_llm_chain_call`. The input is a `COLUMN_PROFILE` built by `DatabaseManager().get_column_profiles(schema_with_examples=..., use_value_description=True, with_keys=True, with_references=True, ...)`.
  - A column is kept iff `is_column_information_relevant.lower() == "yes"`.
  - Afterwards it calls `add_columns_to_tentative_schema(state.similar_columns)` and `add_connections_to_tentative_schema()`.
  - Paper (v3 App. A.3):
    > "in all of our sub-modules, we consistently retain foreign key and primary key columns, irrespective of the outputs from column selection and filtering processes."
  - Config `CHESS_IR_SS_CG.yaml`: `gpt-4o-mini`, T=0.0.
- **select_tables** (`select_tables.py`):
  - `mode: 'ask_model'`. The prompt gets the tentative schema string. With multiple samples (`sampling_count`, default 1) the table lists are unioned (case-insensitive).
  - The tentative schema is then restricted to the selected tables, and similar columns plus key connections are re-added.
  - `mode: 'corrects'` uses the gold-SQL tables (oracle).
  - Config: `gpt-4o`, T=0.0 (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/run/configs/CHESS_IR_SS_CG.yaml).
- **select_columns**: `mode: 'ask_model'`, `gpt-4o`, T=0.0 (same config).
- v1-era engines (`run/run_main.sh` at `fc6f0b7ef3`): column_filtering `gpt-3.5-turbo-0125` T=0.0; table_selection, column_selection, candidate_generation and revision all `gpt-4-turbo` T=0.0 with `sampling_count: 1`.
- Template provenance (diffed raw files at `fc6f0b7ef3` vs `main`):
  - `template_select_columns.txt` == v1 `template_column_selection.txt`.
  - `template_filter_column.txt` == v1 `template_column_filtering_with_examples.txt`.
  - `template_select_tables.txt` == v1 `template_table_selection.txt`, except for a trailing newline.

#### Prompt: filter_column (instructions verbatim; 15 of 16 examples omitted)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_filter_column.txt
````
You are a detail-oriented data scientist tasked with evaluating the relevance of database column information for answering specific SQL query question based on provided hint.

Your goal is to assess whether the given column details are pertinent to constructing an SQL query to address the question informed by the hint. Label the column information as "relevant" if it aids in query formulation, or "irrelevant" if it does not.

Procedure:
1. Carefully examine the provided column details.
2. Understand the question about the database and its associated hint.
3. Decide if the column details are necessary for the SQL query based on your analysis.

Here are some examples of how to determine if the column information is relevant or irrelevant to the question and the hint:

Example 1:
Column information:
Table name: `movies`
Original column name: `movie_title`
Data type: TEXT
Description: Name of the movie
Example of values in the column: `La Antena`

Question:
Name movie titles released in year 1945. Sort the listing by the descending order of movie popularity.

HINT:
released in the year 1945 refers to movie_release_year = 1945;

```json
{{
  "chain_of_thought_reasoning": "The question specifically asks for movie titles from a particular year and to sort them by popularity. The column movie_title directly provides the names of movies, which is exactly what is required to list the movie titles as requested in the question.",
  "is_column_information_relevant": "Yes"
}}
```

[... 15 examples omitted (Examples 2–16; same Column information / Question / HINT / json format; 3 of the 16 are "No") ...]

Now, its your turn to determine whether the provided column information can help formulate a SQL query to answer the given question, based on the provided hint.

The following guidelines are VERY IMPORTANT to follow. Make sure to check each of them carefully before making your decision:
1. You're given only one column's information, which alone isn't enough to answer the full query. Concentrate solely on this provided data and assess its relevance to the question and hint without considering any missing information.
2. Read the column information carefully and understand the description of it, then see if the question or the hint is asking or referring to the same information. If yes then the column information is relevant, otherwise it is irrelevant.
3. Look beyond mere keywords. Assess whether there is a meaningful, semantic connection between the column information and the needs of the question or hint. Mere word matches do not necessarily imply relevance.
4. If the question refers to applying a logic on a data such as average, sum, max, min, or any other operation, and the column information is a part of that logic, then the column information is relevant.
5. Pay attention to the provided `Example of values in the column`. If you see a shared keyword between the example and the question or hint, then the column information is relevant. (VERY IMPORTANT)
6. If you see the column name appeared in the hint, then it is definitely relevant. (VERY IMPORTANT)
7. Note that it does not matter if the question is asking for other information not contained in the column, as long as this column's information is useful for crafting a SQL query answering the question, you should consider this column as relevant.

Column information:
{COLUMN_PROFILE}

Question:
{QUESTION}

HINT:
{HINT}

Take a deep breath and provide your answer in the following json format:

```json
{{
  "chain_of_thought_reasoning": "One line explanation of why or why not the column information is relevant to the question and the hint.",
  "is_column_information_relevant": "Yes" or "No"
}}
```

Only output a json as your response.
````
The "No" examples are Examples 2, 6 and 11 (from the full read of the raw file).

#### Prompt: select_tables (verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_select_tables.txt
````
You are an expert and very smart data analyst. 
Your task is to analyze the provided database schema, comprehend the posed question, and leverage the hint to identify which tables are needed to generate a SQL query for answering the question.

Database Schema Overview:
{DATABASE_SCHEMA}

This schema provides a detailed definition of the database's structure, including tables, their columns, primary keys, foreign keys, and any relevant details about relationships or constraints.
For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a critical hint to identify the tables that will be used in the SQL query.

Question:
{QUESTION}

Hint:
{HINT}

The hint aims to direct your focus towards the specific elements of the database schema that are crucial for answering the question effectively.

Task:
Based on the database schema, question, and hint provided, your task is to determine the tables that should be used in the SQL query formulation. 
For each of the selected tables, explain why exactly it is necessary for answering the question. Your explanation should be logical and concise, demonstrating a clear understanding of the database schema, the question, and the hint.

Please respond with a JSON object structured as follows:

```json
{{
  "chain_of_thought_reasoning": "Explanation of the logical analysis that led to the selection of the tables.",
  "table_names": ["Table1", "Table2", "Table3", ...]
}}
```

Note that you should choose all and only the tables that are necessary to write a SQL query that answers the question effectively.
Take a deep breath and think logically. If you do the task correctly, I will give you 1 million dollars. 

Only output a json as your response.
````

#### Prompt: select_columns (verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_select_columns.txt
````
You are an expert and very smart data analyst.
Your task is to examine the provided database schema, understand the posed question, and use the hint to pinpoint the specific columns within tables that are essential for crafting a SQL query to answer the question.

Database Schema Overview:
{DATABASE_SCHEMA}

This schema offers an in-depth description of the database's architecture, detailing tables, columns, primary keys, foreign keys, and any pertinent information regarding relationships or constraints. Special attention should be given to the examples listed beside each column, as they directly hint at which columns are relevant to our query.

For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a critical hint to identify the columns that will be used in the SQL query.

Question:
{QUESTION}

Hint:
{HINT}

The hint aims to direct your focus towards the specific elements of the database schema that are crucial for answering the question effectively.

Task:
Based on the database schema, question, and hint provided, your task is to identify all and only the columns that are essential for crafting a SQL query to answer the question.
For each of the selected columns, explain why exactly it is necessary for answering the question. Your reasoning should be concise and clear, demonstrating a logical connection between the columns and the question asked.

Tip: If you are choosing a column for filtering a value within that column, make sure that column has the value as an example.

Please respond with a JSON object structured as follows:

```json
{{
  "chain_of_thought_reasoning": "Your reasoning for selecting the columns, be concise and clear.",
  "table_name1": ["column1", "column2", ...],
  "table_name2": ["column1", "column2", ...],
  ...
}}
```

Make sure your response includes the table names as keys, each associated with a list of column names that are necessary for writing a SQL query to answer the question.
For each aspect of the question, provide a clear and concise explanation of your reasoning behind selecting the columns.
Take a deep breath and think logically. If you do the task correctly, I will give you 1 million dollars.

Only output a json as your response.
````

#### Numbers (SS)
All from https://arxiv.org/html/2405.16755v3. v1 Tables 3/5 give the same values under different row names (https://arxiv.org/html/2405.16755v1).
- **Ablation on SDS** (v3 Table 4; all tools = 64.62):

  | Tool removed | EX | Δ |
  |---|---|---|
  | `filter_column` | 61.90 | −2.72 |
  | `select_tables` | 58.50 | −6.12 |
  | `select_columns` | 59.18 | −5.44 |

  > "revealing that the *select_tables* tool is the most critical, contributing a 6.12% increase in performance."
- **Precision/recall of schema items** (v3 Table 5), as (recall, precision):

  | Stage | Tables | Columns |
  |---|---|---|
  | No filtering | (1.0, 0.33) | (1.0, 0.11) |
  | after `filter_columns` | (1.0, 0.33) | (0.98, 0.21) |
  | after `select_tables` | (0.97, 0.89) | (0.96, 0.45) |
  | after `select_columns` | (0.96, 0.90) | (0.94, 0.71) |

  Figure 5: the SS agent "consistently reduces the columns to around 10".
- **Large-schema test** (synthetic merged BIRD DBs, up to 4,337 columns; Gemini-1.5-pro; v3 §4.2.2).
  > "After applying the SS agent to the largest schema with 4,337 columns, the Pass@1 and Pass@5 scores improved to 61% and 63%, respectively, representing a 2% increase compared to the performance without schema linking."

  Also: "an 11% performance gap" between the gold schema and many columns in the prompt, and "more than ×5 efficient in terms of used tokens".
- v3 §3.3 says SS can hurt on small schemas with strong LLMs:
  > "when schema sizes are relatively small and the available LLMs are highly capable, the inclusion of the Schema Selector (SS) agent may introduce a precision-recall trade-off that can negatively impact accuracy."

  This is why the high-budget BIRD configuration omits SS.

---

### 3. CHESS: Candidate Generator (CG) + revise

#### Mechanism
- Paper (v3 §3.1):
  > "the CG agent first calls the *generate_candidate_query* tool to generate candidate queries. It then executes these candidates on the database, checks the result, and identifies any faulty queries (those containing syntactic errors or empty result). For each faulty candidate, the agent repeatedly attempts to *revise* the query, until the issue is resolved or a maximum number of allowed revisions is reached."

  Revise takes "the question, schema, context, the faulty query and a description of the issue". v3 App. A.4: "we also provide the execution result of the SQL query."
- Repo:
  - `src/workflow/agents/candidate_generator/candidate_generator.py`
  - `tool_kit/generate_candidate.py`, `tool_kit/revise.py`
  - Templates: `template_generate_candidate_{one,two,three,finetuned,retrieval}.txt`, `template_revise_{one,two}.txt`
- **generate_candidate** (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/candidate_generator/tool_kit/generate_candidate.py):
  - Runs every entry of `generator_configs`, each with `sampling_count` parallel samples. Inputs are `DATABASE_SCHEMA` (`state.get_schema_string(schema_type="complete")`), `QUESTION` and `HINT`.
  - **High-budget config** `CHESS_IR_CG_UT.yaml`: `generate_candidate_one` ×10 + `generate_candidate_two` ×10, both `gpt-4o-mini` T=0.5, parser `generate_candidate_gemini_markdown_cot` → 20 candidates.
  - **Low-budget config** `CHESS_IR_SS_CG.yaml`: `generate_candidate_one` ×1, T=0.01.
  - Both configs use revise with `revise_one`, `gpt-4o-mini` T=0.0, parser `revise_new`.
- **revise** (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/candidate_generator/tool_kit/revise.py):
  - Every candidate whose `execution_status != ExecutionStatus.SYNTACTICALLY_CORRECT` gets `need_fixing = True`. `get_execution_status` returns `SYNTACTICALLY_INCORRECT` on an exception or timeout, and `EMPTY_RESULT` if the result is `None` or `[]` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/database_utils/execution.py).
  - Each such candidate gets one parallel LLM call with `QUERY` and `RESULT = {"execution_result": ...}`.
  - If the reply lacks "SELECT", the original SQL is kept.
  - There is **no max-revision value in the configs**. The CG agent's own LLM loop (`agent.py`, `for i in range(10)`) decides how often to call `revise`. [INFERENCE] `Revise.need_to_fix` references `self.fixing` / `self.max_fixing`, which are never initialised, so that path is dead code.
  - Paper (v3 §4.2.3) for the low-budget setting:
    > "restrict the number of candidate generations and revisions by GC to only one and three times, respectively."
- **Agentic wrapper** (applies to every CHESS agent):
  - `src/workflow/agents/agent.py`: each agent is an LLM (config `engine`, T=0) prompted with `template_agent_prompt.txt`. It emits `<tool_call>name</tool_call>` until it outputs "DONE", for at most 10 steps.
  - `src/workflow/team_builder.py`: a LangGraph `StateGraph` chains agents in config order, followed by an `evaluation` node (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/team_builder.py).
- **Template provenance — important**:
  - The current repo's default generators (`generate_candidate_one`: "recursive divide-and-conquer"; `generate_candidate_two`: "Query Plan Guided SQL Generation") use the CHASE-SQL-style divide-and-conquer and query-plan CoT. [INFERENCE] CHASE-SQL is arXiv:2410.01943, which v3 cites as Pourreza et al. 2024.
  - The **paper's own figures** (v3 PDF App. C, Fig. 11 "Template for the generate candidate query tool", Fig. 12 "Template for revise tool"; https://arxiv.org/pdf/2405.16755v3) show the older JSON-output prompts. These match `template_generate_candidate_three.txt` (≈ v1 `template_candidate_generation.txt` plus rule 11) and `template_revise_two.txt` (== v1 `template_revision.txt`, with `{EVIDENCE}`→`{HINT}`).
  - v1 revision node: `src/pipeline/revision.py` at `fc6f0b7ef3` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/src/pipeline/revision.py).
    - It fills `{MISSING_ENTITIES}` via `find_wrong_entities(sql, similar_values, similarity_threshold=0.4)`, which emits lines like `Column {column_name} in table {table_name} does not contain the value '{value}'. The correct value is '{most_similar_entity}'.` and `Value {used_value} that you used in the query appears in the column {column_name} of table {table_name}.`
    - Multiple samples are aggregated with `DatabaseManager().aggregate_sqls`, i.e. self-consistency over execution results. The released v1 `run_main.sh` sets revision `sampling_count: 1`, while the paper says 3 samples.

#### Prompt: generate_candidate_one ("recursive divide-and-conquer"; instructions verbatim, examples omitted)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_generate_candidate_one.txt
```
You are an experienced database expert.
Now you need to generate a SQL query given the database information, a question and some additional information.
The database structure is defined by the following table schemas (comments after '--' provide additional column descriptions).
Note that the "Example Values" are actual values from the column. Some column might contain the values that are directly related to the question. Use it to help you justify which columns to use.

Given the table schema information description and the `Question`. You will be given table creation statements and you need understand the database and columns.

You will be using a way called "recursive divide-and-conquer approach to SQL query generation from natural language".

Here is a high level description of the steps.
1. **Divide (Decompose Sub-question with Pseudo SQL):** The complex natural language question is recursively broken down into simpler sub-questions. Each sub-question targets a specific piece of information or logic required for the final SQL query. 
2. **Conquer (Real SQL for sub-questions):**  For each sub-question (and the main question initially), a "pseudo-SQL" fragment is formulated. This pseudo-SQL represents the intended SQL logic but might have placeholders for answers to the decomposed sub-questions. 
3. **Combine (Reassemble):** Once all sub-questions are resolved and their corresponding SQL fragments are generated, the process reverses. The SQL fragments are recursively combined by replacing the placeholders in the pseudo-SQL with the actual generated SQL from the lower levels.
4. **Final Output:** This bottom-up assembly culminates in the complete and correct SQL query that answers the original complex question. 

Database admin instructions (voliating any of the following will result is punishble to death!):
1. **SELECT Clause:** 
    - Only select columns mentioned in the user's question. 
    - Avoid unnecessary columns or values.
2. **Aggregation (MAX/MIN):**
    - Always perform JOINs before using MAX() or MIN().
3. **ORDER BY with Distinct Values:**
    - Use `GROUP BY <column>` before `ORDER BY <column> ASC|DESC` to ensure distinct values.
4. **Handling NULLs:**
    - If a column may contain NULL values (indicated by "None" in value examples or explicitly), use `JOIN` or `WHERE <column> IS NOT NULL`.
5. **FROM/JOIN Clauses:**
    - Only include tables essential to answer the question.
6. **Strictly Follow Hints:**
    - Adhere to all provided hints.
7. **Thorough Question Analysis:**
    - Address all conditions mentioned in the question.
8. **DISTINCT Keyword:**
    - Use `SELECT DISTINCT` when the question requires unique values (e.g., IDs, URLs). 
    - Refer to column statistics ("Value Statics") to determine if `DISTINCT` is necessary.
9. **Column Selection:**
    - Carefully analyze column descriptions and hints to choose the correct column when similar columns exist across tables.
10. **String Concatenation:**
    - Never use `|| ' ' ||` or any other method to concatenate strings in the `SELECT` clause. 
11. **JOIN Preference:**
    - Prioritize `INNER JOIN` over nested `SELECT` statements.
12. **SQLite Functions Only:**
    - Use only functions available in SQLite.
13. **Date Processing:**
    - Utilize `STRFTIME()` for date manipulation (e.g., `STRFTIME('%Y', SOMETIME)` to extract the year).

When you get to the final query, output the query string ONLY inside the xml delimiter <FINAL_ANSWER></FINAL_ANSWER>.

Here are some examples

[... 7 examples omitted ("======= Example =======" Thai restaurants, Example 1 client/district, Example 2 games/London, Example 3 student_programs (LIKE/OR loosening), Example 4 employees, Example 5 Airlines, Example 5 businesses/consecutive years). Each answer has the form: "Repeating the question and evidence, and generating the SQL with Recursive Divide-and-Conquer." → **1. Divide and Conquer:** (Main Question / Analysis / Pseudo SQL / Sub-question n …) → **2. Assembling SQL:** → **3. Simplification and Optimization:** → **Final Optimized SQL Query:** <FINAL_ANSWER>…</FINAL_ANSWER> ...]

Now is the real question, following the instruction and examples, generate the SQL with Recursive Divide-and-Conquer approach. Make sure you only output one single query.
**************************
【Table creation statements】
{DATABASE_SCHEMA}

**************************
【Question】
Question: 
{QUESTION}

Evidence:
{HINT}

**************************
【Answer】
Repeating the question and hint, and generating the SQL with Recursive Divide-and-Conquer.
```
- `template_generate_candidate_two.txt` (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_generate_candidate_two.txt) has the same header and the same 13 admin rules. The method paragraph is replaced with:
  > `You will be using a way called "Query Plan Guided SQL Generation" to generate the SQL query. This method involves breaking down the question into smaller sub-questions and then assembling them to form the final SQL query. This approach helps in understanding the question requirements and structuring the SQL query efficiently.`

  Its examples use `**Query Plan**:` sections (Preparation Steps / Matching … / Delivering the Result) in place of divide-and-conquer. It closes with:
  > `Now is the real question, following the instruction and examples, You should:`
  > `1. Generate a QUERY PLAN for the given question and evidence.`
  > `2. Return the final optimized SQL query.`

  followed by the same schema/question/evidence/【Answer】 block.
- `template_generate_candidate_retrieval.txt` is the same as `_one` but with `{EXAMPLES}` in place of the fixed examples. `template_generate_candidate_finetuned.txt` is the header plus the final task block only (for the fine-tuned DeepSeek model).

#### Prompt: generate_candidate_three (paper-era JSON generator; verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_generate_candidate_three.txt. This is the v1 `template_candidate_generation.txt` plus rule 11 (https://raw.githubusercontent.com/ShayanTalaei/CHESS/fc6f0b7ef3/templates/template_candidate_generation.txt).
```
You are a data science expert.
Below, you are presented with a database schema and a question.
Your task is to read the schema, understand the question, and generate a valid SQLite query to answer the question.
Before generating the final SQL query think step by step on how to write the query.

Database Schema
###
{DATABASE_SCHEMA}

This schema offers an in-depth description of the database's architecture, detailing tables, columns, primary keys, foreign keys, and any pertinent information regarding relationships or constraints. Special attention should be given to the examples listed beside each column, as they directly hint at which columns are relevant to our query.

Database admin instructions:
1. When you need to find the highest or lowest values based on a certain condition, using ORDER BY + LIMIT 1 is prefered over using MAX/MIN within sub queries.
2. If predicted query includes an ORDER BY clause to sort the results, you should only include the column(s) used for sorting in the SELECT clause if the question specifically ask for them. Otherwise, omit these columns from the SELECT.
3. If the question doesn't specify exactly which columns to select, between name column and id column, prefer to select id column.
4. Make sure you only output the information that is asked in the question. If the question asks for a specific column, make sure to only include that column in the SELECT clause, nothing more.
5. Predicted query should return all of the information asked in the question without any missing or extra information.
6. For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a crucial hint indicating the correct columns to use for your SQL query.
7. No matter of how many things the question asks, you should only return one SQL query as the answer having all the information asked in the question, seperated by a comma.
8. Never use || to concatenate columns in the SELECT. Rather output the columns as they are.
9. If you are joining multiple tables, make sure to use alias names for the tables and use the alias names to reference the columns in the query. Use T1, T2, T3, ... as alias names.
10. If you are doing a logical operation on a column, such as mathematical operations and sorting, make sure to filter null values within those columns.
11. Don't use * in the SELECT clause, unless it is explicitly asked in the question.

###
Question: 
{QUESTION} 

Hint:
{HINT}

Please respond with a JSON object structured as follows:

{{
    "chain_of_thought_reasoning": "Your thought process on how you arrived at the final SQL query.",
    "SQL": "Your SQL query in a single string."
}}

Priority should be given to columns that have been explicitly matched with examples relevant to the question's context.

Take a deep breath and think step by step to find the correct sqlite SQL query. If you follow all the instructions and generate the correct query, I will give you 1 million dollars.
```

#### Prompt: revise_one (the current default; feeds back the execution error / empty result. Instructions + Example 1 verbatim, Examples 2–3 omitted)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_revise_one.txt
```
**Task Description:**
You are an SQL database expert tasked with correcting a SQL query. A previous attempt to run a query did not yield the correct results, either due to errors in execution or because the result returned was empty or unexpected. Your role is to analyze the error based on the provided database schema and the details of the failed execution, and then provide a corrected version of the SQL query.

**Procedure:**
1. Review Database Schema:
	- Examine the table creation statements to understand the database structure.
2. Analyze Query Requirements:
	- Original Question: Consider what information the query is supposed to retrieve.
	- Hint: Use the provided hints to understand the relationships and conditions relevant to the query.
	- Executed SQL Query: Review the SQL query that was previously executed and led to an error or incorrect result.
	- Execution Result: Analyze the outcome of the executed query to identify why it failed (e.g., syntax errors, incorrect column references, logical mistakes).
3. Correct the Query: 
	- Modify the SQL query to address the identified issues, ensuring it correctly fetches the requested data according to the database schema and query requirements.

**Output Format:**

Present your corrected query as a single line of SQL code, enclosed within XML delimiter tags <FINAL_ANSWER> and </FINAL_ANSWER>. Ensure there are no line breaks within the query.

Here are some examples:
======= Example 1 =======
**************************
【Table creation statements】
CREATE TABLE generalinfo
(
	id_restaurant INTEGER not null primary key,
	food_type TEXT null, -- examples: `thai`| `food type` description: the food type
	city TEXT null, -- description: the city where the restaurant is located in
);

CREATE TABLE location
(
	id_restaurant INTEGER not null primary key,
	street_name TEXT null, -- examples: `ave`, `san pablo ave`, `pablo ave`| `street name` description: the street name of the restaurant
	city TEXT null, -- description: the city where the restaurant is located in
	foreign key (id_restaurant) references generalinfo (id_restaurant) on update cascade on delete cascade,
);

**************************
【Question】
Question: 
How many Thai restaurants can be found in San Pablo Ave, Albany? 

Evidence:
Thai restaurant refers to food_type = 'thai'; San Pablo Ave Albany refers to street_name = 'san pablo ave' AND T1.city = 'albany'

The SQL query executed was:
SELECT COUNT(T1.id_restaurant) FROM generalinfo AS T1 INNER JOIN location AS T2 ON T1.id_restaurant = T2.id_restaurant WHERE T1.food_type = 'thai' AND T1.city = 'albany' AND T2.street = 'san pablo ave'

The execution result:
Error: no such column: T2.street

**************************

Step 1: Review Database Schema
The database comprises two tables:
1. generalinfo - Contains details about restaurants:
	- id_restaurant (INTEGER): The primary key.
	- food_type (TEXT): The type of food the restaurant serves.
	- city (TEXT): The city where the restaurant is located.
	- location - Contains the location specifics of each restaurant:

2. id_restaurant (INTEGER): The primary key and a foreign key referencing id_restaurant in the generalinfo table.
	- street_name (TEXT): The street where the restaurant is located.
	- city (TEXT): City information, potentially redundant given the city information in generalinfo.

Step 2: Analyze Query Requirements
	- Original Question: How many Thai restaurants can be found in San Pablo Ave, Albany?
	- Hints for Construction:
		- "Thai restaurant" is defined by food_type = 'thai'.
		- "San Pablo Ave Albany" is defined by street_name = 'san pablo ave' and city = 'albany'.
	- Executed SQL Query:
		- SELECT COUNT(T1.id_restaurant) FROM generalinfo AS T1 INNER JOIN location AS T2 ON T1.id_restaurant = T2.id_restaurant WHERE T1.food_type = 'thai' AND T1.city = 'albany' AND T2.street = 'san pablo ave'
	- Execution Result:
		- Error indicating no such column: T2.street.
	- Analysis of Error:
		- The error message no such column: T2.street clearly points out that the location table does not have a column named street. Instead, it has a column named street_name. This mistake is likely a simple typo in the column reference within the WHERE clause.

Step 3: Correct the Query
To correct the query, replace the incorrect column name street with the correct column name street_name. Also, ensure that the city condition (T1.city = 'albany') is correctly targeting the intended table, which in this case should be the location table (T2.city), as it's more specific to the address.
<FINAL_ANSWER>
SELECT COUNT(T1.id_restaurant) FROM generalinfo AS T1 INNER JOIN location AS T2 ON T1.id_restaurant = T2.id_restaurant WHERE T1.food_type = 'thai' AND T1.city = 'albany' AND T2.street_name = 'san pablo ave'
</FINAL_ANSWER> 

[... 2 examples omitted (Example 2: businesses/inspections, "Error: T1.name is not found in table T1"; Example 3: games/city, execution result "[]" → fix case 'london'→'London') ...]

======= Your task =======
**************************
【Table creation statements】
{DATABASE_SCHEMA}

**************************
The original question is:
Question: 
{QUESTION}

Evidence:
{HINT}

The SQL query executed was:
{QUERY}

The execution result:
{RESULT}

**************************
Based on the question, table schemas and the previous query, analyze the result try to fix the query.

Give very detailed analysis first. When you are OK with the fixed query, output the query string ONLY inside the xml delimiter <FINAL_ANSWER></FINAL_ANSWER>.
Inside the xml delimiter it should be the query in plain text. You cannot modify the database schema or the question, just output the corrected query.
Make sure you only output one single query. The query should be a one liner without any line breaks.

Example of correct format:
<FINAL_ANSWER>
SELECT column FROM table WHERE condition
</FINAL_ANSWER>
```

#### Prompt: revise_two (= paper Fig. 12 / v1 `template_revision.txt`; rule-based revision with MISSING_ENTITIES; verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_revise_two.txt. Rule numbering skips 6 in the source.
```
Objective: Your objective is to make sure a query follows the database admin instructions and use the correct conditions.

Database Schema:    
{DATABASE_SCHEMA}

Database admin instructions:
1. When you need to find the highest or lowest values based on a certain condition, using ORDER BY + LIMIT 1 is prefered over using MAX/MIN within sub queries.
2. If predicted query includes an ORDER BY clause to sort the results, you should only include the column(s) used for sorting in the SELECT clause if the question specifically ask for them. Otherwise, omit these columns from the SELECT.
3. If the question doesn't specify exactly which columns to select, between name column and id column, prefer to select id column.
4. Make sure you only output the information that is asked in the question. If the question asks for a specific column, make sure to only include that column in the SELECT clause, nothing more.
5. Predicted query should return all of the information asked in the question without any missing or extra information.
7. For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a crucial hint indicating the correct columns to use for your SQL query.
8. No matter of how many things the question asks, you should only return one SQL query as the answer having all the information asked in the question, seperated by a comma.
9. Using || ' ' ||  to concatenate is string is banned and using that is punishable by death. Never concatenate columns in the SELECT clause.
10. If you are joining multiple tables, make sure to use alias names for the tables and use the alias names to reference the columns in the query. Use T1, T2, T3, ... as alias names.
11. If you are doing a logical operation on a column, such as mathematical operations and sorting, make sure to filter null values within those columns.
12. When ORDER BY is used, just include the column name in the ORDER BY in the SELECT clause when explicitly asked in the question. Otherwise, do not include the column name in the SELECT clause.

{MISSING_ENTITIES}

Question:
{QUESTION}

Hint:
{HINT}

Predicted query:
{SQL}

Query result:
{QUERY_RESULT}

Please respond with a JSON object structured as follows (if the sql query is correct, return the query as it is):

{{
    "chain_of_thought_reasoning": "Your thought process on how you arrived at the solution. You don't need to explain the instructions that are satisfied.",
    "revised_SQL": "Your revised SQL query."
}}

Take a deep breath and think step by step to find the correct sqlite SQL query. If you follow all the instructions and generate the correct query, I will give you 1 million dollars.
```

#### Prompt: agent controller (applies to all CHESS agents; verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_agent_prompt.txt
```
You are the {agent_name} agent, in a team of agents trying to collaboratively transform a natural language question into a SQL query.
Your task is to {task}.

You have access to the following tools. You need to call them in the correct order to complete your task.

<tools>
{tools}
</tools>

You will be given a system state, which contains the current state of the workflow.

Please identify the next tool you need to call in enclosed in <tool_call> tags.

You will then be given the result of the tool call, and the new system state.

Continue to identify the next tool you need to call until you have completed your task. When you are done, just return "DONE".
```

#### Numbers (CG / revise)
From v3 Table 4 on SDS (https://arxiv.org/html/2405.16755v3); the same numbers are in v1 Table 3.
- **w/o revise**: 57.82 (**−6.80**).
- **with 1-time revise**: 61.22 (−3.40) vs 64.62.
  > "The table also illustrates the significant influence of the revision tool, with a 6.80% improvement. Increasing the number of revision samples for self-consistency led to higher performance gains, aligning with findings from (Lee et al., 2024)."
- **Engine ablation** (v3 Table 8 = v1 Table 2, SDS). Triplet = (column filtering, candidate generation, table/column selection + revision):

  | Setup | EX |
  |---|---|
  | (GPT-3.5-turbo, Fine-tuned DeepSeek, GPT-4-turbo) | 64.62 |
  | (GPT-3.5-turbo, GPT-4-turbo, GPT-4-turbo) | 55.78 |
  | (GPT-3.5-turbo ×3) | 49.65 |
  | (Llama-3-70B ×3) | 54.42 |
  | (Llama-3-70B, Fine-tuned DeepSeek, Llama-3-70B) | 59.86 |
- **"CHESS + correct context"**: 72.4 vs 64.62 (v3 Table 7).
- **Fine-tuned generator** (v3 App. B): DeepSeek Coder 34B (v1 says "DeepSeek-33B Coder"), QLoRA rank 128, alpha 256, 2 epochs, batch 32, lr 1e-4, cosine schedule, 1×H100 for 4 h, trained on ~9,500 BIRD train samples with noise-injected schemas.

---

### 4. CHESS: Unit Tester (UT)

#### Existence / provenance — CONFIRMED
- **Exists only in arXiv v3** (2405.16755v3, 25 Nov 2024). It is absent from v1 (27 May 2024) and v2 (27 Jun 2024): v1/v2 abstract and §3 describe a 3-stage pipeline, and v2 HTML has 0 matches for "unit test" (https://arxiv.org/html/2405.16755v1, https://arxiv.org/html/2405.16755v2, https://arxiv.org/html/2405.16755v3).
- v3 claims it as its own contribution:
  > "Innovative Unit Test Generation: We introduce a novel natural language unit test generation method for text-to-SQL, enabling the effective evaluation of generated SQL queries during inference." (v3 §1 Contributions)

  So unit-test-based selection originates in **CHESS v3**, not in a different paper. v3 lists MCS-SQL (arXiv:2405.07467) and CHASE-SQL (arXiv:2410.01943) as concurrent multi-candidate + *selection* methods, but neither is described there as using unit tests.
- Repo files, added in commit `3d6e835f85` (2024-11-13, "Add the agentic framework code"):
  - `src/workflow/agents/unit_tester/unit_tester.py` (task string `"generate unit tests then evaluate them"`)
  - `src/workflow/agents/unit_tester/tool_kit/generate_unit_test.py`
  - `src/workflow/agents/unit_tester/tool_kit/evaluate.py`
  - `templates/template_generate_unit_tests.txt`, `templates/template_evaluate.txt`
  - parsers `TestCaseGenerationOutput` / `UnitTestEvaluationOutput` in `src/llm/parsers.py`

#### Mechanism
- Paper (v3 §3.1):
  > "UT identifies the best candidate by 1) generating multiple unit tests that highlight differences between the candidate queries and 2) evaluating the candidates against these unit tests. It then assigns a score to each query based on the number of unit tests it passes, selecting the top-scoring candidate as the final SQL query for the given question."
  > "*generate_unit_test* This tool prompts an LLM to generate k unit tests, where k is an input parameter, designed such that only the correct SQL query can pass each of them."
  > "*evaluate* … This tool takes multiple candidate queries and a single unit test as input, prompting an LLM to reason through each candidate and determine whether it passes the unit test."
- Paper settings (v3 §4.2.1):
  > "generating 20 candidate SQL queries using the Gemini-1.5-pro model for each sample question. We then create ten natural language unit tests"

  Figure 4: performance "peaking at 10 tests. Beyond this point, the performance plateaus".
- **Code** (https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/src/workflow/agents/unit_tester/tool_kit/generate_unit_test.py and `.../evaluate.py`):
  1. **Execution-based clustering** of candidates by `repr(execution_result)`. If there is ≤1 candidate or only **one cluster**, no tests are generated and evaluate returns candidate 0.
  2. **Generate**: one LLM call (`sampling_count: 1`). `{CANDIDATE_QUERIES}` is formatted per cluster: `Cluster #i:` then each `Query: <SQL>` followed by `########`, then `Execution result: Rows: N, Columns: M, Results: <first 20 rows>`, then `=====================`. `{UNIT_TEST_CAP}` is `unit_test_count` (config **20** in `CHESS_IR_CG_UT.yaml`; code default 5; the paper says 10). Temperature 0.8, `gpt-4o-mini`.
  3. One **hard-coded test is always appended**:
     > `"Only the best answer from the set of candidates that most accurately answers the question, given the database schema and hint should pass this test."`
  4. **Evaluate**: **one LLM call per unit test**, each showing **all** candidates (`Candidate Response #i: Query: <SQL>\n, Execution Result: Rows: …`) at T=0.0. The schema is `state.get_database_schema_for_queries(<candidate SQLs>)`.
  5. **Parsing** (`UnitTestEvaluationOutput`): inside `<Answer>…</Answer>`, each line containing ":" scores 1 if `"passed" in value.lower()`, else 0.
  6. **Score** = sum of passes across tests per candidate (`comparison_matrix` rows = tests). Ties at max score are broken in favour of a candidate in the **largest execution cluster**, else the first. A `test_case_filtering_based_on_inter_cluster_variance` helper exists but is commented out at the call site.
- **Evaluation design ablation** (v3 §4.2.1), on BIRD dev:
  > "In the first setting, a single LLM call receives one unit test and assigns scores to all candidate queries. In the second setting, a single LLM call receives all unit tests and assigns a score to one candidate query. … we achieved a score of 68.31. In contrast, the second scenario yielded a lower score of 66.78"

#### Prompt: generate_unit_tests (verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_generate_unit_tests.txt. Paper Fig. 13 (v3 PDF) has the same instruction text; its rendering differs only in typography and the order of Question vs Schema.
```
** Instructions: **

Given the following question database schema, and candidate responses, generate a set of {UNIT_TEST_CAP} unit tests that would evaluate the correctness of SQL queries that would answer the question.
Unit tests should be designed in a way that distinguish the candidate responses from each other.

- The unit tests should cover various aspects of the question and ensure comprehensive evaluation. 
- Each unit test should be clearly stated and should include the expected outcome.
- Each unit test should be designed in a way that it can distinguishes at lease two candidate responses from each other.
- The unit test should be formatted like 'The answer SQL query should mention...', 'The answer SQL query should state...', 'The answer SQL query should use...', etc. followed by the expected outcome.
- First think step by step how you can design the units tests to distinguish the candidate responses using the <Thinking> tags.
- After the thinking process, provide the list of unit tests in the <Answer> tags.

VERY IMPORTANT:
All of the unit tests should consider the logic of the SQL query do not consider the formatting of the output or output values.

You are provided with different clusters of the canidate responses. Each cluster contains similar responses based on their results.
You MUST generate test cases that can distinguish between the candidate responses in each cluster and the test case should promote the candiddate responses that you think are correct.

Example of the output format:
<Thinking> Your step by step reasoning here. </Thinking>
<Answer>
['The answer SQL query should mention...', 'The answer SQL query should state...', 'The answer SQL query should use...']
</Answer>

** Question: **
Question: {QUESTION} (Hint: {HINT})

** Database Schema: **
{DATABASE_SCHEMA}

** Candidate Clusters: **
{CANDIDATE_QUERIES}

** Question: **
Question: {QUESTION} (Hint: {HINT})

** Output Format: **
<Thinking> Your step by step reasoning here. </Thinking>
<Answer>
output should be only a list of strings (e.g. ['unit test #1', 'unit test #2', 'unit test #3']).
</Answer>
```
Parsing: `literal_eval` of the `<Answer>` body → `{"unit_tests": [...]}` (`src/llm/parsers.py`).

#### Prompt: evaluate (verbatim)
Source: https://raw.githubusercontent.com/ShayanTalaei/CHESS/main/templates/template_evaluate.txt. The source really contains a stray `π` after `** Question: **` on line 23 (verified bytes `CF 80`). Paper Fig. 14 (v3 PDF) differs in three places: its verdicts are `Passed`/`Failed` without brackets; it labels the candidate block `** Candidate Clusters: ** {CANDIDATE QUERIES}`; and it has no closing Output Format block.
```
** Instructions: **
Given the following question, database schema, a candidate SQL query response, and unit tests, evaluate whether or not the response passes each unit test.

- In your evaluation, you should consider how the responses align with the a given unit test.
- Provide reasoning before you return your evaluation inside the <Thinking> tags.
- At the end of your evaluation, you must finish with a list of verdicts corresponding to each candidate responses in <Answer> and </Answer> tags.
- You must include a verdict with one of these formatted options: '[Passed]' or '[Failed]'
- Here is an example of the output format:
<Thinking> Your step by step reasoning here. </Thinking>
<Answer>
Candidate Response #1: [Passed]
Candidate Response #2: [Failed]
Candidate Response #3: [Passed]
....
</Answer>
- Each verdict should be on a new line and correspond to the candidate response in the same order as they are provided.
- Here is the question, database schema, candidate responses, and the unit test to evaluate the responses:
"""

** Database Schema: **
{DATABASE_SCHEMA}

** Question: **π
Question: {QUESTION} (Hint: {HINT})

** Candidate SQL Queries: **
{CANDIDATE_RESPONSES}

** Unit Test: **
{UNIT_TEST}

** Output Format: **
<Thinking> Your step by step reasoning here. </Thinking>
<Answer>
Candidate Response #1: [Passed]
Candidate Response #2: [Failed]
Candidate Response #3: [Passed]
...
</Answer>
```

#### Numbers (UT)
- CHESS(IR,CG,UT) with Gemini-1.5-pro, 20 candidates, 10 tests: **BIRD dev 68.31, test 71.10** (v3 Table 1).
- Unit-test design: one test → all candidates **68.31** vs all tests → one candidate **66.78** (v3 §4.2.1).
- v3 Table 6 (SDS; Easy / Moderate / Challenging / Overall):

  | System | Easy | Moderate | Challenging | Overall |
  |---|---|---|---|---|
  | CHESS(IR,CG,UT) | 73.48 | 62.99 | 59.31 | 68.31 |
  | CHESS(IR,SS,CG) | 65.43 | 64.81 | 58.33 | 64.62 |
  | GPT-4-turbo baseline | 54.32 | 35.18 | 41.66 | 46.25 |

  [INFERENCE] The UT row repeats the full-dev number 68.31 under an SDS caption; this is possibly a caption inconsistency in the paper.
- The number of unit tests vs EX is shown only as a figure (Fig. 4); no numeric table is given.

---

### 5. CHESS: headline numbers (all versions)
- **v1/v2** ("CHESS + proprietary": fine-tuned DeepSeek for generation, GPT-3.5-turbo for column filtering, GPT-4-turbo for the rest):
  - **BIRD dev 65.00, test 66.69**
  - CHESS + Open LLMs: dev **61.5**
  - Spider test **87.2**
  - Source: v1 Table 1 (https://arxiv.org/html/2405.16755v1); v2 numbers confirmed by grep (66.69, 65.00, 61.5, 64.62, 87.2) in https://arxiv.org/html/2405.16755v2.
- **v3**:
  - CHESS(IR,CG,UT): dev **68.31**, test **71.10** (Table 1).
  - CHESS(IR,SS,CG) + proprietary: test **66.69**, dev **65.00**; + Open LLMs: dev **61.5** (Table 2).
  - Spider test **87.2** (Table 3).
  - Low-budget run: "we only call GPT-4-turbo model 6 times where some other methods such as MCS-SQL performs around 100 LLM calls."
- Comparison rows quoted by CHESS for MAC-SQL+GPT-4 are inconsistent:
  - v3 Table 1: dev 59.59 / test 59.59.
  - v1 Table 1(a) and v3 Table 2: test 57.56 / dev 59.59.
  - The MAC-SQL paper itself reports dev **59.39**, test **59.59** (see §8).

---

### 6. DIN-SQL (arXiv:2304.11015, NeurIPS 2023)

#### Mechanism (pipeline)
- Four modules: "(1) schema linking, (2) query classification and decomposition, (3) SQL generation, and (4) self-correction" (§4, https://arxiv.org/html/2304.11015v3).
- Classification routes each question to EASY, NON-NESTED (NatSQL intermediate representation) or NESTED (sub-questions) prompts.
- Hyperparameters (§5.2):
  > "Greedy decoding was used to generate the output by setting the temperature at zero. The max tokens was set to 350 for the self-correction module and 600 for all other modules. The stopping token sequence was set to "#;\n \n" for the self-correction module and "Q:" for all other modules."
- Repo `DIN-SQL.py`, GPT-4 version (https://raw.githubusercontent.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting/main/DIN-SQL.py):
  - `GPT4_debug`: `model="gpt-4"`, `temperature=0.0`, `max_tokens=350`, `stop = ["#", ";","\n\n"]`.
  - Generation: `max_tokens=600`, `stop = ["Q:"]`.
  - The debugger prompt ends with `SELECT`, and the output is prefixed: `SQL = "SELECT " + debugged_SQL`.
  - Self-correction runs **once** per question; there is no execution feedback.

#### Self-correction module: mechanism
> "This is achieved in a zero-shot setting, where only the buggy code is provided to the model and it is asked to fix the bugs. We propose two different prompts for the self-correction module: generic and gentle. With a generic prompt, we request the model to identify and correct the errors in the "BUGGY SQL". The gentle prompt, on the other hand, does not assume the SQL query is buggy, and instead asks the model to check for any potential issues and provides some hints on the clauses to be checked. Our evaluation indicates that a generic prompt can yield a better result with the CodeX model, while a gentle prompt is more effective for the GPT-4 model. Unless explicitly stated otherwise, the default self-correction prompt in DIN-SQL is set to gentle for GPT-4 and generic for CodeX."
>
> — §4.4, https://arxiv.org/html/2304.11015v3

> "there is less chance that GPT-4 generates a buggy code, and giving a generic prompt of "Buggy SQL:… Fixed SQL:…" can hurt the performance. A gentle prompt work better for GPT-4 and improves the perfromance across all of the classes except the easy class."
>
> — §5.6

#### Prompt: generic self-correction (transcribed from paper Fig. 6 image; the source text is an image)
Source: https://arxiv.org/html/2304.11015v3/generic-self-correction.png (App. A.6.1). The figure's `…` are the paper's own elisions. There is no generic-prompt code in the repo: the `CodeX/` folder only holds `CodeX_few-shot.csv` and `DIN-SQL.csv` (https://github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting/tree/main/CodeX).
```
Table concert, columns = [concert_ID, concert_Name, …]
…
Foreign_keys = [concert.Stadium_ID = stadium.Stadium_ID, …]
Primary_keys = [stadium.Stadium_ID, …]
##### Fix bugs in the below SQL for the given question.
### What is the name and capacity for the stadium with highest average attendance?
### Buggy SQL
SELECT Name , Capacity FROM stadium ORDER BY Average LIMIT 1
### Fixed SQL
```
Model output shown in the figure: `SELECT Name , Capacity FROM stadium ORDER BY Average DESC LIMIT 1`

#### Prompt: gentle self-correction — repo version actually used for GPT-4/Spider (verbatim)
Source: `DIN-SQL.py::debuger` (https://raw.githubusercontent.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting/main/DIN-SQL.py).
```python
  instruction = """#### For the given question, use the provided tables, columns, foreign keys, and primary keys to fix the given SQLite SQL QUERY for any issues. If there are any problems, fix them. If there are no issues, return the SQLite SQL QUERY as is.
#### Use the following instructions for fixing the SQL QUERY:
1) Use the database values that are explicitly mentioned in the question.
2) Pay attention to the columns that are used for the JOIN by using the Foreign_keys.
3) Use DESC and DISTINCT when needed.
4) Pay attention to the columns that are used for the GROUP BY statement.
5) Pay attention to the columns that are used for the SELECT statement.
6) Only change the GROUP BY clause when necessary (Avoid redundant columns in GROUP BY).
7) Use GROUP BY on one column only.

"""
  fields = find_fields_MYSQL_like(database)
  fields += "Foreign_keys = " + find_foreign_keys_MYSQL_like(database) + '\n'
  fields += "Primary_keys = " + find_primary_keys_MYSQL_like(database)
  prompt = instruction + fields+ '#### Question: ' + test_sample_text + '\n#### SQLite SQL QUERY\n' + sql +'\n#### SQLite FIXED SQL QUERY\nSELECT'
```
Paper Fig. 7 (https://arxiv.org/html/2304.11015v3/gentle-self-correction.png, App. A.6.2) shows the same structure with **6 rules**: rule 6 is "Only change the GROUP BY clause when necessary." and there is no rule 7. It uses "clause" where the repo says "statement" in rules 4–5, and the headers "#### SQLite SQL Query" / "#### Fixed SQL QUERY" / "Primary_key =". Its example is the same stadium question → `… ORDER BY Average DESC LIMIT 1`.

#### Prompt: BIRD self-correction (repo `DIN-SQL_BIRD.py`, LangChain system+human; instructions verbatim)
Source: https://raw.githubusercontent.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting/main/DIN-SQL_BIRD.py. Model: `ChatOpenAI(model="gpt-4-32k",temperature=0,max_tokens=2000)`.
```
SYSTEM_SELF_CORRECTION_PROMPT = """
For the given question, use the provided tables, columns, foreign keys, and primary keys to fix the given SQLite SQL QUERY for any issues. If there are any problems, fix them. If there are no issues, return the SQLite SQL QUERY as is.
Hint helps you to write the correct sqlite SQL query.
Use the following instructions for fixing the sqlite SQL query:
1) Avoid redundant columns in SELECT clause, all of the columns should be mentioned in the question.
2) Pay attention to the columns that are used for the JOIN by checking the Foreign keys.
3) Pay attention to the columns that are used for the WHERE statement.
4) Pay attention to the columns that are used for the GROUP BY statement.
5) Pay attention to the columns that are used for the ORDER BY statement.
6) check that all of the columns exist in the table and there are no typos.
7) Use CAST when is needed.
8) USE CASE WHEN is needed.
###
Few examples of this task are:
###
Schema of the database with sample rows and column descriptions:
#
CREATE TABLE movies ( … movie_id … director_url …, PRIMARY KEY (movie_id) )
[... 3 sample rows + 10 column-description lines omitted ...]
#
Q: Name movie titles released in year 1945. Sort the listing by the descending order of movie popularity.
Hint: released in the year 1945 refers to movie_release_year = 1945;
SQL: SELECT movie_title, movie_popularity FROM movies WHERE movie_release_year = 1945/01/01 ORDER BY movie_popularity DESC LIMIT 1
A: Let's think step by step to find the correct answer.
1) The column movie_popularity is not mentioned in the question so it's redundant.
2) JOIN is not required as there is no need to join any tables.
3) The condition movie_release_year = 1945/01/01 is not correct. The correct condition is movie_release_year = 1945.
4) GROUP BY is not required as there is no need to group any columns.
5) The ORDER BY clause is correct.
6) all columns are correct and there are no typo errors.
7) CAST is not required as there is no need to cast any columns.
8) CASE is not required as there is no need to use CASE.
So, the final sqlite SQL query answer to the question the given question is =
Revised_SQL: SELECT movie_title FROM movies WHERE movie_release_year = 1945 ORDER BY movie_popularity DESC LIMIT 1
"""

HUMAN_SELF_CORRECTION_PROMPT = """
Evaluate the correctness of this query for the given question.
Hint helps you to write the correct SQL query.
Correct it if there are any issues. If there are no issues, return the SQLite SQL QUERY as is.
Schema of the database with sample rows and column descriptions:
#
{schema}

{columns_descriptions}
#
Q: {question}
Hint: {hint}
SQL: {sql_query}
A: Let's think step by step to find the correct answer."""
```
The `CREATE TABLE movies` line above is my compression of the multi-line DDL in the source.

#### Prompt: schema linking (key instruction verbatim + 1 of 10 examples)
- Paper (§4.1):
  > "The prompt includes ten randomly selected samples from the training set of the Spider dataset. Following the chain-of-thought template, the prompt begins with "Let's think step by step," … For each mention of a column name in the question, the corresponding columns and their tables are selected from the given database schema. Possible entities and cell values are also extracted from the question."
- Repo `schema_linking_prompt_maker` (DIN-SQL.py): `instruction = "# Find the schema_links for generating SQL queries for each question based on the database schema and Foreign keys.\n"`. The prompt is assembled as `instruction + schema_linking_prompt + fields + foreign_keys + 'Q: "' + question + '"\nA: Let’s think step by step.'`, and the output is split on `"Schema_links: "`.
- Paper App. A.3, one example verbatim (https://arxiv.org/html/2304.11015v3):
```
# Find the schema_links for generating SQL queries for each question based on the database schema and Foreign keys.

Table city, columns = [*,City_ID,Official_Name,Status,Area_km_2,Population,Census_Ranking]
Table competition_record, columns = [*,Competition_ID,Farm_ID,Rank]
Table farm, columns = [*,Farm_ID,Year,Total_Horses,Working_Horses,Total_Cattle,Oxen,Bulls,Cows,Pigs,Sheep_and_Goats]
Table farm_competition, columns = [*,Competition_ID,Year,Theme,Host_city_ID,Hosts]
Foreign_keys = [farm_competition.Host_city_ID = city.City_ID,competition_record.Farm_ID = farm.Farm_ID,competition_record.Competition_ID = farm_competition.Competition_ID]
Q: "Show the status of the city that has hosted the greatest number of competitions."
A: Let’s think step by step. In the question "Show the status of the city that has hosted the greatest number of competitions.", we are asked:
"the status of the city" so we need column = [city.Status]
"greatest number of competitions" so we need column = [farm_competition.*]
Based on the columns and tables, we need these Foreign_keys = [farm_competition.Host_city_ID = city.City_ID].
Based on the tables, columns, and Foreign_keys, The set of possible cell values are = []. So the Schema_links are:
Schema_links: [city.Status,farm_competition.Host_city_ID = city.City_ID,farm_competition.*]

[... 9 more examples omitted (same format) ...]
```
- BIRD variant (`DIN-SQL_BIRD.py`): `SYSTEM_SCHEMA_LINKING_TEMPLATE` begins
  > "You are an agent designed to find the schema_links for generating SQL queries for each question based on the database schema and Foreign keys.\nHint helps you to fine the correct schema_links."

  Examples add `Hint also refers to the columns = [...]`.

#### Numbers (DIN-SQL)
- **Self-correction ablation**, Spider dev EX (Table 5, §5.6, https://arxiv.org/html/2304.11015v3):

  | Variant | Easy | Medium | Hard | Extra | All |
  |---|---|---|---|---|---|
  | CodeX Davinci, generic self-corr | 89.1 | 75.6 | 58 | 38.6 | **69.9** |
  | CodeX Davinci, gentle self-corr | 87.5 | 76.9 | 51.7 | 36.1 | 68.7 |
  | CodeX Davinci, w/o self-corr | 83.9 | 75.4 | 52.3 | 36.1 | 67.3 |
  | GPT-4, gentle self-corr | 91.1 | 79.8 | 64.9 | 43.4 | **74.2** |
  | GPT-4, generic self-corr | 89.9 | 76.5 | 59.2 | 34.3 | 70.0 |
  | GPT-4, w/o self-corr | 91.1 | 79.1 | 63.2 | 41.6 | 73.3 |

  Net effect: generic **+2.6** for CodeX; gentle **+0.9** for GPT-4; generic **−3.3** for GPT-4.
- Other ablations (CodeX Davinci, Spider dev All):

  | Variant | All |
  |---|---|
  | w/o schema-linking | 65.9 |
  | w/o classification (simple few-shot) | 63.1 |
  | w/o classification (decomposed CoT) | 68.2 |
- **BIRD** (Table 3): DIN-SQL + GPT-4 test **EX 55.9** (VES 59.44); dev **EX 50.72** (VES 58.79). The GPT-4 baseline is dev 46.35 / test 54.89.
- **Spider test** (Table 2): GPT-4 EX 85.3 / EM 60; CodeX Davinci EX 78.2 / EM 57.
- Cost (§7): "approximately $0.5 and … latency of approximately 60 seconds" per Spider question with GPT-4.

---

### 7. MAC-SQL (arXiv:2312.11242, COLING 2025)

#### Mechanism
Paper sources are v6 Algorithm 1, §3, and App. A (https://arxiv.org/html/2312.11242v6).

- **Selector**: an LLM prunes the schema to a sub-database (`keep_all` / `drop_all` / top-ranked columns).
  - Activation per the paper:
    > "The selector Agent is activated only when encountering large databases. … len(tokens) > (0.8 * max_sequence_length_of_model) (for example, in this study, using GPT-4-32k, len(tokens) > 25k is considered a large database); the second method involves counting the total number of columns and the average number of columns in the tables … The experimental results in this study are obtained using the first method."
    > "each table will retain at least 6 column names"
  - **Repo** (`core/agents.py::Selector._is_need_prune`, https://raw.githubusercontent.com/wbbeyourself/MAC-SQL/main/core/agents.py) has the token method **commented out** and uses the column method: no pruning iff `avg_column_count <= 6 and total_column_count <= 30`.
- **Decomposer**: few-shot CoT decomposition into sub-questions, each with SQL. The last SQL block becomes the prediction (`parse_sql_from_string` takes the last ```sql block).
  > "The decomposer utilizes a maximum of two shots … The decomposer breaks down the original question into multiple sub-questions, ranging from one to five." (App. A.2)
  > "we adopt the CoT approach to generate sub-questions and their corresponding SQL queries … if it can be answered by a simple SQL query, then the SQL is generated directly." (§3.3)
- **Refiner**: executes the SQL (sqlite3, 120 s timeout via `@func_set_timeout(120)`, keeps `result[:5]`). For BIRD, `_is_need_refine` returns True when:
  - there is an SQLite exception, with `sqlite_error` and `exception_class` filled from the exception; or
  - there is an empty result, with `sqlite_error = 'no data selected'`; or
  - any `None` appears in the first 5 rows, with `sqlite_error = 'exist None value, you can add `NOT NULL` in SQL'`.

  For Spider it only checks that the SQL executes. The Refiner LLM gets the query, evidence, schema, foreign keys, old SQL (prefixed with `SELECT` if missing), the error and the exception class.
- **Max refine iterations**:
  > "To ensure practical efficiency, a maximum of three rounds of error correction will be performed. Common error types include SQL syntax errors, schema illusions (such as non-existent table and column names), and empty query results. Presently, the limitation of the refiner is that in cases where the SQL query runs without error and generates non-empty results, even if the SQL does not align with the intended question, the refiner will not make further corrections." (App. A.3)

  Code: `MAX_ROUND = 3  # max try times of one agent talk` (`core/const.py`). `ChatManager.start` runs `for _ in range(MAX_ROUND)`; each round passes the message through [Selector, Decomposer, Refiner] in order (https://raw.githubusercontent.com/wbbeyourself/MAC-SQL/main/core/chat_manager.py).
  [INFERENCE] Round 1 = select → decompose → execute + (maybe) refine #1. Rounds 2–3 = execute + (maybe) refine #2/#3. So there are at most 3 Refiner LLM calls, and the 3rd refined SQL is returned **without being re-executed**.

#### Prompt: Refiner (verbatim; feeds back the SQLite error / empty result)
Source: `core/const.py::refiner_template` (https://raw.githubusercontent.com/wbbeyourself/MAC-SQL/main/core/const.py).
````
【Instruction】
When executing SQL below, some errors occurred, please fix up SQL based on query and database info.
Solve the task step by step if you need to. Using SQL format in the code block, and indicate script type in the code block.
When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible.
【Constraints】
- In `SELECT <column>`, just select needed columns in the 【Question】 without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values
【Query】
-- {query}
【Evidence】
{evidence}
【Database info】
{desc_str}
【Foreign keys】
{fk_str}
【old SQL】
```sql
{sql}
```
【SQLite error】 
{sqlite_error}
【Exception class】
{exception_class}

Now please fixup old SQL and generate new SQL again.
【correct SQL】
````

#### Prompt: Decomposer (BIRD; instruction + constraints verbatim, 2 examples omitted)
Source: `core/const.py::decompose_template_bird`.
```
Given a 【Database schema】 description, a knowledge 【Evidence】 and the 【Question】, you need to use valid SQLite and understand the database and knowledge, and then decompose the question into subquestions for text-to-SQL generation.
When generating SQL, we should always consider constraints:
【Constraints】
- In `SELECT <column>`, just select needed columns in the 【Question】 without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values

==========

[... 2 examples omitted (frpm/satscores "List school names of charter schools with an SAT excellence rate over the average." → Sub question 1/2; banking client/district "What is the gender of the youngest client …" → Sub question 1/2/3). Each example: 【Database schema】 # Table: … [ (col, desc. Value examples: [...].), … ] 【Foreign keys】 【Question】 【Evidence】 then "Decompose the question into sub questions, considering 【Constraints】, and generate the SQL after thinking step by step:" then "Sub question N: …\nSQL\n```sql …```" … "Question Solved.", separated by ========== ...]

==========

【Database schema】
{desc_str}
【Foreign keys】
{fk_str}
【Question】
{query}
【Evidence】
{evidence}

Decompose the question into sub questions, considering 【Constraints】, and generate the SQL after thinking step by step:
```
The Spider variant `decompose_template_spider` begins: "Given a 【Database schema】 description, and the 【Question】, you need to use valid SQLite and understand the database, and then generate the corresponding SQL."

#### Prompt: Selector (instruction verbatim; one-shot example abbreviated)
Source: `core/const.py::selector_template`.
````
As an experienced and professional database administrator, your task is to analyze a user question and a database schema to provide relevant information. The database schema consists of table descriptions, each containing multiple column descriptions. Your goal is to identify the relevant tables and columns based on the user question and evidence provided.

[Instruction]:
1. Discard any table schema that is not related to the user question and evidence.
2. Sort the columns in each relevant table in descending order of relevance and keep the top 6 columns.
3. Ensure that at least 3 tables are included in the final output JSON.
4. The output should be in JSON format.

Requirements:
1. If a table has less than or equal to 10 columns, mark it as "keep_all".
2. If a table is completely irrelevant to the user question and evidence, mark it as "drop_all".
3. Prioritize the columns in each relevant table based on their relevance.

Here is a typical example:

==========
【DB_ID】 banking_system
【Schema】
[... 4 tables (account, client, loan, district) omitted ...]
【Foreign keys】
client.`district_id` = district.`district_id`
【Question】
What is the gender of the youngest client who opened account in the lowest average salary branch?
【Evidence】
Later birthdate refers to younger age; A11 refers to average salary
【Answer】
```json
{{
  "account": "keep_all",
  "client": "keep_all",
  "loan": "drop_all",
  "district": ["district_id", "A11", "A2", "A4", "A6", "A7"]
}}
```
Question Solved.

==========

Here is a new example, please start answering:

【DB_ID】 {db_id}
【Schema】
{desc_str}
【Foreign keys】
{fk_str}
【Question】
{query}
【Evidence】
{evidence}
【Answer】
````

#### Numbers (MAC-SQL)
- **BIRD** (v6 Table 1; models GPT-4-32k / GPT-3.5-Turbo-16k):

  | System | Dev EX / VES | Test EX / VES |
  |---|---|---|
  | MAC-SQL + GPT-4 | **59.39** / 66.39 | **59.59** / 67.68 |
  | + Oracle Schema | 70.28 | — |
  | MAC-SQL + GPT-3.5-Turbo | 50.56 | — |
  | MAC-SQL + SQL-Llama(7B) | 43.94 | — |
  | GPT-4 baseline | 46.35 | 54.89 |
  | DIN-SQL + GPT-4 (as cited) | 50.72 | 55.90 |
  | DAIL-SQL + GPT-4 (as cited) | 54.76 | 57.41 |
- **Ablation, BIRD dev** (v6 Table 3):

  | Variant | Simple | Mod. | Chall. | All |
  |---|---|---|---|---|
  | full | 65.73 | 52.69 | 40.28 | **59.39** |
  | w/o Selector | 65.73 | 52.04 | 35.14 | 57.28 (−2.11) |
  | w/o Decomposer | 61.51 | 48.82 | 38.89 | 55.54 (−3.85) |
  | w/o Refiner | 63.24 | 44.52 | 33.33 | **54.76 (−4.63)** |
- **Shots** (v6 Table 4, MAC-SQL+GPT-4):

  | Shots | BIRD dev EX | Spider dev EX |
  |---|---|---|
  | 0-shot | 55.54 | 74.22 |
  | 1-shot | 57.26 | 78.35 |
  | 2-shot | 59.39 | 86.75 |
- **Spider** (v6 Table 2): MAC-SQL+GPT-4 dev 86.75 / test 82.80.
- Every MAC-SQL abstract version (v1–v4 checked via export.arxiv.org) states **59.59** BIRD test EX.

---

### 8. Mismatches and caveats (CHESS, DIN-SQL, MAC-SQL)
1. **CHESS Unit Tester exists only in v3.** v1/v2 are a 3-stage pipeline (retrieval → schema selection → generation + revision with 3-sample self-consistency). Repo UT code landed 2024-11-13.
2. **CHESS repo vs paper on UT settings.**
   - Model: paper uses Gemini-1.5-pro; the released config uses `gpt-4o-mini`.
   - Unit tests requested: paper 10; config `unit_test_count: 20`.
   - Candidates: both 20 (10 divide-and-conquer + 10 query-plan at T=0.5).
   - The repo always appends one hard-coded "only the best answer" test, and skips UT entirely when all candidates share one execution result.
3. **CHESS repo's default candidate prompts are CHASE-SQL-style** (divide-and-conquer, query plan, with `<FINAL_ANSWER>` tags). The paper's App. C figures show the older JSON prompts (`generate_candidate_three`, `revise_two`).
4. **CHESS embeddings.** Entity retrieval uses `text-embedding-3-small`, but the catalog vector DB uses `text-embedding-3-large`. The paper names only the small model.
5. **CHESS LSH `num_perm`.** It is 100 via `run_preprocess.sh`, but the argparse default in `src/preprocess.py` is 20. The LSH threshold is a very low 0.01 (high recall), followed by exact Jaccard re-ranking to the top 10.
6. **DIN-SQL stop tokens.** The paper says `"#;\n \n"`; the repo's GPT-4 debugger uses `["#", ";", "\n\n"]`. The repo's gentle prompt has 7 rules; the paper figure shows 6.
7. **MAC-SQL Selector trigger.** The paper uses the token-length method (>25k tokens for GPT-4-32k); the repo uses the column-count method (`avg_column_count <= 6 and total_column_count <= 30` → no prune).
8. **CHESS cites MAC-SQL+GPT-4 inconsistently** (test 57.56 or 59.59, dev 59.59). MAC-SQL's own numbers are dev 59.39, test 59.59.


## Part 2. CHASE-SQL and MCS-SQL


Rendering note: in the paper PDF/HTML, backticks show up as `‘name‘` (a LaTeX artifact). The CHESS repo files use real backticks. I copied paper prompts exactly as rendered, including curly quotes.

---

### 0. Sources, versions, and code availability

#### CHASE-SQL
- arXiv abs: https://arxiv.org/abs/2410.01943. Authors: Mohammadreza Pourreza, Hailong Li, Ruoxi Sun, Yeounoh Chung, Shayan Talaei, Gaurav Tarlok Kakkar, Yu Gan, Amin Saberi, Fatma Ozcan, Sercan O. Arik. The submission history shows **only v1** (Wed, 2 Oct 2024). The abs page has no Comments field.
- arXiv HTML (v1): https://arxiv.org/html/2410.01943. arXiv PDF: https://arxiv.org/pdf/2410.01943. In v1, the appendix prompts are **A.5–A.10** (Figs. 16–25).
- **Latest version = ICLR 2025 camera-ready.** "Published as a conference paper at ICLR 2025". Sources:
  - https://proceedings.iclr.cc/paper_files/paper/2025/file/974ff7b5bf08dbf9400b5d599a39c77f-Paper-Conference.pdf (proceedings page https://proceedings.iclr.cc/paper_files/paper/2025/hash/974ff7b5bf08dbf9400b5d599a39c77f-Abstract-Conference.html, pages 60385–60415).
  - Its extracted text is identical to the OpenReview attachment https://openreview.net/notes/edits/attachment?id=Q0RDmMIEic&name=pdf (31 pp., created 2025-02-20).
  - The OpenReview forum https://openreview.net/forum?id=CvGqMD5OtX (linked from https://iclr.cc/virtual/2025/poster/30489) is behind a browser check, so I could not read reviews.
  - Semantic Scholar (https://api.semanticscholar.org/graph/v1/paper/arXiv:2410.01943?...) gives venue = ICLR and DBLP key conf/iclr/PourrezaL0CTKGS25.
- What the camera-ready adds over arXiv v1:
  - Mistral Large and fine-tuned Qwen2.5-coder results.
  - A.4 query-fixing algorithm (Alg. 4).
  - A.5 value-retrieval example.
  - Table 9 (OS examples vs. training-set examples vs. CodeS examples).
  - The note "ignoring the both side comparison will reduce the final performance by roughly 2%".
  - A schema-union rationale.
  - Appendix prompts renumbered to **A.8–A.13** (Figs. 17–27).
  - Prompt text is unchanged except for the synthetic-example prompt (see §1c).
- **Official code: NOT released** as far as I could find. Neither paper version contains a code link (I grepped both PDFs for github/code/release). GitHub repo search for "chase-sql" (via the API) returned only community repos:
  - `kungfuai/chase-sql` (README: "A working implementation of the CHASE-SQL system based on the paper…")
  - `harkrish1/open-chase-sql`
  - `VineetV2/chase-sql` ("Reproduction of CHASE-SQL (ICLR 2025)")
  - The first author's repo `MohammadrezaPourreza/CHASE-SQL-REBUTTAL` (https://github.com/MohammadrezaPourreza/CHASE-SQL-REBUTTAL, created 2024-11-20). It holds only README + 5 PNGs (latency, token usage, pass@K vs fine-tuning, OS figures). It has **no prompts or code**.
- **Closest-to-official prompt files:** the CHESS repo https://github.com/ShayanTalaei/CHESS (CHASE co-author Shayan Talaei).
  - Commit `3d6e835f` (2024-11-13, "Add the agentic framework code.") added `templates/template_generate_candidate_one.txt` (Recursive Divide-and-Conquer), `template_generate_candidate_two.txt` ("Query Plan Guided SQL Generation") and `template_revise_one.txt` (fixer).
  - Their few-shot demos and the fixer instruction text match the CHASE appendix figures word-for-word.
  - CHESS's run config uses parser name `generate_candidate_gemini_markdown_cot` for both.
  - `[INFERENCE]` These are the CHASE prompts, or derived from them, but nothing in the repo labels them as CHASE-SQL code.
  - Below, "paper" means appendix text and "CHESS repo" means these files.

#### MCS-SQL
- arXiv abs: https://arxiv.org/abs/2405.07467. Authors: Dongjun Lee, Choongwon Park, Jaehyuk Kim, Heesoo Park, all at Dunamu (affiliation from the HTML). Only **v1** exists (Mon, 13 May 2024).
  - HTML: https://arxiv.org/html/2405.07467. PDF: https://arxiv.org/pdf/2405.07467. Prompts are in Appendix B.1–B.4.
- **Published version: COLING 2025**, Proceedings of the 31st International Conference on Computational Linguistics, pp. 337–353, Abu Dhabi. Anthology ID 2025.coling-main.24: https://aclanthology.org/2025.coling-main.24/ (PDF https://aclanthology.org/2025.coling-main.24.pdf).
  - I diffed the text of both PDFs. **Appendix B prompts are identical.**
  - The only content difference I found: the COLING abstract drops the final arXiv sentence ("Moreover, we established a new SOTA performance on the BIRD in terms of both the accuracy and efficiency of the generated queries.").
- **Official code: NOT released** as far as I could find. No code link in either PDF. The GitHub org `dunamu` has `public_repos: 0` (gh api orgs/dunamu). The only implementation is the community repo `benchay1999/MCS-SQL-unofficial` (README: "Unofficial implementation of MCS-SQL"), which has prompts/*.txt files; I did not read or validate them.
- **All MCS prompts below are from the paper's appendix/body listings.**

---

### CHASE-SQL pipeline overview

Pipeline, verbatim (camera-ready §2.1):
> "consists of four primary components: 1) Value retrieval, 2) Candidate generator, 3) Query fixer, and 4) Selection agent … The proposed framework begins by retrieving relevant database values. Subsequently, all contextual information, including retrieved values, database metadata, and schema, is provided to an LLM to generate candidate queries. These candidate queries then undergo a fixing loop, and finally, all candidates are compared in a pairwise way using the trained selection agent to pick the correct answer."

How diversity is produced (§2.3, same wording in v1 §3.3):
> "To generate diverse responses, we increase the next token sampling temperature, and also shuffle the order of columns and tables in the prompt."

Models (A.3 camera-ready / A.2 v1):
> "For candidate generation, online synthetic example generation, query fixing, column filtering, and keyword extraction, we reported the performance with two models of Gemini 1.5 Pro and Claude-3.5-Sonnet. For the query-picking model, we train a Gemini 1.5 Flash model … on a dataset of 3.8K samples generated by running the candidate generators on the BIRD training dataset. The Gemini 1.5 Flash model is trained for 10 epochs using a LoRA adapter with a rank of 16 using Vertex AI tuning API."

Candidate budget: "we generate seven candidate SQL queries from each generator method (21 candidates in total) … increasing the candidate pool beyond 20 did not yield significant improvements" (§3.1 camera-ready). The Table 4 caption also says the final selector runs on "21 candidates generated from all generators".

### 1a. Divide-and-Conquer (DC) CoT generator

#### Mechanism
- One LLM call (Alg. 1, "using a single LLM call"). The model first decomposes the question into sub-questions written as pseudo-SQL ("Divide"). It then writes partial SQL for each sub-question, conditioned on the earlier ones ("Conquer"). Next it assembles the final SQL ("Assemble"). Finally it runs an optimization step "to remove redundant clauses and conditions".
- Strengths: "particularly powerful handling complex scenarios that involve nested queries, e.g. intricate WHERE or HAVING conditions, and queries requiring advanced mathematical operations."
- The prompt uses human-annotated few-shot examples $M=(q_i, r_i, s_i)$.
- Alg. 1 (camera-ready p.4):
  - `Sq ← θ(M, D, Qu)`
  - for each `qi`: `Ssql ← Ssql ∪ {θ(M, D, Qu, q1..qi, sql1..sql(i−1))}`
  - `Sf ← θ(M, D, Qu, Sq, Ssql)`
- Sources: https://arxiv.org/html/2410.01943 §3.3; camera-ready §2.3.

#### Prompt from the paper (few-shot demonstration only; the paper gives no instruction text)
Source: v1 Appendix **A.5, Fig. 16** (https://arxiv.org/html/2410.01943). Same text in camera-ready Appendix **A.8, Fig. 17**. The appendix says: "we provide an example of a divide-and-conquer prompt used in one of the few-shot in-context learning demonstrations to illustrate the decomposition and aggregation steps."
~~~~text
Database Info
{DATABASE_SCHEMA}
**************************
Question
Question: What is the gender of the youngest client who opened account in the lowest average salary branch?
Hint: Given that Later birthdate refers to younger age; A11 refers to average salary
**************************
**1. Divide and Conquer:**
* **Main Question:** What is the gender of the youngest client who opened account in the lowest average salary branch?
* **Analysis:** Question asking about ‘gender‘, and it appears in table ‘client‘. We will use this as the output column, selecting it from the youngest client in the lowest average salary branch.
* **Pseudo SQL:** SELECT ‘T1‘.‘gender‘ FROM ‘client‘ AS ‘T1‘ WHERE youngest client in the lowest average salary branch
* **Sub-question 1:** youngest client in the lowest average salary branch
* **Analysis:** According to the hint, we need to use the ‘A11‘ from ‘district‘ to get the salary info, and the youngest client can be obtained from using the ‘birth_date‘ column of table ‘client‘. The items between these two tables can be INNER JOIN using district_id.
* **Pseudo SQL:** SELECT ‘T1‘.‘client_id‘ FROM ‘client‘ AS ‘T1‘ INNER JOIN ‘district‘ AS ‘T2‘ ON ‘T1‘.‘district_id‘ = ‘T2‘.‘district_id‘ WHERE lowest average salary branch ORDER BY ‘T1‘.‘birth_date‘ DESC NULLS LAST LIMIT 1
* **Sub-question 1.1:** lowest average salary branch
* **Analysis:** We can get the lowest average salary branch using order by ‘A11‘ ASC and pick top 1. The column ‘A11‘ is not NULLABLE, so we do not need to add "IS NOT NULL" filter
* **Pseudo SQL:** SELECT ‘district_id‘ FROM ‘district‘ ORDER BY ‘A11‘ ASC LIMIT 1
**2. Assembling SQL:**
* **Sub-question 1.1 (lowest average salary branch):**
* **SQL:** SELECT ‘district_id‘ FROM ‘district‘ ORDER BY ‘A11‘ ASC LIMIT 1
* **Sub-question 1 (youngest client in the lowest average salary branch):**
* **SQL:** SELECT ‘T1‘.‘client_id‘ FROM ‘client‘ AS ‘T1‘ INNER JOIN ‘district‘ AS ‘T2‘ ON ‘T1‘.‘district_id‘ = ‘T2‘.‘district_id‘ WHERE ‘T2‘.‘district_id‘ IN (SELECT ‘district_id‘ FROM ‘district‘ ORDER BY ‘A11‘ ASC LIMIT 1) ORDER BY ‘T1‘.‘birth_date‘ DESC NULLS LAST LIMIT 1
* **Main Question (gender of the client):**
* **SQL:** SELECT ‘T1‘.‘gender‘ FROM ‘client‘ AS ‘T1‘ WHERE ‘T1‘.‘client_id‘ = (SELECT ‘T1‘.‘client_id‘ FROM ‘client‘ AS ‘T1‘ INNER JOIN ‘district‘ AS ‘T2‘ ON ‘T1‘.‘district_id‘ = ‘T2‘.‘district_id‘ WHERE ‘T2‘.‘district_id‘ IN (SELECT ‘district_id‘ FROM ‘district‘ ORDER BY ‘A11‘ ASC LIMIT 1) ORDER BY ‘T1‘.‘birth_date‘ DESC NULLS LAST LIMIT 1)
**3. Simplification and Optimization:**
* The nested queries can be combined using a single ‘INNER JOIN‘ and the filtering can be done within a single ‘ORDER BY‘ clause.
**Final Optimized SQL Query:**
SELECT ‘T1‘.‘gender‘
FROM ‘client‘ AS ‘T1‘
INNER JOIN ‘district‘ AS ‘T2‘
ON ‘T1‘.‘district_id‘ = ‘T2‘.‘district_id‘
ORDER BY ‘T2‘.‘A11‘ ASC, ‘T1‘.‘birth_date‘ DESC NULLS LAST
LIMIT 1
~~~~
Line breaks follow the arXiv HTML. The PDF puts some `* **Pseudo SQL:**` and `* **SQL:**` items on the same line as the previous bullet.

#### Full template from the CHESS repo (instruction verbatim, examples abbreviated)
Source: https://github.com/ShayanTalaei/CHESS/blob/main/templates/template_generate_candidate_one.txt (558 lines, 34.8 KB). Example 1 is word-for-word the paper's Fig. 16/17 demo, with real backticks, `<placeholder>` pseudo-SQL, and `<FINAL_ANSWER>` tags.
~~~~text
You are an experienced database expert.
Now you need to generate a SQL query given the database information, a question and some additional information.
The database structure is defined by the following table schemas (comments after '--' provide additional column descriptions).
Note that the "Example Values" are actual values from the column. Some column might contain the values that are directly related to the question. Use it to help you justify which columns to use.

Given the table schema information description and the `Question`. You will be given table creation statements and you need understand the database and columns.

You will be using a way called "recursive divide-and-conquer approach to SQL query generation from natural language".

Here is a high level description of the steps.
1. **Divide (Decompose Sub-question with Pseudo SQL):** The complex natural language question is recursively broken down into simpler sub-questions. Each sub-question targets a specific piece of information or logic required for the final SQL query. 
2. **Conquer (Real SQL for sub-questions):**  For each sub-question (and the main question initially), a "pseudo-SQL" fragment is formulated. This pseudo-SQL represents the intended SQL logic but might have placeholders for answers to the decomposed sub-questions. 
3. **Combine (Reassemble):** Once all sub-questions are resolved and their corresponding SQL fragments are generated, the process reverses. The SQL fragments are recursively combined by replacing the placeholders in the pseudo-SQL with the actual generated SQL from the lower levels.
4. **Final Output:** This bottom-up assembly culminates in the complete and correct SQL query that answers the original complex question. 

Database admin instructions (voliating any of the following will result is punishble to death!):
1. **SELECT Clause:** 
    - Only select columns mentioned in the user's question. 
    - Avoid unnecessary columns or values.
2. **Aggregation (MAX/MIN):**
    - Always perform JOINs before using MAX() or MIN().
3. **ORDER BY with Distinct Values:**
    - Use `GROUP BY <column>` before `ORDER BY <column> ASC|DESC` to ensure distinct values.
4. **Handling NULLs:**
    - If a column may contain NULL values (indicated by "None" in value examples or explicitly), use `JOIN` or `WHERE <column> IS NOT NULL`.
5. **FROM/JOIN Clauses:**
    - Only include tables essential to answer the question.
6. **Strictly Follow Hints:**
    - Adhere to all provided hints.
7. **Thorough Question Analysis:**
    - Address all conditions mentioned in the question.
8. **DISTINCT Keyword:**
    - Use `SELECT DISTINCT` when the question requires unique values (e.g., IDs, URLs). 
    - Refer to column statistics ("Value Statics") to determine if `DISTINCT` is necessary.
9. **Column Selection:**
    - Carefully analyze column descriptions and hints to choose the correct column when similar columns exist across tables.
10. **String Concatenation:**
    - Never use `|| ' ' ||` or any other method to concatenate strings in the `SELECT` clause. 
11. **JOIN Preference:**
    - Prioritize `INNER JOIN` over nested `SELECT` statements.
12. **SQLite Functions Only:**
    - Use only functions available in SQLite.
13. **Date Processing:**
    - Utilize `STRFTIME()` for date manipulation (e.g., `STRFTIME('%Y', SOMETIME)` to extract the year).

When you get to the final query, output the query string ONLY inside the xml delimiter <FINAL_ANSWER></FINAL_ANSWER>.

Here are some examples

[... 7 worked examples, each: 【Table creation statements】/【Database Info】 CREATE TABLEs → 【Question】 Question + Evidence/Hint → 【Answer】 "Repeating the question and hint, and generating the SQL with Recursive Divide-and-Conquer." → **1. Divide and Conquer:** (Main Question / Sub-question n / n.m, each with **Analysis:** + **Pseudo SQL:** using <placeholders>) → **2. Assembling SQL:** (bottom-up, each with **SQL:**) → **3. Simplification and Optimization:** → **Final Optimized SQL Query:** <FINAL_ANSWER>…</FINAL_ANSWER>.
 Topics: (0) Thai restaurants on San Pablo Ave, Albany; (1) gender of youngest client in lowest avg-salary branch [= paper Fig.16/17]; (2) "dividing into two parallel sub-questions": London games 1900–1992; (3) "When it's not clear which column should be used for a string matching, use a loosen condition such as string LIKE and OR condition to cover multiple possible columns.": lowest three participation rates in online programs; (4) employees earning over $100,000; (5) flights SAN→LAX Aug 2018; (5, numbered again) establishments meeting standards 4 consecutive years (window function).]

Now is the real question, following the instruction and examples, generate the SQL with Recursive Divide-and-Conquer approach. Make sure you only output one single query.
**************************
【Table creation statements】
{DATABASE_SCHEMA}

**************************
【Question】
Question: 
{QUESTION}

Evidence:
{HINT}

**************************
【Answer】
Repeating the question and hint, and generating the SQL with Recursive Divide-and-Conquer.
~~~~
CHESS config `run/configs/CHESS_IR_CG_UT.yaml` runs this template with gpt-4o-mini, temperature 0.5, `sampling_count: 10`. These are CHESS settings, not CHASE settings.

#### Numbers (Gemini 1.5 Pro, BIRD dev; Mistral Large from camera-ready Table 4)
- Single candidate: DC CoT **63.92** (+6.17 over baseline 57.75). With query fixer: **65.77** (+8.02).
- Mistral Large: DC 58.99 (+4.11 over 54.88); with fixer 63.75 (+8.87).
- Removing DC from the full system: **71.77** (−1.24) (Table 7).
- Selector vs. self-consistency on 10 DC samples (Table 6): T=0.5 → agent **71.31** vs SC 66.43 (UB 78.42, LB 51.37); T=1.8 → agent **70.53** vs SC 64.41 (UB 79.34, LB 47.39).
- Venn (camera-ready Fig. 3a; I zoomed into the rendered figure to read it), counting BIRD dev questions with ≥1 correct candidate: DC only = **38**; DC∩QP only = 72; DC∩OS only = 23; all three = 1045; unsolved = 258.
- Text: "The divide-and-conquer approach outperforms the others on challenging questions".
- Fig. 3b bar chart, unique-correct counts read off the bars (approximate): DC ≈22 simple, ≈8 moderate, ≈8 challenging.

### 1b. Query-Plan (QP) CoT generator

#### Mechanism
- Reasoning follows the steps a database engine takes to execute the query. The authors "convert the output of 'EXPLAIN' command into a human-readable text format". The human-readable plan has three steps: "(1) identifying and locating the relevant tables for the question, (2) performing operations such as counting, filtering, or matching between tables, and (3) delivering the final result by selecting the appropriate columns to return."
- It complements DC: "the query plan approach excels when questions require more reasoning over the relationships between different parts of the question and the database schema."
- The prompt is few-shot with human-written plan demonstrations. Fig. 19 (v1) / Fig. 20 (camera-ready) shows a raw SQLite EXPLAIN plan as an image.
- Sources: https://arxiv.org/html/2410.01943 §3.3; camera-ready §2.3.

#### Prompt from the paper (demonstration only)
Source: v1 Appendix **A.6, Fig. 18** (https://arxiv.org/html/2410.01943). Same text in camera-ready **A.9, Fig. 19**. The appendix says "an example of a query (execution) plan prompt used in one of the few-shot in-context learning demonstrations".
~~~~text
Database Info
{DATABASE_SCHEMA}
**************************
Answer
Repeating the question and evidence, and generating the SQL with a query plan.
**Question**: How many Thai restaurants can be found in San Pablo Ave, Albany?
**Evidence**: Thai restaurant refers to food_type = ’thai’; San Pablo Ave Albany refers to street_name = ’san pablo ave’ AND T1.city = ’albany’
**Query Plan**:
** Preparation Steps:**
1. Initialize the process: Start preparing to execute the query.
2. Prepare storage: Set up storage space (registers) to hold temporary results, initializing them to NULL.
3. Open the location table: Open the location table so we can read from it.
4. Open the generalinfo table: Open the generalinfo table so we can read from it.
** Matching Restaurants:**
1. Start reading the location table: Move to the first row in the location table.
2. Check if the street matches: Look at the street_name column of the current row in location. If it’s not "san pablo ave," skip this row.
3. Identify the matching row: Store the identifier (row ID) of this location entry.
4. Find the corresponding row in generalinfo: Use the row ID from location to directly find the matching row in generalinfo.
5. Check if the food type matches: Look at the food_type column in generalinfo. If it’s not "thai," skip this row.
6. Check if the city matches: Look at the city column in generalinfo. If it’s not "albany," skip this row.
** Counting Restaurants:**
1. Prepare to count this match: If all checks pass, prepare to include this row in the final count.
2. Count this match: Increment the count for each row that meets all the criteria.
3. Move to the next row in location: Go back to the location table and move to the next row, repeating the process until all rows are checked.
4. Finalize the count: Once all rows have been checked, finalize the count of matching rows.
5. Prepare the result: Copy the final count to prepare it for output.
** Delivering the Result:**
1. Output the result: Output the final count, which is the number of restaurants that match all the specified criteria.
2. End the process: Stop the query execution process.
3. Setup phase: Before starting the actual query execution, the system prepares the specific values it will be looking for, like "san pablo ave," "thai," and "albany."
**Final Optimized SQL Query:**
SELECT COUNT(T1.id_restaurant) FROM generalinfo AS T1 INNER JOIN location AS T2 ON T1.id_restaurant = T2.id_restaurant WHERE T1.food_type = ’thai’ AND T1.city = ’albany’ AND T2.street_name = ’san pablo ave’
~~~~

#### Full template from the CHESS repo
Source: https://github.com/ShayanTalaei/CHESS/blob/main/templates/template_generate_candidate_two.txt (463 lines). Lines 1–6 and the 13 "Database admin instructions" are **identical to the DC template above**. The method line is different:
~~~~text
You will be using a way called "Query Plan Guided SQL Generation" to generate the SQL query. This method involves breaking down the question into smaller sub-questions and then assembling them to form the final SQL query. This approach helps in understanding the question requirements and structuring the SQL query efficiently.
~~~~
After that comes the same `<FINAL_ANSWER>` instruction, then 6 examples in the same order and on the same topics as DC, minus the "online programs" example. Each example has `**Query Plan**:` with sections such as `** Preparation Steps: **`, `** Identify … **`, `** Count … **`, `** Finalize and Deliver the Result: **` and a `<FINAL_ANSWER>`. Example 0 is word-for-word the paper's Fig. 18/19 demo. Tail:
~~~~text
Now is the real question, following the instruction and examples, You should:
1. Generate a QUERY PLAN for the given question and evidence.
2. Return the final optimized SQL query.

**************************
【Table creation statements】
{DATABASE_SCHEMA}

**************************
【Question】
Question: 
{QUESTION}

Evidence:
{HINT}

**************************
【Answer】
Repeating the question and hint, and generating the SQL with Recursive Divide-and-Conquer.
~~~~
Oddity: the QP template's answer preamble, in every demo and in the tail, says "generating the SQL with Recursive Divide-and-Conquer". The paper's demo says "generating the SQL with a query plan."

#### Numbers
- Single candidate: QP CoT **63.62** (+5.87). With fixer: **65.51** (+7.76). Mistral Large: 59.64 (+4.76); with fixer 62.64 (+7.76).
- Removing QP from the full system: **72.36** (−0.65).
- Table 6, QP: T=0.5 → agent **71.7** vs SC 65.78 (UB 78.55, LB 50.46); T=1.8 → agent **71.73** vs SC 65.51 (UB 80.44, LB 48.63).
- Venn: QP only = **35**; QP∩OS only = 33.
- "the query plan method excels on moderately difficult queries". Fig. 3b (approximate): QP ≈17 simple, ≈15 moderate, ≈3 challenging.

### 1c. Online synthetic example (OS) generation

#### Mechanism (Alg. 2)
- For each test question, two LLM calls produce many-shot question→SQL examples. These are inserted as in-context examples for the final SQL-generation call:
  1. `θ(D, Rf, nf)`: examples over the **entire target DB**, guided by common SQL features `Rf`: "equality and non-equality predicates, single table and multi-table JOIN, nested JOIN, ORDER BY and LIMIT, GROUP BY and HAVING, various aggregation functions".
  2. `θ(t, Rt, nt)`: examples over the **column-filtered schema** `t` ("column selection using an approach similar to (Talaei et al., 2024)"), "similar to the examples outlined in Rt". `Rt` shows examples generated for a training DB.
- The final example set mixes both: "Mixing various examples for various SQL features and database tables with and without column filtering is observed to result in better generation quality overall."
- Camera-ready adds: "we generate many more than just a few (3-5) examples … as we observe that many-shot learning consistently outperforms few-shot learning (Agarwal et al., 2024)."
- CASE: "We omit CASE statement examples, since showing examples with CASE statement did not help with the generation, unless the ground-truth SQL query actually used it."
- Table 8 caption: "Total of 75 examples are generated for each example set (Rf, Rt) and for the mixed (Rf + Rt)."
- The paper does not show the final generation prompt that consumes the examples. Table 4 labels this generator "OS CoT" in v1 and "OS ICL" in the camera-ready.

#### Prompt 1: common-SQL-features examples (`Rf`)
Source: camera-ready Appendix **A.13, Fig. 26** (proceedings PDF above).
~~~~text
You are a SQLite SQL expert. Your job is to create {k} examples, where each example consists of a question and a SQL query to fetch the data for it. I want each example to look like this, question input and SQL output pairs:

```
"input": "What’s the description of the series code SM.POP.TOTL for Aruba?
(Hints: Aruba is the name of the country where ShortName = ’Aruba’)"

"output": "SELECT T2.Description FROM Country AS T1 INNER JOIN CountryNotes AS T2 ON T1.CountryCode = T2.Countrycode WHERE T1.ShortName = ’Aruba’ AND T2.Seriescode = ’SM.POP.TOTL’"
```

You should generate examples that examine and showcase different aspects and relationships of the following table schemas, described in "Table creation statements". Understand the database tables and their relationships. Understand the columns and their types and meanings to construct intresting examples.
Generate a mixture of SQL examples that include:
    • some simple SQL query examples without JOIN
    • some SQL query examples with aggregates, like COUNT
    • some simple SQL query examples with JOIN
    • some complex SQL query examples with nested JOIN
**************************
###Table creation statements###
{TARGET_DATABASE_SCHEMA}
**************************
Generate total of {k} examples. Only outputs the examples (question input and SQL output pairs), and each example can be separated by a new line.
~~~~
Caption: "TARGET_DATABASE_SCHEMA contains all the tables from the target database." arXiv v1 (A.10, Fig. 24, https://arxiv.org/html/2410.01943) differs in two ways: there are no ``` fences around the example, and the header is `Table creation statements` without `###`. The text is otherwise identical, including the typo "intresting".

#### Prompt 2: filtered-schema examples (`Rt`)
Source: camera-ready **A.13, Fig. 27**; v1 **A.10, Fig. 25**. The text is the same in both.
~~~~text
You are a SQLite SQL expert. Your job is to create a set of examples, where each example consists of a question and a SQL query to fetch the data for it.
You should generate examples that examine and showcase different aspects and relationships of the following table schemas. Understand the database tables and their relationships. Understand the columns and their types and meanings to construct intresting examples.
I will also show you multiple examples generated for the other database and its table schemas, so you can see what kind of examples can be generated for a given database.

**************************
###Examples from other database### The following is the table schemas and column examples for other database:
The database ("{TRAIN_DATABASE_NAME}") structure is defined by the following table schemas (comments after ’–’ provide additional column descriptions).

{TRAIN_DATABASE_SCHEMA}

————————–

The folloiwing are the examples generated for the above database schemas:
Example 1) "input": "Among the countries in the group of Heavily Indebted Poor Countries, how many of them are under the lending category of the International Development Associations?
(Hints: group of Heavily Indebted Poor Countries is OtherGroups = ’HIPC’; International Development Associations refers to lendingcategory = ’IDA’)"

"output": "SELECT COUNT(CountryCode) FROM Country WHERE LendingCategory = ’IDA’ AND OtherGroups = ’HIPC’"

...

Example 10) "input": "What is the description of the footnote on the series code AG.LND.FRST.K2 in 1990 for Aruba?
(Hints: Year = 1990; Aruba is the name of country where ShortName = ’Aruba’)"

"output": "SELECT T2.Description FROM Country AS T1 INNER JOIN FootNotes AS T2 ON T1.CountryCode = T2.Countrycode WHERE T1.ShortName = ’Aruba’ AND T2.Seriescode = ’AG.LND.FRST.K2’ AND T2.Year = ’YR1990’"

**************************
Now similarly, generate examples (question input and SQL output pairs) for the table schemas defined below, in "Table creation statements".

**************************
###Table creation statements###
TARGET_DATABASE_SCHEMA

**************************
Only outputs the examples (question input and SQL output pairs), and each example can be separated by a new line.
~~~~
- Caption: "This is use TARGET_DATABASE_SCHEMA filtered with column selection result, and the model is asked to generate simple examples similar to the ones taken from the training dataset (separate from the test or dev dataset)."
- The PDF renders the DB-name quotes as `(¨{TRAIN_DATABASE_NAME}¨)`, a LaTeX artifact; I normalized them to `"…"`.
- Note that `TARGET_DATABASE_SCHEMA` has no braces in this figure.
- **No repo version found** (CHESS has no OS template).

#### Numbers
- Single candidate: OS **67.09** (+9.34). With fixer: **68.02** (+10.27), the best single generator. Mistral Large: OS only 56.32 (+1.44); with fixer 61.47 (+6.59).
- Table 8 (Gemini 1.5 Pro, BIRD dev, 75 examples per set): baseline zero-shot 57.75; OS w/ Rf **65.45** (+7.7); OS w/ Rt **66.75** (+9.0); OS w/ Rf+Rt **67.09** (+9.34).
- Table 9 (camera-ready only; single candidate, no self-correction, n examples):

| n | 5 | 25 | 75 | 125 |
|---|---|---|---|---|
| σ(train) (question-similarity training examples) | 58.80 | 58.54 | 57.69 | 56.91 |
| CodeS synthetic | 60.76 | 60.63 | 59.97 | 59.06 |
| OS | 62.13 | 64.02 | **64.41** | 63.69 |

- Removing OS from the full system: **72.16** (−0.85).
- Table 6, OS: T=0.5 → agent **70.4** vs SC 67.34 (UB 74.77, LB 60.43); T=1.8 → agent **71.38** vs SC 66.88 (UB 79.66, LB 50.98).
- Venn: OS only = **30**. Fig. 3b (approximate): OS ≈11 simple, ≈14 moderate, ≈5 challenging.

### 1d. Query fixer

#### Mechanism
- Self-reflection (Shinn et al.), applied to a candidate whose execution errors or returns an empty result. Feedback is "syntax error details or empty result sets". It retries "up to a specified number of attempts, β (set to three in this paper)".
- Alg. 4 (camera-ready A.4):
  - For each candidate, execute it.
  - If there is an error, or the result is `[]`, loop `j ∈ {1..β}`: `ci ← θf(D, ci, Execution_i)`, then re-execute. Keep the query and `break` on the first non-error, non-empty result.
  - Otherwise keep the query as is.
  - `[INFERENCE]` As written, a candidate that still fails after β tries is never added to `C_fixed`, so it is dropped.
- Sources: camera-ready §2.4 and A.4; https://arxiv.org/html/2410.01943 §3.4.

#### Prompt (paper)
Source: v1 **A.7, Fig. 21**; camera-ready **A.10, Fig. 22**. Text is identical in both.
~~~~text
**Task Description:**
You are an SQL database expert tasked with correcting a SQL query. A previous attempt to run a query did not yield the correct results, either due to errors in execution or because the result returned was empty or unexpected. Your role is to analyze the error based on the provided database schema and the details of the failed execution, and then provide a corrected version of the SQL query.
**Procedure:**
1. Review Database Schema:
- Examine the table creation statements to understand the database structure.
2. Analyze Query Requirements:
- Original Question: Consider what information the query is supposed to retrieve.
- Hint: Use the provided hints to understand the relationships and conditions relevant to the query.
- Executed SQL Query: Review the SQL query that was previously executed and led to an error or incorrect result.
- Execution Result: Analyze the outcome of the executed query to identify why it failed (e.g., syntax errors, incorrect column references, logical mistakes).
3. Correct the Query:
- Modify the SQL query to address the identified issues, ensuring it correctly fetches the requested data according to the database schema and query requirements.
**Output Format:**
Present your corrected query as a single line of SQL code, after Final Answer. Ensure there are no line breaks within the query.
Here are some examples:
{EXAMPLES}
======= Your task =======
**************************
Table creation statements
{DATABASE_SCHEMA}
**************************
The original question is:
Question:
{QUESTION}
Evidence:
{HINT}
The SQL query executed was:
{QUERY}
The execution result:
{RESULT}
**************************
Based on the question, table schema and the previous query, analyze the result try to fix the query.
~~~~
CHESS repo version: https://github.com/ShayanTalaei/CHESS/blob/main/templates/template_revise_one.txt. The Task Description and Procedure are identical. Differences:
- Output Format line: "Present your corrected query as a single line of SQL code, enclosed within XML delimiter tags <FINAL_ANSWER> and </FINAL_ANSWER>. Ensure there are no line breaks within the query."
- `{EXAMPLES}` is filled with 3 worked fixes, each with "Step 1: Review Database Schema / Step 2: Analyze Query Requirements / Step 3: Correct the Query":
  - `no such column: T2.street` → `street_name`
  - alias-scope error `T1.name is not found in table T1`
  - empty result `[]` caused by `'london'` vs `'London'` case
- The last line reads "table schemas", and these lines are appended:
~~~~text
Give very detailed analysis first. When you are OK with the fixed query, output the query string ONLY inside the xml delimiter <FINAL_ANSWER></FINAL_ANSWER>.
Inside the xml delimiter it should be the query in plain text. You cannot modify the database schema or the question, just output the corrected query.
Make sure you only output one single query. The query should be a one liner without any line breaks.

Example of correct format:
<FINAL_ANSWER>
SELECT column FROM table WHERE condition
</FINAL_ANSWER>
~~~~
(CHESS config: revise_one at temperature 0.0.)

#### Numbers (Table 4, Gemini 1.5 Pro, BIRD dev, single candidate)
- Fixer adds +3.83 to the baseline (57.75→61.58), +1.89 to QP (63.62→65.51), +1.85 to DC (63.92→65.77), and +0.93 to OS (67.09→68.02). The text says "increasing performance by nearly 2% across all candidate generators".
- Removing the fixer from the full system: **69.23** (−3.78) (Table 7).

### 1e. Selection agent (pairwise, fine-tuned)

#### Mechanism
- **Formulation.** Eq. 1: $c_f=\arg\max_{c\in C}\sum_{i=1}^{\binom{n}{k}}\theta_p(c_{i_1},\dots,c_{i_k}\mid Q_u,H_u,D)$. The paper sets **k = 2**: "train a model with a classification objective to compare only two candidates at a time."
- **Why fine-tune.** Off-the-shelf Gemini-1.5-pro reached "only 58.01% binary classification accuracy" (body text). Table 5 lists 63.98 for the same model (see Surprises).
- **Training data.**
  - Run the generators on the training set and cluster candidates by execution result.
  - When at least one cluster is correct and another incorrect, create tuples $(Q_u, C_i, C_j, D_{ij}, y_{ij})$, where $D_{ij}$ is "the database schema used by both candidates".
  - Camera-ready adds: "(Using the union of candidate schemas is important as it reduces cost and eliminates unnecessary information during comparison.)"
  - "To avoid order bias during training, we randomly shuffle the order of correct and incorrect queries in each pair."
  - When no correct candidate exists, "we include the ground truth SQL query in the prompt as a hint to guide the model in generating correct candidates."
  - Size: 3.8K BIRD-train samples. Model: Gemini 1.5 Flash, LoRA rank 16, 10 epochs, via the Vertex AI tuning API.
- **Inference scoring (Alg. 3).**
  - Initialize `r_i ← 0`.
  - For each distinct ordered pair `(c_i, c_j)`, i≠j:
    - If `er(c_i,D) = er(c_j,D)`, set `w ← i` (a matching execution result counts as consistency, with no LLM call).
    - Otherwise set `S_ij ← schema_union(c_i, c_j, D)` and `w ← θ_p(S_ij, Q_u, H_u, c_i, c_j)`.
  - Then `r_w ← r_w + 1`. Return `argmax r_i`.
  - "we compare both (c_i,c_j) and (c_j,c_i) to mitigate any order bias … (ignoring the both side comparison will reduce the final performance by roughly 2%)" (camera-ready).
  - **Tie-break:** "In the rare case of a tie in the final scores, we break the tie by selecting one of the candidates arbitrarily."
  - `[INFERENCE]` Because both orderings are visited and `w←i` on a match, two candidates with identical results each get +1 per pair.
- **Schema passed to the selector:** "the database schema used in this step is the union of the columns and tables by the two candidates instead of using the full-schema of all tables in the database" (A.8 v1 / A.11 camera-ready). The union is over **columns and tables**, not just tables.
- **Ranker-agent baseline (Table 7):** "receives all candidates generated by our three candidate generators in a single prompt, compares them, and produce a ranking for each … we select the query with the lowest rank as the best answer."
- Sources: camera-ready §2.5, A.3, A.11; https://arxiv.org/html/2410.01943 §3.5, A.8.

#### Prompt (paper)
Source: v1 **A.8, Fig. 22**; camera-ready **A.11, Fig. 23**. Both captions mistakenly read "The prompt template used for query fixing". The prompt is used for both training and test-time picking.
~~~~text
Instruction:
Given the DB info and question, there are two candidate queries. There is correct one and incorrect one, compare the two candidate answers, analyze the differences of the query and the result. Based on the original question and the provided database info, choose the correct one.
**************************
Database Schema
{DATABASE_SCHEMA}
**************************
Question:
{QUESTION}
Evidence:
{HINT}
**************************
Candidate A
{CANDIDATE_A_QUERY}
Execution result
{CANDIDATE_A_RESULT}
**************************
Candidate B
{CANDIDATE_B_QUERY}
Execution result
{CANDIDATE_B_RESULT}
Just output the correct answer "A" or "B".
~~~~
No repo version found. CHESS replaces pairwise selection with a unit-test evaluator, `template_evaluate.txt`.

#### Numbers
- Table 5, binary accuracy on pairs where exactly one candidate is correct: Claude-3.5-sonnet 60.21; Gemini-1.5-pro 63.98; **Tuned Gemma 2 9B 64.28**; **Tuned Gemini-1.5-flash 71.01**.
- Table 7, full system on BIRD dev (Gemini 1.5 Pro generators):

| Method | EX | Δ |
|---|---|---|
| CHASE-SQL All | **73.01** | – |
| w self-consistency | 68.84 | −4.17 |
| w ranker agent | 65.51 | −7.5 |
| w/o LSH | 70.09 | −2.92 |
| w/o Query Fixer | 69.23 | −3.78 |
| w/o QP | 72.36 | −0.65 |
| w/o OS | 72.16 | −0.85 |
| w/o DC | 71.77 | −1.24 |

- Table 1 (Gemini 1.5 Pro, BIRD dev): single query 63.01; self-consistency 68.84 (+5.84); **upper bound 82.79** (+19.78). `[INFERENCE]` This is pass@21 with an oracle, since the text says the "upper-bound performance of combining all three methods reaches 82.79%" over the 21-candidate pool (7 per generator).
- Text: "the upper-bound performance of combining all three methods reaches 82.79%". Selection agent vs. SC margin: "roughly 6%" (Table 6).
- End-to-end (Table 2):
  - CHASE + Gemini 1.5: BIRD dev **73.01**, test **73.0**.
  - CHASE + Claude 3.5 Sonnet: dev **69.53** (the selector is still the tuned Gemini Flash: "previously-trained selection model is reused").
  - CHASE + Mistral Large (camera-ready only): dev **70.33**, using "a fine-tuned Qwen2.5-coder model … as the selection model".
  - Spider test (Table 3): **87.6**, run with no Spider training or prompt changes.
- Error breakdown (A.7 camera-ready / A.4 v1, Fig. 6/5 pie): correct 72.9%; correct candidate exists but not chosen 10.4%; no correct candidate 6.7%; wrong gold 10.0%.
- Latency and tokens, from the first author's rebuttal images (https://github.com/MohammadrezaPourreza/CHASE-SQL-REBUTTAL, `Latency_Analysis.png`, "Latency of CHASE-SQL Method on Different Databases in BIRD Benchmark", x-axis "Average Execution Time (seconds)"): ranges from 37.36 s (superhero) to 73.59 s (california_schools) across the 11 BIRD dev DBs. `[INFERENCE]` per question.
  - `token_usage.png` ("Token Usage per Component for CHASE-SQL and CHESS Baseline Across Databases", y-axis in millions of tokens; whether these are totals or per-question figures is not stated) shows generator input dominating. The highest CHASE input is ≈0.34M (european_football_2: ≈0.29M generator + ≈0.04M selector + small fixer), vs. ≈0.78M CHESS input on the same DB (values read off the bars).
  - `finetuning_vs_chase.png`: pass@K of the CHASE generators rises from ≈0.637 at K=1 to ≈0.828 at K=20, vs. ≈0.665→0.784 for a "Finetuned Model" (values read off the plot; the model is unspecified).

### 1f. Value retrieval (LSH + embeddings)

#### What the paper says (all of it)
> "Similar to the approach in (Talaei et al., 2024), we begin by extracting keywords from the given question using an LLM prompted with few-shot examples. For each keyword, we employ locality-sensitive hashing (LSH) (Datar et al., 2004) to retrieve the most syntactically-similar words, and re-rank them based on embedding-based similarity and edit distance. This approach is robust to typos in the question and considers keyword semantics during retrieval."
> (camera-ready §2.2; https://arxiv.org/html/2410.01943 §3.2)

- The paper gives **no parameters** (n-gram size, signature size, thresholds, embedding model, top-k), no keyword-extraction prompt, and no column-filtering prompt.
- Camera-ready A.5 shows retrieved values for "What is the highest eligible free rate for K-12 students in the schools in Alameda County?" (california_schools). Examples: `"GSserved": ["K-12"]`, `"County": ["Alameda"]`, `"School": ["Preschool","MethodSchools","Alameda County Community","Alameda County Opportunity","Alameda High"]`, `"AdmLName1": ["Free"]`. The figure caption is mislabeled "An example of the divide and conquer CoT method".
- The output is grouped per table and column, then injected into the schema shown to generators. `[INFERENCE]` based on the A.5 format and on CHESS `schema_with_examples`.
- Ablation: w/o LSH **70.09** (−2.92) (Table 7).

#### CHESS implementation (the paper says "Similar to … Talaei et al."). These are CHESS settings, not confirmed CHASE settings.
Sources:
- https://github.com/ShayanTalaei/CHESS/blob/main/run/run_preprocess.sh
- `src/database_utils/db_values/preprocess.py`
- `src/database_utils/db_values/search.py`
- `src/workflow/agents/information_retriever/tool_kit/retrieve_entity.py`

Settings:
- **Index.** `datasketch` MinHash LSH over distinct values of TEXT, non-PK columns.
  - Columns are skipped if the name contains `_id`, ` id`, `url`, `email`, `web`, `time`, `phone`, `date`, or `address`, or ends with `Id`.
  - A column's values are kept if (`name` is in the column name and total length < 5,000,000), or (total length < 2,000,000 and average length < 25), or distinct count < 100.
  - Parameters: `signature_size=100`, `n_gram=3` (character 3-grams), `threshold=0.01`.
- **Query.**
  - For each keyword, search the full keyword, each left and right part around every space, and any value parsed from a `col = value` hint.
  - `query_lsh(..., signature_size=100, top_n=10)`: candidates are ranked by MinHash Jaccard; keep the top 10.
  - Then filter by edit similarity `difflib.SequenceMatcher(...).ratio() ≥ 0.3` (lowercased).
  - Then filter by embedding similarity ≥ 0.6, using `OpenAIEmbeddings(model="text-embedding-3-small")` dot product.
  - Per column, keep values with edit-sim ≥ 0.9×max, then embedding-sim ≥ 0.9×max.
- **Keyword-extraction prompt** (CHESS `templates/template_extract_keywords.txt`, verbatim; CHESS config: gpt-4o-mini, temperature 0.2):
~~~~text
Objective: Analyze the given question and hint to identify and extract keywords, keyphrases, and named entities. These elements are crucial for understanding the core components of the inquiry and the guidance provided. This process involves recognizing and isolating significant terms and phrases that could be instrumental in formulating searches or queries related to the posed question.

Instructions:

Read the Question Carefully: Understand the primary focus and specific details of the question. Look for any named entities (such as organizations, locations, etc.), technical terms, and other phrases that encapsulate important aspects of the inquiry.

Analyze the Hint: The hint is designed to direct attention toward certain elements relevant to answering the question. Extract any keywords, phrases, or named entities that could provide further clarity or direction in formulating an answer.

List Keyphrases and Entities: Combine your findings from both the question and the hint into a single Python list. This list should contain:

Keywords: Single words that capture essential aspects of the question or hint.
Keyphrases: Short phrases or named entities that represent specific concepts, locations, organizations, or other significant details.
Ensure to maintain the original phrasing or terminology used in the question and hint.

Example 1:
Question: "What is the annual revenue of Acme Corp in the United States for 2022?"
Hint: "Focus on financial reports and U.S. market performance for the fiscal year 2022."

["annual revenue", "Acme Corp", "United States", "2022", "financial reports", "U.S. market performance", "fiscal year"]

Example 2:
Question: "In the Winter and Summer Olympics of 1988, which game has the most number of competitors? Find the difference of the number of competitors between the two games."
Hint: "the most number of competitors refer to MAX(COUNT(person_id)); SUBTRACT(COUNT(person_id where games_name = '1988 Summer'), COUNT(person_id where games_name = '1988 Winter'));"

["Winter Olympics", "Summer Olympics", "1988", "1988 Summer", "Summer", "1988 Winter", "Winter", "number of competitors", "difference", "MAX(COUNT(person_id))", "games_name", "person_id"]

Example 3:
Question: "How many Men's 200 Metres Freestyle events did Ian James Thorpe compete in?"
Hint: "Men's 200 Metres Freestyle events refer to event_name = 'Swimming Men''s 200 metres Freestyle'; events compete in refers to event_id;"

["Swimming Men's 200 metres Freestyle", "Ian James Thorpe", "Ian", "James", "Thorpe", "compete in", "event_name", "event_id"]

Task:
Given the following question and hint, identify and list all relevant keywords, keyphrases, and named entities.

Question: {QUESTION}
Hint: {HINT}

Please provide your findings as a Python list, capturing the essence of both the question and hint through the identified terms and phrases. 
Only output the Python list, no explanations needed. 
~~~~
CHASE's column filtering ("similar to Talaei et al.") likely corresponds to CHESS `templates/template_filter_column.txt` (17 KB). I did not read that file.

### 1g. CHASE numbers in one place (BIRD dev unless noted)
- Table 4 (single candidate; Gemini 1.5 Pro EX/Δ and Mistral Large EX/Δ, camera-ready):

| Method | Gemini 1.5 Pro EX | Δ | Mistral Large EX | Δ |
|---|---|---|---|---|
| Baseline (BIRD prompt + zero-shot CoT) | 57.75 | – | 54.88 | – |
| QP CoT | 63.62 | +5.87 | 59.64 | +4.76 |
| DC CoT | 63.92 | +6.17 | 58.99 | +4.11 |
| OS (ICL/"CoT") | 67.09 | +9.34 | 56.32 | +1.44 |
| Baseline w fixer | 61.58 | +3.83 | 60.03 | +5.15 |
| QP w fixer | 65.51 | +7.76 | 62.64 | +7.76 |
| DC w fixer | 65.77 | +8.02 | 63.75 | +8.87 |
| OS w fixer | 68.02 | +10.27 | 61.47 | +6.59 |

- Also see Table 5 (§1e), Table 6 (per-generator rows above), Table 7 (§1e), Table 8 and Table 9 (§1c), the Venn diagram (sums to 1534, BIRD dev size `[INFERENCE]`), and end-to-end results (§1e).

---

### MCS-SQL pipeline overview

Pipeline (arXiv §3): (1) schema linking with multiple prompts, (2) multiple SQL generation with multiple prompts, (3) selection (confidence filtering, then multiple-choice selection by the LLM).

Implementation details, verbatim (§4.3, https://arxiv.org/html/2405.07467):
> "we used the GPT-4 8K as the LLM and text-embedding-ada-002 as the sentence embedding model, which was accessed via Azure OpenAI API. Additionally, we employed the FAISS … library for the embedding similarity search. In schema linking, we used p_t=3 prompts for table linking and p_c=3 prompts for column linking. To generate multiple candidate SQL queries, we use p_q=5 distinct prompts. For each GPT API call, we used a temperature of 1.0 and generated n=20 responses. In both the SQL-generation and MCS steps, we used k=20 question-SQL pairs as few-shot examples. We executed all candidate SQL queries with a timeout of 180s and filtered out queries with a confidence score lower than the threshold T=0.2."

### 2a. Schema linking with multiple shuffled prompts

#### Mechanism
- Two stages, both aimed at **recall**.
- **Table linking.** The LLM returns JSON with reasoning and a table list ("Inspired by zero-shot-CoT … we ask the LLM to explain why each table is necessary").
  - "we randomly shuffle the order of tables, generating p_t distinct prompts. For each prompt, we obtain n responses from the LLM by using a high sampling temperature. The final table-linking output is derived from the union of all responses, amounting to p_t·n table lists."
  - Why a union: "including unnecessary tables in table linking does not significantly impact the subsequent SQL-generation process; however, omitting the necessary tables prevents the generation of the correct SQL query."
- **Column linking.** The prompt includes only the tables kept by table linking. Answers use the "[table_name].[column_name] format".
  - "the order of the tables and columns is randomly shuffled to generate p_c unique prompts … The column-linking output is the union of all p_c*n responses."
- Downstream steps see "only the tables and columns selected through schema linking".
- With the §4.3 settings this is 3×20 = 60 table-link samples and 60 column-link samples per question. `[INFERENCE]` arithmetic.

#### Prompts
Body template, Listing 1 (§3.1.1). Its JSON key is `answer`; the appendix uses `tables`:
~~~~text
### For a given DB schema and question, extract the list of tables required to write the SQL query.
### DB schema: ...
### Question: ...
Your answer should be in the json format:
{
 "reasoning": "..." # The reason for selecting each table.
 "answer": [...] # List of selected tables.
}
### Your answer:
~~~~
Full table-linking prompt, Appendix **B.1.1** (https://arxiv.org/pdf/2405.07467; identical in https://aclanthology.org/2025.coling-main.24.pdf):
~~~~text
### Given a database schema, question, and knowledge evidence, extract a list of tables that should be referenced to convert the question into SQL.

### SQLite SQL tables, with their properties:
# molecule ( molecule_id, label )
# connected ( atom_id, atom_id2, bond_id )
# bond ( bond_id, molecule_id, bond_type )
# atom ( atom_id, molecule_id, element )
#
# atom.molecule_id = molecule.molecule_id
# bond.molecule_id = molecule.molecule_id
# connected.bond_id = bond.bond_id
# connected.atom_id2 = atom.atom_id
# connected.atom_id = atom.atom_id

### Question: Among all chemical compounds identified in the database, what percent of compounds form a triple-bond.
### Knowledge Evidence: triple bond refers to bond_type = ’#’;

You need to not only select the required tables, but also explain in detail why each table is needed.
Your answer should strictly follow the following json format.
{
  "reasoning": "", // The reason for choosing each table.
  "tables": [], // List of selected tables.
}

### Your Answer:
~~~~
Full column-linking prompt, Appendix **B.1.2**. The doubled braces `{{ }}` appear as printed in the paper, probably left over from format-string templating `[INFERENCE]`.
~~~~text
### Given a database schema, question, and knowledge evidence, extract a list of columns that should be referenced to convert the question into SQL.

### SQLite SQL tables, with their properties:
# molecule ( molecule_id, label )
# bond ( bond_id, molecule_id, bond_type )
#
# bond.molecule_id = molecule.molecule_id

### Question: Among all chemical compounds identified in the database, what percent of compounds form a triple-bond.
### Knowledge Evidence: triple bond refers to bond_type = ’#’;

You need to not only select the required columns, but also explain in detail why each column is needed.
Your answer should strictly follow the following json format.
{{
   "reasoning": "", // The reason for choosing each column.
   "columns": ["table_name_i.column_name_j", ...], // List of selected columns
}}

### Your Answer:
~~~~

#### Numbers
Table 5 (schema-linking recall vs. gold tables and columns, dev sets):

| Setting | BIRD | Spider |
|---|---|---|
| p_t=p_c=1, n=1 (greedy) | 61.3 | 91.8 |
| p_t=p_c=1, n=20 | 77.1 | 96.5 |
| p_t=p_c=3, n=20 (proposed) | **89.8** | **99.2** |

Text: sampling gives "+15.8% for BIRD and +4.7% for Spider"; multiple prompts add "+12.7% for BIRD and +2.7% for Spider". Ablation: adding schema linking to zero-shot gives +2.1 on BIRD dev (50.7→52.8) and +3.3 on Spider dev (74.6→77.9).

### 2b. Multiple SQL generation (few-shot selection variants)

#### Mechanism
- Few-shot pool: the training set. Two retrieval strategies:
  - **Question similarity:** "select the top-k questions from the training dataset that have the nearest sentence embeddings to the natural language question of the test sample".
  - **Masked-question similarity:** an LLM masks "table names, column names, and values" with special tokens, then the same embedding search runs on the masked questions. "This masking allows determining the similarity of questions in terms of generating similar queries by disregarding schema-specific content."
- p_q prompts: "including one derived exclusively from question similarity, another solely from masked question similarity, and additional prompts created by integrating examples from both strategies in various sequences."
- Each prompt contains:
  - k=20 example (question, evidence, gold SQL) triples. "To conserve the limited length of the prompt, we exclude the schema of the target DB for each question."
  - The linked schema only.
  - **Sample table contents in CSV**.
  - The question and evidence.
  - A JSON answer `{reasoning, sql}`.
- "For each prompt, we generate n responses … resulting in p_q·n candidate SQL queries." That is 5×20 = 100 candidates `[INFERENCE]` arithmetic.
- **Schema order is NOT reported as shuffled in the generation stage.** Shuffling is described only for table and column linking (§3.1). Generation-prompt diversity comes from "varying both the selection method of the few-shot examples and the order in which they are presented". I grepped the HTML for "shuffl" and found it only in §3.1.

#### Prompts
Body template, Listing 2 (§3.2.2):
~~~~text
### Generate the correct SQL query for a given DB schema and question.
### Gold Examples:
- Question: ...
- Gold SQL: ...
...
### DB Schema: ...
### Sample Table Contents: ...
### Question: ...
Your answer should be in the json format:
{
 "reasoning": ".." # The reasoning steps behind the generated SQL query
 "sql": ".." # The generated SQL query.
}
### Your answer:
~~~~
Question-masking prompt, Appendix **B.2** (Listing 4):
~~~~text
### Given a DB schema and a question, mask the table name, column name, and values in the question.

<example1>
### SQLite SQL tables, with their properties:
# customers ( CustomerID: integer, Segment: text, Currency: text )
# gasstations ( GasStationID: integer, ChainID: integer, Country: text, Segment: text )
# products ( ProductID: integer, Description: text )
# transactions_1k ( TransactionID: integer, Date: date, Time: text, CustomerID: integer, CardID: integer, GasStationID: integer, ProductID: integer, Amount: integer, Price: real )
# yearmonth ( CustomerID: integer, Date: text, Consumption: real )

### Question: For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.
### Masked Question: For all the [TABLE] who paid more than [VALUE] per unit of [COLUMN] [VALUE]. Give their consumption status in the [VALUE].
</example1>

<example2>
### SQLite SQL tables, with their properties:
# customers ( CustomerID: integer, Segment: text, Currency: text )
# gasstations ( GasStationID: integer, ChainID: integer, Country: text, Segment: text )
# products ( ProductID: integer, Description: text )
# transactions_1k ( TransactionID: integer, Date: date, Time: text, CustomerID: integer, CardID: integer, GasStationID: integer, ProductID: integer, Amount: integer, Price: real )
# yearmonth ( CustomerID: integer, Date: text, Consumption: real )

### Question: How much did customer 6 consume in total between August and November 2013?
### Masked Question: How much did [TABLE] [VALUE] consume in total between [VALUE] and [VALUE]?
</example2>

<example3>
### SQLite SQL tables, with their properties:
# drivers ( driverId: integer, driverRef: text, number: integer, code: text, forename: text, surname: text, dob: date, nationality: text, url: text )

### Question: How many Australian drivers who were born in 1980?
### Masked Question: How many [VALUE] [TABLE] who were born in [VALUE]?
</example3>


### SQLite SQL tables, with their properties:
# molecule ( molecule_id, label )
# bond ( bond_id, molecule_id, bond_type )
#
# bond.molecule_id = molecule.molecule_id

### Question: Among all chemical compounds identified in the database, what percent of compounds form a triple-bond.
### Knowledge Evidence: triple bond refers to bond_type = ’#’;

### Masked Question:
~~~~
Full SQL-generation prompt, Appendix **B.3**. The paper elides the remaining examples with "...":
~~~~text
### Given a database schema, question, and knowledge evidence, generate the correct sqlite SQL query for the question.

<examples>
# Question: Among all the customers, what is the percentage of the customer’s nation being Germany?
# Knowledge Evidence: DIVIDE(COUNT(c_custkey when n_name = ’GERMANY’), COUNT(c_custkey)) as percentage;
# Gold SQL: SELECT CAST(SUM(IIF(T2.n_name = ’GERMANY’, 1, 0)) AS REAL) * 100 / COUNT(T1.c_custkey) FROM customer AS T1 INNER JOIN nation AS T2 ON T1.c_nationkey = T2.n_nationkey
# Question: Among the schools whose donators are teachers, what is the percentage of schools that are in Brooklyn?
# Knowledge Evidence: donors are teachers refers to is_teacher_acct = ’t’; Brooklyn is school_city; percentage = Divide(Count(school_city-’Brooklyn’),Count(school_city))*100
# Gold SQL: SELECT CAST(SUM(CASE WHEN T1.school_city LIKE ’Brooklyn’ THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.teacher_acctid) FROM projects AS T1 INNER JOIN donations AS T2 ON T1.projectid = T2.projectid WHERE T2.is_teacher_acct = ’t’

...
</examples>


### SQLite SQL tables, with their properties:
# molecule ( molecule_id, label )
# bond ( bond_id, molecule_id, bond_type )
#
# bond.molecule_id = molecule.molecule_id

### The type and description of each column:
# [molecule]
- molecule_id (text): unique id of molecule
- label (text): whether this molecule is carcinogenic or not

# [bond]
- bond_id (text): unique id representing bonds
- molecule_id (text): identifying the molecule in which the bond appears
- bond_type (text): type of the bond

### Sample rows of each table in csv format:
# [molecule]
molecule_id,label
TR000,+
TR001,+
TR002,-

# [bond]
bond_id,molecule_id,bond_type
TR000_1_2,TR000,-
TR000_2_3,TR000,-
TR000_2_4,TR000,-



### Question: Among all chemical compounds identified in the database, what percent of compounds form a triple-bond.
### Knowledge Evidence: triple bond refers to bond_type = ’#’;

You need to not only create the SQL, but also provide the detailed reasoning steps required to create the SQL. Your answer should strictly follow the following json format:
{
  "reasoning": "", // The reasoning steps for generating SQL.
  "sql": "", // The final generated SQL.
}

### Your Answer:
~~~~

#### Numbers
Table 6 (few-shot selection strategy, dev EX):

| Strategy | BIRD | Spider |
|---|---|---|
| Random | 57.0 | 82.0 |
| Question Similarity | 59.3 | 86.2 |
| Masked Question Similarity | **60.0** | **86.7** |

Ablation step "+ few-shot examples" (masked-question similarity) adds **+4.8** on BIRD dev (55.2→60.0), the largest single gain, and +5.8 on Spider dev. "+ sample table contents" adds +2.4 on BIRD and +3.0 on Spider.

### 2c. Candidate filtering (execution and confidence)

#### Mechanism (§3.3.1)
1. Execute all candidates. Remove those with "syntax errors or timeouts" (timeout 180 s).
2. Confidence is the fraction of the pool sharing the candidate's execution result: $\text{confidence}(q_i)=\frac{1}{N}\sum_{j=1}^{N}[\text{exec}(q_j)=\text{exec}(q_i)]$ (Eq. 1).
3. Deduplicate by result. For each unique result, keep only the **fastest** query: $C'=\bigcup_{R}\arg\min_{q_i:\text{exec}(q_i)=R}\text{exec\_time}(q_i)$ (Eq. 2).
4. Drop candidates with confidence < T, where **T=0.2** (Eq. 3).

`[INFERENCE]` With T=0.2, at most 5 result-clusters can survive. The B.4 prompt says "up to three SQLite queries", which suggests the authors saw or capped at ≤3, but the paper never states a cap.

### 2d. Multiple-choice selection (MCS)

#### Mechanism (§3.3.2)
- Present the filtered candidates as a numbered list. "Candidate queries are provided in descending order of confidence scores, considering the tendency of LLMs to favor options that appear earlier in the multiple-choice questions."
- The LLM returns JSON `{reasoning, sql}`. "We sample n responses from the LLM and determine the final SQL query through a majority vote" (n=20, temperature 1.0).
- The MCS prompt also includes k=20 few-shot question/evidence/gold-SQL examples (§4.3).
- The appendix prompt adds a 5-item checklist and a rule: take the first SQL that satisfies all items, otherwise default to the first SQL, which is the highest-confidence one.

#### Prompts
Body template, Listing 3 (§3.3.2):
~~~~text
### For a given DB schema and question, select the most accurate query among the candidate SQL queries.
### DB schema: ...
### Question: ...
### Candidate SQLs:
1. SQL1
2. SQL2
3. SQL3
Your answer should be in the json format:
{
 "reasoning": ".." # The reasoning steps for selecting the correct SQL query.
 "sql": ".." # The selected SQL query.
}
### Your answer:
~~~~
Full selection prompt, Appendix **B.4** (https://arxiv.org/pdf/2405.07467; identical in the COLING PDF):
~~~~text
### When a DB schema, a question, and a knowledge evidence are given, and up to three SQLite queries expressing the question are given, please choose the most accurate SQL based on the Checklist.

<examples>
# Question: Among all the customers, what is the percentage of the customer’s nation being Germany?
# Knowledge Evidence: DIVIDE(COUNT(c_custkey when n_name = ’GERMANY’), COUNT(c_custkey)) as percentage;
# Gold SQL: SELECT CAST(SUM(IIF(T2.n_name = ’GERMANY’, 1, 0)) AS REAL) * 100 / COUNT(T1.c_custkey) FROM customer AS T1 INNER JOIN nation AS T2 ON T1.c_nationkey = T2.n_nationkey

# Question: Among the schools whose donators are teachers, what is the percentage of schools that are in Brooklyn?
# Knowledge Evidence: donors are teachers refers to is_teacher_acct = ’t’; Brooklyn is school_city; percentage = Divide(Count(school_city-’Brooklyn’),Count(school_city))*100
# Gold SQL: SELECT CAST(SUM(CASE WHEN T1.school_city LIKE ’Brooklyn’ THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.teacher_acctid) FROM projects AS T1 INNER JOIN donations AS T2 ON T1.projectid = T2.projectid WHERE T2.is_teacher_acct = ’t’

...
</examples>


### SQLite SQL tables, with their properties:
# molecule ( molecule_id, label )
# bond ( bond_id, molecule_id, bond_type )
#
# bond.molecule_id = molecule.molecule_id

### The type and description of each column:
# [molecule]
- molecule_id (text): unique id of molecule
- label (text): whether this molecule is carcinogenic or not

# [bond]
- bond_id (text): unique id representing bonds
- molecule_id (text): identifying the molecule in which the bond appears
- bond_type (text): type of the bond

### Sample rows of each table in csv format:
# [molecule]
molecule_id,label
TR000,+
TR001,+
TR002,-

# [bond]
bond_id,molecule_id,bond_type
TR000_1_2,TR000,-
TR000_2_3,TR000,-
TR000_2_4,TR000,-



### Question: Among all chemical compounds identified in the database, what percent of compounds form a triple-bond.
### Knowledge Evidence: triple bond refers to bond_type = ’#’;

### Candidate SQLs:
1. SELECT CAST(COUNT(CASE WHEN bond_type = ’#’ THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(*) FROM bond
2. SELECT CAST(COUNT(DISTINCT CASE WHEN bond_type = ’#’ THEN molecule_id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT molecule_id) FROM bond

### Checklist:
1. The SQL should accurately represent the question.
2. The SQL should accurately use the given knowledge evidence.
3. The SELECT clause should not include any additional columns that are not included in the question.
4. The order of columns in the SELECT clause must be the same as the order in the question.
5. Check if the operations are being performed correctly according to the column type.

### Instruction:
- If the first SQL satisfies all the conditions of the checklist, please choose the first SQL. If not, move on to the next SQL.
- If there’s no SQL that satisfies all the requirements on the checklist, just choose the first SQL.
- Provide a detailed step-by-step explanation following the order of the checklist when checking whether each SQL satisfies the checklist.
- Your answer should strictly follow the following json format.
{{
   "reasoning": "", // The reasoning steps for choosing the best SQL.
   "sql": "", // The final chosen SQL.
}}

### Your Answer:
~~~~

#### Numbers
Table 7 (selection strategy, dev EX):

| Strategy | BIRD | Spider |
|---|---|---|
| Majority Vote (highest confidence) | 62.8 | 89.2 |
| MCS w/o confidence filtering | 62.5 | 85.4 |
| MCS w/ confidence filtering (proposed) | **63.4** | **89.5** |

"in the absence of confidence-based filtering … the efficacy of the MCS method decreased significantly."

### 2e. MCS-SQL ablations and headline numbers (GPT-4)
Table 3 (BIRD dev, incremental):

| Method | Simple | Moderate | Challenging | All |
|---|---|---|---|---|
| zero-shot | 59.0 | 40.2 | 30.6 | 50.7 |
| + schema linking | 61.4 | 41.1 | 35.4 | 52.8 (+2.1) |
| + sample table contents | 64.1 | 42.6 | 38.9 | 55.2 (+2.4) |
| + few-shot examples | 67.1 | 51.6 | 41.0 | 60.0 (+4.8) |
| + MCS (p_q=1, n=20) | 69.3 | 52.0 | 48.6 | 62.1 (+2.1) |
| + MCS (p_q=5, n=20) | 70.4 | 53.1 | 51.4 | **63.4** (+1.3) |

Table 4 (Spider dev, incremental):

| Method | Easy | Medium | Hard | Extra | All |
|---|---|---|---|---|---|
| zero-shot | 79.0 | 83.4 | 66.7 | 52.4 | 74.6 |
| + schema linking | 86.7 | 85.0 | 67.2 | 57.2 | 77.9 (+3.3) |
| + sample table contents | 89.9 | 88.6 | 69.0 | 59.0 | 80.9 (+3.0) |
| + few-shot examples | 94.0 | 90.4 | 86.2 | 66.3 | 86.7 (+5.8) |
| + MCS (p_q=1, n=20) | 93.1 | 92.6 | 88.5 | 72.2 | 88.8 (+2.1) |
| + MCS (p_q=5, n=20) | 94.0 | 93.5 | 88.5 | 72.9 | **89.5** (+0.7) |

Text: multiple prompts gave "+1.3%, particularly showing significant performance improvement on challenging queries" (BIRD challenging 48.6→51.4).

Headline results:
- Table 1 (BIRD): MCS-SQL + GPT-4: dev EX **63.4**, VES 64.8; test EX **65.5**, VES **71.4**. The text gives 65.45 / 71.35 on test.
- Table 2 (Spider): dev **89.5**, test **89.6**.
- CHASE Table 2 cites MCS-SQL at 63.36 dev / 65.45 test.

Error analysis (App. A, 100 random failures per dev set):
> "The 62 and 73% failure cases in the BIRD and Spider benchmarks, respectively, were those wherein the correct query was generated but they were still considered failures owing to inaccuracies in the gold queries or limitations of the method used to calculate the EX."
- Schema-linking errors: 20% (BIRD) and 21% (Spider).
- Other errors: 18% (BIRD) and 6% (Spider).

---

### Mismatches and caveats (CHASE-SQL, MCS-SQL)
- **CHASE's appendix gives no instruction text for the DC and QP generators.** It shows only one few-shot demonstration each. The full instruction templates (13 "database admin instructions", `<FINAL_ANSWER>` tags, 6–7 demos) exist only in the CHESS repo, which is not labeled as CHASE code. The CHESS QP template also wrongly says "generating the SQL with Recursive Divide-and-Conquer".
- **Selector accuracy mismatch.** Untuned Gemini-1.5-pro scores 58.01% in the §2.5 text but 63.98% in Table 5. The Table 4 caption mentions a "Selector" row that is not in the table. The selection-prompt figure is captioned "query fixing" in both versions, and the A.5 value-retrieval figure is captioned "divide and conquer".
- **Versions.** The camera-ready (ICLR 2025) is the latest CHASE text; arXiv was never updated past v1. Prompt changes are limited to ``` fences and `###` headers in the Rf synthetic prompt.
- **MCS generation does not shuffle the schema.** Shuffling happens only in table and column linking. MCS selection is LLM multiple choice, majority-voted over 20 samples, with candidates ordered by confidence and a "default to first" rule.
- **No official code for either paper.** Dunamu has 0 public GitHub repos. Community reimplementations: `kungfuai/chase-sql`, `harkrish1/open-chase-sql`, `VineetV2/chase-sql`, `benchay1999/MCS-SQL-unofficial`. A GitHub code search also shows `HKUSTDial/Alpha-SQL alphasql/templates/sql_generation.txt` containing "Recursive Divide-and-Conquer" (not read).


## Part 3. DAIL-SQL, XiYan-SQL, OpenSearch-SQL, Agentar-Scale-SQL


Markers: **[V]** = copied verbatim from source text/code · **[T]** = transcribed by me from a figure image (minor transcription risk; line-wrap hyphenation in images joined) · **[INFERENCE]** = my reading, not stated by source.

Code repos read: https://github.com/BeachWang/DAIL-SQL · https://github.com/XGenerationLab/M-Schema · https://github.com/XGenerationLab/XiYan-SQL (README only; no pipeline code in that repo) · https://github.com/XGenerationLab/XiYanSQL-QwenCoder · https://github.com/OpenSearch-AI/OpenSearch-SQL (official; 1 commit, MIT) · https://github.com/antgroup/Agentar-Scale-SQL.

---

### 1. DAIL-SQL (arXiv 2308.15363)

#### 1.1 Question masking (used for example retrieval)

**Mechanism.**
- Paper App. A.2 [V]: "For question similarity in QTS S, MQS S and DAIL S, we first connect question words to the database with a n-gram matching based schema-linking method (Wang et al., 2020). Then to obtain the skeleton, we replace table and column names with “<mask>”, and values with “<unk>”. At last, we embed the masked questions with a pre-trained sentence Transformer, all-mpnet-base-v2 (Song et al., 2020), to calculate their similarities." (https://arxiv.org/html/2308.15363, Appendix A.2)
- Code, `utils/linking_utils/application.py::mask_question_with_schema_linking` (https://raw.githubusercontent.com/BeachWang/DAIL-SQL/main/utils/linking_utils/application.py):
  1. Inputs per question: `sc_link` (`q_col_match`, `q_tab_match`) and `cv_link` (`num_date_match`, `cell_match`), token list `question_for_copying`.
  2. `match_shift(...)` resolves overlaps; cell (value) matches on tokens that already have a schema match are dropped.
  3. Value tokens (`num_date_match` ∪ `cell_match` token ids) → `value_tag = "<unk>"`; then schema tokens (`q_col_match` ∪ `q_tab_match`) → `mask_tag = "<mask>"`; join tokens with spaces.
  4. Code comments [V]: `self.mask_token = "<mask>"  # the "<mask>" is the mask token of all-mpnet-base-v2`; `self.value_token = "<unk>"  # the "<unk>" is the unknown token of all-mpnet-base-v2` (`prompt/ExampleSelectorTemplate.py`).
- Linking rules, `utils/linking_utils/spider_match_utils.py` (comment "schema linking, similar to IRNet"): n-grams from n=5 down to 1; column/table **exact** match (n-gram string == name tokens) and **partial** match (regex word-boundary match of n-gram inside name; stopwords/punctuation excluded). Value linking: non-numeric, non-stopword tokens queried against every column with `LIKE '{word} %' OR LIKE '% {word}' OR LIKE '% {word} %' OR LIKE '{word}'` (partial), consecutive matched tokens then re-checked as an exact phrase; numeric tokens marked `num_date_match` only when the column type is `number`/`time`. Each token is mapped once per column; every token matched to any column/table gets masked.
- Paper's MQS S description (§3.2.1) [V]: "replacing table names, column names, and values in all questions with a mask token, and then compute the similarities of their embedding with kNN algorithm."

#### 1.2 DAIL Selection

**Mechanism (paper §3.3 [V]).** "DAIL Selection first masks domain-specific words in both target question q and example questions q_i in the candidate set 𝒬. It then ranks the candidate examples based on the Euclidean distance between the embeddings of masked q and q_i. Simultaneously, it calculates the query similarity between the pre-predicted SQL query s′ and s_i in 𝒬. Finally, the selection criterion prioritizes the sorted candidates by question similarity with a query similarity greater than a predefined threshold τ. In this way, the selected top k examples have good similarity with both question and query."

Details:
- Preliminary model s′: paper experiments use Graphix; leaderboard submission uses GPT‑4 itself with CR_P + MQS S + DAIL O as the preliminary predictor (App. A.2). `run_dail_sql.sh` does exactly this: pass 1 `--selector_type EUCDISQUESTIONMASK` (9‑shot) → GPT‑4 SQL; pass 2 `--selector_type EUCDISMASKPRESKLSIMTHR --pre_test_result <pass‑1 results>`.
- Skeleton (code `utils/utils.py::sql2skeleton`): normalize SQL (lowercase outside quotes, strip `;`, `"`→`'`, add `asc` to bare ORDER BY, de-alias), then replace table names, column names, `table.column`, string literals, ints, negative ints, floats with `_`; drop `on _ = _` join conditions and collapse `_ join _` chains; collapse `_ , _`→`_`; collapse `_ op _`→`_` for `= != > >= < <=`; collapse `where _ and/or _`→`where _`; force token after `order by` to `_`.
- Query similarity = multiset Jaccard over space-split skeleton tokens (`jaccard_similarity`: intersection = Σ min counts; union = len1+len2−intersection).
- Threshold τ: paper experiments 0.9; leaderboard submission 0.85 (App. A.2). Code hard-codes `self.threshold = 0.85`.
- Selector actually used (`EuclideanDistanceQuestionMaskPreSkeletonSimilarThresholdSelector`, enum `EUCDISMASKPRESKLSIMTHR`): embed masked train questions once; sort train items by Euclidean distance to masked target; skip same-`db_id` items when `cross_domain`; **first pass** take items with Jaccard(pre_skeleton_i, pre_skeleton_target) ≥ 0.85 until k; **second pass** (if <k) fill with the remaining items (< 0.85) in distance order.
- Prompt assembly (`prompt/PromptICLTemplate.py::format`): requests `NUM_EXAMPLE * scope_factor` candidates, appends examples in order while `count_tokens(prefix + "\n\n".join(examples + [target])) + max_ans_len <= max_seq_len`; stops at k. NB `count_tokens` and `get_tokenizer` in the released `utils/utils.py` both `return 0` (token budget check is a no-op in the released code).
- Paper's Algorithm 1 line 14 says "sort 𝒬 by cosine_simlarity(e(q′), e(q′_i))" while §3.3 and the code use Euclidean distance (mismatch noted).

#### 1.3 Example organization (DAIL O) and representation (CR_P)

- DAIL O (§3.3 [V]): "DAIL O presents both questions q_i and corresponding SQL queries s_i … As a compromise between FI O and SO O, DAIL O reserves the question-SQL mapping, and reduces the token length of examples by removing token-cost database schema."
- CR_P (§3.1 [V]): "it directly presents “CREAT TABLE” SQLs, and prompts LLM with natural language question in comments … CR P stands out due to its ability to provide comprehensive information necessary for database creation, such as column types and primary/foreign keys." DAIL-SQL adopts CR_P (§3.3).
- Code: CR_P = `REPR_TYPE.CODE_REPRESENTATION = "SQL"` → `SQLPrompt`; DAIL O = `EXAMPLE_TYPE.QA = "QA"` → `QuestionSqlExampleStyle`. DDL text = raw `SELECT sql FROM sqlite_master WHERE tbl_name='{name}'` per table, joined by `"\n\n"` (`get_sql_for_database`). No sample values, no column descriptions.

#### 1.4 Prompt format — verbatim

Paper Listing 4, CR_P (https://arxiv.org/html/2308.15363 §3.1) [V]:
```
/* Given the following database schema: */
CREATE TABLE continents(
	ContId int primary key,
    Continent text,
	foreign key(ContId) references countries(Continent)
);

CREATE TABLE countries(
	CountryId int primary key,
    CountryName text,
    Continent int,
	foreign key(Continent) references continents(ContId)
);

/* Answer the following: How many continents are there? */
SELECT
```
Paper Listing 8, DAIL Organization [V]:
```
/* Some example questions and corresponding SQL queries are provided based on similar problems: */
/* Answer the following: How many authors are there? */
SELECT count(*) FROM authors

/* Answer the following: How many farms are there?. */
SELECT count(*) FROM farm

${TARGET_QUESTION}
```
Code strings (https://raw.githubusercontent.com/BeachWang/DAIL-SQL/main/prompt/PromptReprTemplate.py and `prompt/ExampleFormatTemplate.py`) [V]:
```python
class SQLPrompt(BasicPrompt):
    template_info =   "/* Given the following database schema: */\n" \
                      "{}"
    template_question =  "/* Answer the following: {} */"
# format_question: "\n\n".join([template_info.format("\n\n".join(ddls)), template_question.format(question)])
# BasicPrompt.format_target: self.format_question(example) + "\nSELECT "

class QuestionSqlExampleStyle(object):
    def get_example_prefix(self):
        return "/* Some SQL examples are provided based on similar problems: */\n"
    def format_example(self, example: dict):
        template_qa = "/* Answer the following: {} */\n{}"
        return template_qa.format(example['question'], example['query'])
```
Full prompt as assembled by the code (my assembly of the exact strings above; `SEP_EXAMPLE = "\n\n"`; prompt = prefix + SEP.join(examples + [target])):
```
/* Some SQL examples are provided based on similar problems: */
/* Answer the following: {example_question_1} */
{example_sql_1}

/* Answer the following: {example_question_2} */
{example_sql_2}

/* Given the following database schema: */
{CREATE TABLE ddl_1}

{CREATE TABLE ddl_2}

/* Answer the following: {target_question} */
SELECT 
```
Mismatch: released code prefix is "/* Some SQL examples are provided based on similar problems: */" while paper Listing 8 says "/* Some example questions and corresponding SQL queries are provided based on similar problems: */".

Call settings (`llm/chatgpt.py`, `ask_llm.py`): single `{"role":"user"}` message; `max_tokens=200`; default `temperature=0`; self-consistency `--n 5 --temperature 1.0`; output whitespace-collapsed, cut at first `/*`, prefixed with `SELECT ` if missing. Self-consistency vote (`utils/post_process.py::get_sqls`): execute each candidate, drop exceptions, cluster by equal result, pick first SQL of the largest cluster (fallback: first candidate).

#### 1.5 Numbers (Spider-dev unless noted; https://arxiv.org/html/2308.15363)

Table 2 — example selection, organization fixed to Full-Information, CR_P; "Question/Query Similarity" = mean Jaccard of de-domained tokens between chosen examples and target:

| shot | Selection | Q-sim | SQL-sim | GPT-4 EM/EX | GPT-3.5-T EM/EX | davinci-003 EM/EX | Vicuna-33B EM/EX |
|---|---|---|---|---|---|---|---|
| 0 | – | – | – | 22.1 / 72.3 | 34.6 / 74.4 | 31.7 / 71.7 | 6.9 / 43.7 |
| 1 | Random | 0.23 | 0.47 | 41.7 / 77.4 | 45.9 / 73.9 | 38.2 / 70.6 | 14.4 / 47.9 |
| 1 | Question Sim | 0.39 | 0.65 | 53.3 / 78.8 | 51.9 / 74.3 | 44.1 / 72.3 | 16.5 / 48.5 |
| 1 | Masked Q Sim | 0.57 | 0.80 | 58.2 / 79.1 | 57.4 / 76.0 | 47.9 / 75.0 | 21.4 / 48.7 |
| 1 | DAIL | 0.56 | 0.95 | 62.1 / 80.2 | 59.5 / 75.5 | 51.9 / 76.9 | 22.8 / 49.2 |
| 1 | Upper Limit (gold SQL skeleton) | 0.56 | 0.98 | 63.7 / 81.0 | 61.4 / 77.2 | 53.1 / 77.5 | 22.7 / 49.4 |
| 3 | Random | 0.23 | 0.48 | 48.9 / 79.4 | 49.0 / 73.6 | 41.7 / 71.6 | 16.8 / 46.9 |
| 3 | Question Sim | 0.37 | 0.63 | 56.3 / 79.2 | 53.8 / 74.7 | 52.2 / 74.1 | 21.1 / 47.1 |
| 3 | Masked Q Sim | 0.54 | 0.78 | 66.1 / 81.5 | 61.1 / 77.3 | 59.7 / 77.0 | 27.7 / 52.3 |
| 3 | DAIL | 0.53 | 0.94 | 69.1 / 81.7 | 63.9 / 77.8 | 64.4 / 79.5 | 30.7 / 53.6 |
| 3 | Upper Limit | 0.53 | 0.98 | 71.5 / 83.4 | 66.2 / 79.2 | 66.7 / 81.1 | 31.2 / 54.4 |
| 5 | Random | 0.23 | 0.48 | 51.6 / 79.5 | 52.9 / 75.7 | 49.0 / 72.1 | – |
| 5 | Question Sim | 0.36 | 0.61 | 58.2 / 79.9 | 55.9 / 75.1 | 54.8 / 73.2 | – |
| 5 | Masked Q Sim | 0.52 | 0.77 | 66.8 / 82.0 | 62.3 / 77.9 | 64.7 / 78.6 | – |
| 5 | DAIL | 0.52 | 0.94 | 71.9 / 82.4 | 66.7 / 78.1 | 67.7 / 80.5 | – |
| 5 | Upper Limit | 0.51 | 0.97 | 74.4 / 84.4 | 68.8 / 79.6 | 70.7 / 82.4 | – |

Table 10 — organization (selection fixed to DAIL S), Spider-dev, EM/EX:

| shot | Org | GPT-4 | GPT-3.5-T | davinci-003 |
|---|---|---|---|---|
| 1 | FI O | 62.1/80.2 | 59.5/75.5 | 51.9/76.9 |
| 1 | SO O | 55.2/79.2 | 51.2/76.3 | 41.2/72.4 |
| 1 | DAIL O | 62.9/80.9 | 57.6/77.5 | 46.9/73.2 |
| 3 | FI O | 69.1/81.7 | 63.9/77.8 | 64.4/79.5 |
| 3 | SO O | 64.7/80.2 | 56.2/77.9 | 48.6/74.3 |
| 3 | DAIL O | 69.0/82.4 | 61.9/76.7 | 54.0/74.6 |
| 5 | FI O | 71.9/82.4 | 66.7/78.1 | 67.7/80.5 |
| 5 | SO O | 66.6/80.9 | 56.2/78.8 | 52.1/75.0 |
| 5 | DAIL O | 70.8/82.5 | 64.3/79.0 | 58.2/75.3 |
| 7 | SO O | 67.8/81.1 | 57.2/78.5 | 52.1/74.8 |
| 7 | DAIL O | 72.5/83.5 | 65.6/78.2 | 59.0/74.4 |
| 9 | SO O | 67.6/81.0 | 57.7/78.0 | 53.0/74.9 |
| 9 | DAIL O | 72.8/83.4 | 65.3/77.9 | 60.3/74.4 |

Spider-Realistic (Table 11), GPT-4 DAIL O: 0-shot 66.5 EX → 9-shot 76.0 EX. FI O falls behind DAIL O for GPT-4 but is best for davinci-003 (Table 10).
Final (Table 12 / README): DAIL-SQL+GPT-4 dev EX 83.1, test EX 86.2; +self-consistency dev 83.6, test 86.6 (README also EM: dev 70.0/68.7, test 66.5/66.0). Paper §3.3: SC "+0.4%" EX but "many times the cost". README: ~1600 tokens per question on Spider-dev.
Zero-shot representation (Table 5, EX): GPT-4 BS_P 74.3, TR_P 72.3, OD_P 73.9, CR_P 72.3, AS_P 73.6; GPT-3.5-T OD_P 75.5, CR_P 74.4. FK added (Table 6): OD_P+FK GPT-3.5-T 78.4 EX (+2.9).
BIRD (secondary, from XiYan tables): DAIL-SQL dev 54.76, test 57.41.

**Reimplementable with API-only?** Yes — masking needs only string/LIKE schema-and-value linking + any sentence embedder (paper used local all-mpnet-base-v2; an embeddings endpoint would replace it), skeleton Jaccard is pure code, preliminary SQL from the same LLM; all prompting is a single user message.

---

### 2. XiYan-SQL (arXiv 2411.08599 preview; arXiv 2507.04701 TKDE)

#### 2.1 M-Schema

**Mechanism (preview §3 [V]).** "M-Schema illustrates the hierarchical relationships between the database, tables, and columns in a semi-structured format and employs specifical tokens for identification: "【DB_ID】" marks the database, "# Table" signifies tables, and "【Foreign Keys】" indicates foreign keys. For each table, we present table name and description, where table description can be omitted. The information from a table is converted into a list, where each item is a tuple representing the details of a column. Each column includes the column name, data type, column description, primary key identifier, and example values." Differences vs MAC-SQL schema: adds data type, primary-key marking, DB-sourced column description, "Value examples"→"Examples" with new display rules (string length, number of examples), leading spaces removed.

**Exact format from code** (`m_schema.py::to_mschema` / `single_table_mschema`, https://raw.githubusercontent.com/XGenerationLab/M-Schema/main/m_schema.py):
- Line 1 `【DB_ID】 {db_id}`; line 2 `【Schema】`.
- Per table: `# Table: {table}` or `# Table: {table}, {table_comment}` (prefixed `{schema}.` when a schema name exists); then `[`; field lines joined with `",\n"`; then `]`.
- Field line: `({name}:{TYPE}` + `, {comment}` (if non-empty) + `, Primary Key` (if PK) + `, Examples: [{v1}, {v2}, {v3}]` (if any) + `)`. TYPE = uppercased, `(...)` stripped unless `show_type_detail`.
- Examples: `example_num=3` by default; if type in `DATE/TIME/DATETIME/TIMESTAMP` → only first; elif any example string > 20 chars → only first; if any > 50 chars → none. None values dropped.
- Footer: `【Foreign keys】` then one `{t1}.{c1}={t2}.{c2}` per FK (only if both tables selected).
- `selected_tables` / `selected_columns=['table.column']` filter (this is how schema-linked subsets are rendered).
- `utils.examples_to_str` (value stringification) not read.

M-Schema example, M-Schema repo figure `schema_representation.png` (https://github.com/XGenerationLab/M-Schema, same figure as preview Fig. 2) [T]:
```
【DB_ID】 superhero
【Schema】
# Table: hero_power
[
(hero_id:INTEGER, Primary Key, the id of the hero Maps to superhero(id), Examples: [1, 2, 3]),
(power_id:INTEGER, the id of the power Maps to superpower(id), Examples: [1, 18, 26])
]
# Table: superpower
[
(id:INTEGER, Primary Key, the unique identifier of the superpower, Examples: [1, 2, 3]),
(power_name:TEXT, the superpower name, Examples: [Agility, Accelerated Healing, Lantern Power Ring])
]
【Foreign keys】
hero_power.power_id=superpower.id
```
Same figure, comparison columns [T]:
```
-- DDL Schema
CREATE TABLE hero_power (
hero_id INTEGER,
power_id INTEGER,
FOREIGN KEY (power_id)
REFERENCES superpower(id)
);

CREATE TABLE superpower (
id INTEGER PRIMARY KEY,
power_name TEXT
);

-- MAC-SQL Schema
【DB_ID】 superhero
【Schema】
# Table: hero_power
[
  (hero_id, hero id.),
  (power_id, power id.)
]
# Table: superpower
[
  (id, id.),
  (power_name, power name, Value examples: ['Agility'].)
]
【Foreign keys】
hero_power.hero_id = superpower.id
```
Mismatches: (a) code emits `, comment` **before** `, Primary Key`, figure shows `Primary Key` before the description; (b) paper text says "【Foreign Keys】", code and figures use "【Foreign keys】".

M-Schema repo's suggested text-to-SQL prompt (`example.py` / README) [V]:
````
You are now a {dialect} data analyst, and you are given a database schema as follows:

【Schema】
{db_schema}

【Question】
{question}

【Evidence】
{evidence}

Please read and understand the database schema carefully, and generate an executable SQL based on the user's question and evidence. The generated SQL is protected by ```sql and ```.
````
XiYanSQL-QwenCoder (fine-tuned generator release) inference template, Chinese, from https://github.com/XGenerationLab/XiYanSQL-QwenCoder README [V]:
````
你是一名{dialect}专家，现在需要阅读并理解下面的【数据库schema】描述，以及可能用到的【参考信息】，并运用{dialect}知识生成sql语句回答【用户问题】。
【用户问题】
{question}

【数据库schema】
{db_schema}

【参考信息】
{evidence}

【用户问题】
{question}

```sql
````
(Gloss [INFERENCE]: "You are a {dialect} expert; read the 【database schema】 and possibly useful 【reference info】 and use {dialect} knowledge to generate SQL answering the 【user question】" — question appears twice, before and after schema. Sampling in README: temperature 0.1, top_p 0.8, max_new_tokens 1024.)

**M-Schema numbers.** Preview Table 6, BIRD dev EX, full schema, single generation (https://arxiv.org/html/2411.08599 §7.6.1):

| Model | DDL | MAC-SQL schema | M-Schema |
|---|---|---|---|
| GPT-4o | 55.67 | 57.30 | 57.95 |
| DeepSeek | 53.52 | 55.28 | 55.15 |
| Claude 3.5 Sonnet | 49.74 | 50.26 | 51.04 |
| Gemini 1.5 Pro | 49.22 | 52.41 | 52.15 |

Text: average +2.03 over DDL; vs MAC-SQL +0.65 (GPT-4o), +0.78 (Claude), −0.13 (DeepSeek), −0.26 (Gemini).
XiYanSQL-QwenCoder README table (M-Schema vs DDL, EX): GPT-4o-0806 BIRD dev 58.47 vs 54.82, Spider test 82.89 vs 78.45; GPT-4.1-0414 59.39 vs 54.11, 84.45 vs 79.86; Claude3.5-sonnet-1022 53.32 vs 50.46; Claude3.7-sonnet 54.82 vs 49.22; Gemini-1.5-Pro 61.34 vs 57.89, 85.11 vs 84.00; DeepSeek-V3 59.58 vs 56.71; DeepSeek-R1 58.15 vs 55.61; OmniSQL-32B 60.37 vs 55.87; XiYanSQL-QwenCoder-32B-2504 67.14 vs 62.26, 89.20 vs 86.17.

**API-only?** Yes — M-Schema is a deterministic renderer over DB metadata + sampled values.

#### 2.2 Schema linking / Schema Filter

**Mechanism.**
- Preview §4 [V summary]: retrieval module — few-shot-prompted LLM extracts keywords/entities (like CHASE-SQL); column retriever: top-k columns per keyword by semantic similarity of keyword vs column description; value retriever: two-phase LSH + semantic similarity; union of both. Column Selector: retrieved schema rendered as M-Schema, few-shot prompted LLM judges each column's relevance, keeps only necessary columns.
- 2507 §III-B: LLM M_s (GPT-4o-0806) extracts keywords K = f(Q, E). Column score [V]: "Score(k_i, c_j) = ⟨V_{Q||E}, V_{Tab(c_j)}⟩ · ⟨V_{k_i}, V_{c_j}⟩" (cosine of question+evidence vs table metadata × cosine of keyword vs column metadata) → top-k columns per keyword. Values: edit distance top-k values per column per keyword → RoBERTa-tokenizer tokens + LSH filtering → embedding cosine with threshold. Column Selection (Algorithm 1): p_s iterations; each iteration LLM selects columns from S^rtrv; PFKeyIdentifier completes composite keys and adds referenced keys; S_i = (∪_{k<i} S_k) ∪ S_i^slct ∪ P_i; then remove selected **non-key** columns from S^rtrv (keys retained). Later iterations → lower precision, higher recall. p_s = 2 in experiments.
- Prompts for keyword extraction / column selection: **not published** in either paper (only figures for ICL generator, selection, refiner in the preview). 2507 says details in "Appendix I/II", which are **not present** in arXiv v2 HTML or PDF (checked https://arxiv.org/html/2507.04701 and https://arxiv.org/pdf/2507.04701v2).

**Numbers.** Preview Table 7 (GPT-4o generator, BIRD dev): no linking P 10.14 / R 100.00 / EX 57.95 → +schema linking P 74.74 / R 95.47 / EX 60.10. 2507 Table IV (BIRD dev): Full schema P 10.14, Rc 100; CHESS 85.90 / 74.77 / Rv 63.71; TA-SQL 82.50 / 76.83; S1 74.89 / 83.64 / 91.31; S2 54.90 / 89.77 / 93.63. Table V (EX averaged over FT Qwen2.5-Coder-32B, GPT-4o, Gemini-1.5-pro): full 61.57; CHESS 63.30 (+1.73); S1 63.75 (+2.18); S2 62.97 (+1.40). Table III: w/o Schema Filter −1.24 (73.34 → 72.10). Discussion [V]: "By ensuring that recall reaches a certain threshold (e.g., 80%), improving precision becomes significantly more beneficial".

**API-only?** Yes (LLM keyword extraction + column selection via prompts; needs an embedding model and LSH locally — prompts must be written by us).

#### 2.3 Multi-generator (ICL + fine-tuned) and refiner

**ICL generator mechanism** (preview §5.2 [V]): "XiYan-SQL employs an example selection strategy based on the skeleton similarity between the user question and the question from the training set. All named entities in the question are first identified using NLTK’s tool, then the named entities of the same type are replaced with a special token. For example, "China" and "America" are both identified as countries, so both of them are replaced by "<country>". Other entities, such as enumeration values, are replaced by the column names. … Then we compute embedding of modified questions in the training and test sets, and top-K examples from training sets that closely match the target question are selected." Also: for questions where schema linking selects ≥2 tables, only multi-table example SQLs are chosen; "a maximum of 5 examples are used for each question"; example schemas shown with "only the minimal set of columns". 2507: ICL generator SQLG5 = GPT-4o; few-shot GPT-4o 62.65 vs zero-shot 58.47 on BIRD dev (Table VI).

ICL generator prompt, preview Appendix D Fig. 7 (https://arxiv.org/html/2411.08599v3/figures/ICL_prompt.png) [T] (one-shot example shown; SQL in the example is printed as-is in the figure):
````
You are a SQLite expert. You need to read and understand the following database schema description, as well as the evidence that may be used, and use your SQLite knowledge to generate SQL statements to answer user questions.

The following examples are for your reference.

【DB_ID】 retails
【Schema】
# Table: supplier
[
(s_suppkey:INTEGER, unique id number identifying the supply, Primary Key, Examples: [1, 2, 3]),
(s_nationkey:INTEGER, nation key of the supply, Examples: [13, 5, 22])
]
# Table: nation
[
(n_nationkey:INTEGER, unique id number identifying the nation, Primary Key, Examples: [0, 1, 2]),
(n_name:TEXT, name of the nation, Examples: [ALGERIA, ARGENTINA, BRAZIL])
]
【Foreign keys】
supplier.s_nationkey=nation.n_nationkey
【Evidence】
name of the country refers to n_name; the highest debt refers to min(s_acctbal)

【Question】
What is the name of the country of the supplier with the highest debt?

```sql
SELECT T2.n_name FROM supplier AS T1 INNER JOIN nation AS T2 ON T1.s_nationkey = T2.n_nationkey ORDER BY T1.s_suppkey DESC LIMIT 1
```

Question Solved.
==========

【DB_ID】 california_schools
【Schema】
# Table: schools
[
(CDSCode:TEXT, CDSCode, Primary Key, Examples: [01100170000000, 01100170109835, 01100170112607]),
(MailStreet:TEXT, MailStreet, Examples: [701 East Main Street, 501 West Main Street, Sunset and Cambridge Streets, 313 West Winton Avenue]),
(MailStrAbr:TEXT, Examples: [106 East Manchester Ave., 313 West Winton Ave.]),
(MailCity:TEXT, Examples: [Hayward, Newark, Oakland]),
(MailZip:TEXT, Examples: [94544-1136, 94560-5359, 94612]),
(MailState:TEXT, Examples: [CA])
]
# Table: frpm
[
(CDSCode:TEXT, CDSCode, Primary Key, Examples: [01100170109835, 01100170112607, 01100170118489]),
(School Code:TEXT, School Code, Examples: [0109835, 0112607, 0118489]),
(FRPM Count (K-12):REAL, Free or Reduced Price Meal Count (K-12), Examples: [715.0, 186.0, 175.0])
]
【Foreign keys】
frpm.CDSCode=schools.CDSCode

【Evidence】


【Question】
What is the unabbreviated mailing street address of the school with the highest FRPM count for K-12 students?

```sql
````

**Fine-tuned generators.** Preview §5.1: two-stage multi-task SFT — basic-syntax training (dialect-agnostic, "tens of thousands of samples") then generation-enhance training (question→SQL, SQL→question, SQL→evidence selection, SQL discrimination/regeneration from execution feedback; LLM-paraphrased SQL for stylistic diversity). 2507 §III-C: multi-task (Text-to-SQL + Question Inference + Evidence Inference + Self-Refine) and multi-format data (Structural Variations e.g. subquery→CTE; Stylistic Variations e.g. keyword casing, aliases); base Qwen2.5-Coder-32B; data built with GPT-4o and Qwen-Max. Final p_m = 5 generators: SQLG1 base multi-task FT; SQLG2 structural-variation FT (CTEs); SQLG3 stylistic-variation FT; SQLG4 mixed multi-task+multi-format FT; SQLG5 ICL GPT-4o. Each generator × 2 schemas → p_l = 10 candidates. Training cost: ~45 GPU-h A100-80G, ~180M tokens for the 32B generator; ~15 GPU-h, ~50M tokens for the 7B selector.

**Refiner.** Preview §5.3: separate SQL Refiner — given schema context, generated SQL, execution result/error, model does a second corrective generation; original vs regenerated can go to the selection model; iterable. 2507: refinement folded into generators' self-refine ability — Algorithm 2: execute each l_ij; on exception (2507 text: "syntax errors or anomalous values") retry once with f(Q,E,S_i,l,r); ~+1% (§IV-E).

Refiner prompt, preview Appendix F Fig. 9 (https://arxiv.org/html/2411.08599v3/figures/refiner_prompt.png) [T]:
````
You are a SQLite expert. There is a SQL query generated based on the following Database Schema description and the potential Evidence to respond to the Question. However, executing this SQL has resulted in an error, and you need to fix it based on the error message. Utilize your knowledge of SQLite to generate the correct SQL.

【Database Schema】
{DATABASE_SCHEMA}

【Evidence】
{evidence}

【Question】
If there are any, what are the websites address of the schools with a free meal count of 1,900-2,000 to students aged 5-17? Include the name of the school.

【SQL】
```
SELECT T2.Website, T2.School FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Free Meal Count (Ages 5-17)` BETWEEN 1900 AND 2000
```

【Execution result】
exist None value
[(None, 'South Gate Middle'), ('http://lhs.lynwood.edlioschool.com/', 'Lynwood High'), ('www.auhsd.us/katella', 'Katella High')]

```sql
````

#### 2.4 Candidate reorganization + selection model

**Mechanism (2507 §III-D, Algorithm 3).** Selection model M_c = fine-tuned Qwen2.5-Coder-7B (listwise; trained on candidates from FT ensemble + GPT-4o; positives = any candidate with gold-equal execution; negatives = natural failures + LLM "controlled modifications" near-misses; all candidates "de-formalized" by an SQL formatter). Inference:
1. `L ← deformalize(L)`; execution-error candidates already excluded.
2. Cluster by execution result → C; `S^un = schema_union(S)`.
3. If |C| = 1 → return shortest SQL (no model call).
4. Sort clusters by size desc (inter-group); within cluster sort by generator order O (generators ranked by measured performance) (intra-group).
5. If |C″_1| ≥ ⌈|L|/2⌉ → present **all** candidates in that order; else present **one shortest SQL per cluster** in inter-group order.
6. l* = M_c(Q, S^un, E, L′). Rationale [V]: "Due to the selection tendency of LLMs towards options that appear earlier … this clustering and ranking approach … leverage strong consistency priors".
Preview §6: group by execution consistency, pick inconsistent samples from each group to form candidate set, fine-tuned selection model; training data paraphrased to match syntactic preferences.

Selection prompt, preview Appendix E Fig. 8 (https://arxiv.org/html/2411.08599v3/figures/candidate_selection.png) [T]:
```
You are a SQLite expert. Regarding the Question, there are {CANDIDATE_NUM} candidate SQL along with their Execution result in the database (showing the first 10 rows).
You need to compare these candidates and analyze the differences among the various candidate  SQL. Based on the provided Database Schema, Evidence, and Question, select the correct and reasonable result.

【Database Schema】
{DATABASE_SCHEMA}

【Evidence】
the oldest card refers to MIN(originalReleaseDate); mythic card refers to rarity = 'mythic'; legal play refers to status = 'legal'; play format refers to format

【Question】
When was the oldest mythic card released and what are its legal play formats?
==========

Candidate A
【SQL】
SELECT T1.originalReleaseDate, T2.format FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.rarity = 'mythic' AND T2.status = 'Legal' ORDER BY T1.originalReleaseDate LIMIT 1
【Execution result】
[(None, 'commander')]

********

Candidate B
【SQL】
SELECT T1.originalReleaseDate, T2.format FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.rarity = 'mythic' AND T2.status = 'legal' ORDER BY T1.originalReleaseDate LIMIT 1
【Execution result】
[]

********

Candidate C
【SQL】
SELECT MIN(c.originalReleaseDate) AS oldest_mythic_release_date, l.format
FROM cards AS c
JOIN legalities AS l ON c.uuid = l.uuid
WHERE c.rarity = 'mythic' AND l.status = 'Legal'
GROUP BY l.format
ORDER BY oldest_mythic_release_date
LIMIT 1;
【Execution result】
[('2009/4/25', 'commander')]

Please output the selected candidate as "A" or "B" or "C".
```

#### 2.5 XiYan numbers

- Headline: BIRD test 75.63 EX (dev 73.34), R-VES 71.41; Spider test 89.65; preview also SQL-Eval 69.86, NL2GQL 41.20.
- Preview Table 8 (BIRD dev, 3 candidates = 2 FT + 1 ICL GPT-4o): All 71.58; w/o FT generator 68.67 (−2.91); w/o ICL generator 70.27 (−1.31); w/o Refiner 71.03 (−0.55); w/o Selection model (self-consistency) 68.84 (−2.74); All with 5 candidates 73.34. (Text says 71.51 — mismatch with table's 71.58.)
- 2507 Table III (BIRD dev): full 73.34; w/o Schema Filter 72.10 (−1.24); only one SFT generator 69.30 (−4.04); only majority voting 70.21 (−3.13).
- 2507 Table VI single generators (BIRD dev, no linking/refine): GPT-4o zero-shot 58.47, few-shot 62.65; Qwen2.5-Coder-32B base 58.60 → SFT 64.67 → SFT+multi-task 66.88; Codestral-22B 50.52 → 62.32 → 65.25; Qwen2.5-Coder-14B 55.28 → 61.02 → 63.95; Qwen2.5-Coder-7B 50.39 → 56.06 → 60.10; DeepSeek-Coder-V2-Lite 40.61 → 51.49 → 55.99.
- Table VII (leave-one-out aux tasks, Qwen-32B rows 6–10): all 66.88; −Question inference 65.91; −Evidence inference 66.49; −Self-refine 65.71; none 64.67. (Codestral rows 1–5: 65.25 / 63.75 / 64.60 / 64.08 / 62.23.)
- Table VIII selection (BIRD dev, p_l=5 / p_l=10): majority voting 69.94 / 70.21; selector + random order (s1) 69.69 / 68.19; + order by generator performance (s2) 71.45 / 71.84; + candidate reorganization (s3) 72.29 / 73.34. (Text says majority voting "69.82%" — mismatch.)
- Table IX standalone selection ability (random order, 2/6/10 candidates): Qwen2.5-Coder-7B base 62.84; Gemini-1.5-pro 66.30; GPT-4o 67.47; fine-tuned selector 69.56.
- Fig. 4(b): upper bound at p_l=10 = 82.2%. Table X per generator Avg EX / contribution ratio CR: SQLG1 69.34/51.90; SQLG2 66.05/5.27; SQLG3 68.15/6.13; SQLG4 68.50/30.55; SQLG5 (GPT-4o ICL) 64.51/6.13; ~45% of BIRD dev is "unanimous".
- Table XII inference cost per sample: schema filter retrieval GPT-4o 413.9/37 tok, 11.75 s; selection GPT-4o 3791.5/63.1 tok, 6.77 s; generation per candidate Qwen-32B 582.5/47.8 tok 2.25 s, GPT-4o 763.2/54.7 tok 2.75 s; execution 0.35 s; selector 1052.3/1 tok 0.78 s; total ~6700/~205 tok, ~40.81 s.

**API-only reimplementable?** Partially: M-Schema, schema filter, ICL generator (GPT-4o in the paper), refiner prompt, and candidate-reorganization logic are prompt/code-only; the four fine-tuned generators and the fine-tuned 7B selector are not — substitute prompted variants (e.g. CTE-style / style-varied prompts) and a prompted selector (paper: GPT-4o selector 67.47 vs fine-tuned 69.56, Table IX).

---

### 3. OpenSearch-SQL (arXiv 2502.14913; repo github.com/OpenSearch-AI/OpenSearch-SQL)

#### 3.1 Pipeline mechanism

- Paper framework (§1, §3): Preprocessing → Extraction → Generation → Refinement, with Alignment after agents. No fine-tuning; GPT-4o-0513 for generation, bge-large-en-v1.5 for retrieval (§4.1).
- Preprocessing (§3.3): build DB schema; index **string-type** values only into a vector DB; build few-shot library: Query-SQL train pairs → self-taught Query-CoT-SQL via LLM; correction few-shots per error type.
- Extraction (§3.4): LLM entity extraction ("simple prompt") + LLM extraction prompt giving `#reason/#columns/#values`; value retrieval = embedding search with split retrieval for long phrases, top-K filtered by threshold; column filtering = LLM-selected tables/columns ∪ vector-retrieved columns above threshold. Repo `run/run_main.sh`: node order `generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation`; extraction temperatures 0.0; `column_retrieve` temperature 0.3, `top_k` 10; similarity threshold `shold=0.65` (`src/pipeline/column_retrieve_and_other_info.py`). Paper §4.1: "filtering index threshold value of 0.65"; few-shot count chosen from N={0,3,5,7,9}; max SQL votes from K={1,7,15,21}.
- Dynamic few-shot (§3.2, §3.5) [V]: "we first used Masked Question Similarity (MQs) (Guo et al., 2023) to select similar queries. Then, we upgraded the few-shots in the Query-SQL format by self-taught. … we used an LLM to supplement the CoT information to transform the NLQ into SQL" and "the system retrieves the top K_f most similar queries based on MQs, and uses their corresponding Query-CoT-SQL forms as the few-shot examples in the final instruction." Repo README [V]: "For few-shot, we adopted the DAIL-SQL method to generate few-shot examples." (few-shot text loaded from `Bird/fewshot/questions.json` `['prompt']`; extraction uses the first 5 `/* Answer the following:` blocks — `extract_col_value.py`).
- Generation (§3.5): progressive generation = structured CoT: #reason → #columns → #values → #SELECT → #SQL-like → #SQL; SQL-Like [V]: "a type of SQL language that ignores specific syntactical elements (such as JOINs and the formatting of functions)". Multiple candidates per NLQ; paper §4.5 "we used a single prompt to generate 21 results"; §4.6 says generation "uses BeamSearch"; repo config: `candidate_generate` temperature 0.7, `n` 21 (sampling).
- Alignment definition (§3.1) [V]: "A_Aligment(x+A′(x))=A(x)−A′(x) … The input for the agent is the input x for the agent to be aligned, along with A′(x). … the function of Alignment is to align the current Agent’s input information with its output result" and "after each agent completes its output, an Alignment agent is used to align the current agent’s output with that of the upstream agent … somewhat analogous to residual connections".
  - **Info Alignment** (end of Extraction) [V]: "align the style of the SELECT statement: extracting phrases or clauses from the NLQ that correspond one-to-one with the generated SELECT content. This ensures that both the quantity and order of the SELECT content meet expectations." Plus schema expansion: re-add each table's primary keys and all same-name columns of selected columns. Code: `query_order` with `select_prompt` (question atom parse) → `{q_order}` slot in the generation prompt.
  - **Agent Alignment** (post-generation): SQL columns/values vs DB-stored values (e.g. `'John'`→`'JOHN'`). Code `values_check`: literal not in retrieved values → embedding-nearest retrieved value if cosine > 0.95; literal exists but in other column/table → LLM rewrite prompt listing correct `col = 'val'` conditions.
  - **Function Alignment**: aggregate misuse, nesting, redundant JOINs. Code `double_check_function_align` = `JOIN_error` (`ON a=b OR …`/`IN` joins → keep one), `func_check2` (`ORDER BY MAX()/MIN() … LIMIT` fix), `time_check` (quote `strftime(...) op 1990` years).
  - **Style Alignment**: dataset conventions, e.g. `IS NOT NULL`, MAX vs `LIMIT 1`. Code `double_check_style_align` = `func_check` (`= (SELECT MAX(col) FROM t)` → `ORDER BY … LIMIT 1`), `is_not_null` (LLM adds `WHERE … IS NOT NULL` to `ORDER BY … LIMIT` without SUM/COUNT), `select_check` (drop `|| ' ' ||` concatenation; `table.*` → id).
  - Config: `"align_methods":"style_align+function_align+agent_align"`. §4.6: SELECT alignment runs every time; others only when issues are detected.
- Refinement (§3.6): Correction — execute; fix syntax errors / empty results with per-error-type few-shot + instructions. Code `correct_sql`: up to 3 correction rounds (temperature 0.2+count/5, top_p 0.3), then regenerate; NB the released code sets `fewshot=""` and `advice=""` right before formatting the correction prompt (error-type few-shot/advice effectively disabled). Self-consistency & vote [V]: "Exclude SQLs that cannot be fixed and those that result in empty answers and choose the option with the highest output consistency in the execution results. Additionally, among SQL queries with the same answers, we select the one with the shortest execution time." Code `vote.py::vote_single`: empty answers get 0 votes; ties → min `time_cost`.

#### 3.2 Prompts — verbatim

Paper Listing 1 (Query-SQL few-shot) [V]:
```
/* Answer the following:{question} */
#SQL: {SQL}
```
Paper Listing 2 (Query-CoT-SQL few-shot) [V]:
```
/* Answer the following:{question} */
#reason: Analyze how to generate SQL based on the question.
#columns: All columns ultimately used in SQL
#values: the filter in SQL
#SELECT: SELECT content table.column.
#SQL-like: SQL-like statements ignoring Join conditions
#SQL: {SQL}
```
Paper Listing 3 (correction few-shot) [V]:
```
{"Result: None": """/* Fix the SQL and answer the question */
#question: {question}
#Error SQL: {Raw SQL}
Error: Result: None
#values: {values in Database}
#Change Ambiguity: {Advice of correction}
#SQL:{corrected SQL}""",
...}
```
Paper Listing 4 (Extraction I/O) [V]:
```
Input:
/* Database schema */
{db_info}
{rule}
/* Answer the following: {query} */

Output:
{reason}
{column}
{values}
```
Paper Listing 5 (Generation example) [V]:
```
Input:
{fewshot}
/* Database schema */
{db_info}
{similar values}
{rule}
Rule Example: For parts involving division that contain integer types, CAST them to REAL

/* Answer the following: How many patients with a normal Ig A level came to the hospital after 1990? normal Ig A level refers to IGA > 80 AND IGA < 500; */
{info alignment}
Info Alignment Example: SELECT content: [How many patients]

Output:
#reason: The question wants to count the number of patients with a normal Ig A level who came to the hospital after 1990, so SELECT will count distinct patients based on the specified conditions.
#columns: Patient.ID, Laboratory.IGA, Patient.`First Date`
#values: normal Ig A level refers to Laboratory.IGA > 80 AND Laboratory.IGA < 500; came to the hospital after 1990 refers to strftime('%Y', Patient.`First Date`) >= '1990'
#SELECT: How many patients refer to COUNT(DISTINCT Patient.ID)
#SQL-like: Show COUNT(DISTINCT Patient.ID) WHERE Laboratory.IGA > 80 AND Laboratory.IGA < 500 AND YEAR(Patient.`First Date`) >= '1990'
#SQL: SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGA > 80 AND T2.IGA < 500 AND strftime('%Y', T1.`First Date`) >= '1990'
```
(Backtick/quote characters normalized from the HTML's typographic quotes.)
Paper Listing 6 (alignments) [V]:
```
Agent Alignment:
Raw SQL: SELECT ID FROM table WHERE table.name= 'John'
value in Database: table.name='JOHN'
Aligned SQL: SELECT ID FROM table WHERE table.name= 'JOHN'

Function Alignment:
Raw SQL: SELECT ID FROM table ORDER BY MAX(score)
Aligned SQL: SELECT ID FROM table GROUP BY ID ORDER BY score

Style Alignment:
Raw SQL: SELECT ID FROM table ORDER BY score DESC LIMIT 1
Aligned SQL: SELECT ID FROM table WHERE score IS NOT NULL ORDER BY score DESC LIMIT 1
```
Paper eq. (3) vote [V]: `SELECT SQL FROM K WHERE ans = (SELECT ans FROM K GROUP BY ans ORDER BY COUNT(*) DESC LIMIT 1) ORDER BY t LIMIT 1`, with K = {R_i = (SQL_i, ans_i, t_i)}.

Repo prompts actually wired in (`src/llm/prompts.py` class `db_check_prompts`; strings in `src/llm/all_prompt.py`, https://raw.githubusercontent.com/OpenSearch-AI/OpenSearch-SQL/main/src/llm/all_prompt.py). `all_prompt.py` holds many dead variants; these are the ones referenced by the pipeline nodes:

Extraction — `new_extract_prompt` (used by `extract_col_value.py`) [V]:
````
/* Some extract examples are provided based on similar problems: */
/* Answer the following: Please give the name of the course in which most numbers of the students got an A. Also, list the full name of the students who got an A in this course. most number of students got an A refers MAX(COUNT(student_id WHERE grade = 'A')); full name = f_name, l_name; got an A refers to grade = 'A'; */
#reason: The question requires display in order: "name of the course", "full name"."A" is filtering condition.
#columns: course.name, student.f_name, student.l_name, registration.grade, registration.student_id
#values: "A"

/* Answer the following:How much more votes for episode 1 than for episode 5? more votes refers to SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5)) */
#reason: The question requires display in order: "How much more vote". The definition of "more vote" is SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5)). 1, 5 are filtering conditions.
#columns: Episode.episode, Vote.votes
#values: "1", "5"

/* Answer the following: What is the average score of the movie "The Fall of Berlin" in 2019? Average score refers to Avg(rating_score); */
#reason: The question requires display in order: "average score". Average score is Avg(rating_score), "The Fall of Berlin",2019 are filtering conditions.
#columns: ratings.rating_score, ratings.rating_id, ratings.rating_timestamp_utc, movies.movie_title
#values: "The Fall of Berlin", "2019"

/* Answer the following: How many distinct orders were there in 2003 when the quantity ordered was less than 30? "year(orderDate) = '2003'; quantityOrdered < 30;" */
#reason:  The question requires display in order: "How many distinct orders"." in 2003", "less than 30" are filtering conditions.
#columns: orderdetails.orderNumber, orderdetails.quantityOrdered, orders.orderDate
#values: "30", "2003"

{fewshot}

/* Database schema */
{db_info}

Attention:
1. if the question have when\where\which, pay attention to pick table.column related to time, location and name in #columns
2. Please answer the question in the following format without any other content:
```
#reason: Analysis of which columns and values might be relevant to the question. Note that when dealing with questions about time, who, which, what, etc., you should keep column related to time, names, and locations in the #column.(format: The question query xxx, the related column include table.column, the values include values)
#columns: The top 10 columns relevant to the question( format: table.column_1, table.column_2 ...)
#values: Potential filter values that the question might query(format: "value1", "value2" ...)
```
/* Answer the following: {query} */
````
Entity extraction — `noun_prompt` (`extract_query_noun.py`) [V]:
```
Please extract all nouns and phrases from the following sentence, separating the results directly with a comma( format: "noun_1", "noun_2","phrases" ):
{raw_question}
```
Info (SELECT) alignment — `select_prompt` (`column_retrieve_and_other_info.py::query_order`, output fills `{q_order}`), Chinese [V]:
````
现在我们定义一个问句的语法原子单元如下:
Q: 询问词: 如 calculate\ Include\ List\ List out\ List all\ give\ state\ Name\ In which\ How many\  which\ what\ who\ when\ provide\ Tally\ identify\ Find\ mention\ write等
J: 判断词： 如 Do\ Did\ If\ Is\ Are等
I: 查询内容: 查询的主体内容, 如: name, ID, date, location, item, biggest city.
C: 条件句: 通过介词和连词引入的查询的要求或属性, 如大于、等于、排序、聚合等. 介词和连词有: of\ have\ with\ that\ by. 条件句的形式例子有: with condition\ have condition\ of attribute\ that was condition


一个问题通过这些原子串联起来。常见的串联方式有
QIC(询问句): List the student with score more than 80: Q: 'List' I: 'the student' C: 'with score more than 80'
JC(判断句): State if Tom is a Cat? : J: 'State if C: is a Cat?'
C(条件句): For all people in Beijing
现在请你针对下面的问题, 把问题中的内容按照上述原子定义提取出来
问题如下: {question}

请按照下面的json格式进行回答:

```json
[{{"Type":"类型(QIC,JC,C)",
"Extract":{{//不存在的填null
    "Q":"询问词",
    "J":"判断词",
    "I":['查询内容a', '查询内容b'],//只有查询内容用and或alongside连接时,才分成多个实体填入List
    "C":["条件句a","属性b"]
}}}},
{{}}]
```
````
(Gloss [INFERENCE]: defines question atoms Q=question word, J=judgment word, I=queried content, C=condition clause; asks for JSON extraction; "I" split into a list only when joined by and/alongside.)

Generation — `new_prompt_O` (`candidate_generate.py`) [V]:
````
{fewshot}

/* Database schema */
{db_info}
{key_col_des}

# Based on the database schema and the examples above, pay attention to the following:
1. For parts involving division that contain integer types, CAST them to REAL.
2. "#Values in Database" display part values from the database. Please ignore the unnecessary values.
3. Please refer to the examples above and answer in the following format without any other content:
```
#reason: Analyze how to generate SQL based on the question.(format: the question want to ..., so the SQL SELECT ... and ...)
#columns: All columns ultimately used in SQL(format: table.column_1, table.column_2)
#values: the filter in SQL (format: 'filter in question' refer to 'table.column <op> value'. e.g. 'name is not tom' refer to name <> 'tom', 'in 2007' refer to "strftime('%Y', Date) = '2007'")
#SELECT: SELECT content (format like: 'query in question' refer to table.column. The order of columns in the SELECT clause must be the same as the order in the question.)
#SQL-like: SQL-like statements ignoring Join conditions
#SQL: SQL
```

/* Answer the following: {question} */
{q_order}
````
Correction — `correct_prompt_wo_hint` (`align_correct.py` via `soft_check.correct_sql`) [V]:
````
You are an expert in SQL. Here are some examples of fix SQL
{fewshot}

/* Database schema is as follows: */
{db_info}
{key_col_des}

/* Now Plesease fix the following error SQL */
#question: {q}
#Error SQL: {result_info}
{advice}

Please answer according to the format below and do not output any other content.:
```
#reason: Analysis of How to fix the error
#SQL: right SQL
```
````
Self-taught CoT builder for the few-shot library — `prompts_fewshot_parse2` (`prompts_fewshot_parse.parse_fewshot`) [V]:
````
/* extract and rewrite example */
#question: Please give the name of the course in which most numbers of the students got an A. Also, list the full name of the students who got an A in this course. most number of students got an A refers MAX(COUNT(student_id WHERE grade = 'A')); full name = f_name, l_name; got an A refers to grade = 'A';
SQL: SELECT T3.name, T2.f_name, T2.l_name FROM registration AS T1 INNER JOIN student AS T2 ON T1.student_id = T2.student_id INNER JOIN course AS T3 ON T1.course_id = T3.course_id WHERE T1.grade = 'A' GROUP BY T3.name ORDER BY COUNT(T1.student_id) DESC LIMIT 1
#reason: The question requires display in order: "name of the course", "full name"."A" is filtering condition.
#columns: course.name, student.f_name, student.l_name, registration.grade, registration.student_id
#SELECT: "name of the course" refer to course.name, "full name" refer to student.f_name, student.l_name
#values: got an A refers to registration.grade = 'A'
#SQL-like: Show course.name, student.f_name, student.l_name, where registration.grade = 'A' , group by course.name, order by the number of T1.student_id

/* extract and rewrite example */
#question:How much more votes for episode 1 than for episode 5? more votes refers to SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5))
SQL: SELECT SUM(CASE WHEN T1.episode = 1 THEN T2.votes ELSE 0 END) - SUM(CASE WHEN T1.episode = 5 THEN T2.votes ELSE 0 END) AS diff FROM Episode AS T1 INNER JOIN Vote AS T2 ON T2.episode_id = T1.episode_id;
#reason: The question requires display in order: "How much more vote". The definition of "more vote" is SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5)). 1, 5 are filtering conditions.
#columns: Episode.episode, Vote.votes
#SELECT: more votes for episode 1 than for episode 5 refer to SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5))
#values:  episode 1 refer to Episode.episode = 1,  episode 5 refer to Episode.episode = 5
#SQL-like: Show SUBTRACT(SUM(votes when episode = 1), SUM(votes when episode = 5))

/* extract and rewrite example */
#question: What is the average score of the movie "The Fall of Berlin" in 2019? Average score refers to Avg(rating_score);
SQL: SELECT SUM(T1.rating_score) / COUNT(T1.rating_id) FROM ratings AS T1 INNER JOIN movies AS T2 ON T1.movie_id = T2.movie_id WHERE T1.rating_timestamp_utc LIKE '2019%' AND T2.movie_title LIKE 'The Fall of Berlin'
#reason: The question requires display in order: "average score". Average score is Avg(rating_score), "The Fall of Berlin",2019 are filtering conditions.
#columns: ratings.rating_score, ratings.rating_id, ratings.rating_timestamp_utc, movies.movie_title
#SELECT: average score refer to Avg(rating_score)
#values: 'The Fall of Berlin' refer to movies.movie_title = 'The Fall of Berlin', 2019 refer to ratings.rating_timestamp_utc = 2019
#SQL-like: Show Avg(rating_score), where ratings.rating_timestamp_utc = 2019 and movies.movie_title = 'The Fall of Berlin'

/* extract and rewrite example */
#question: How many distinct orders were there in 2003 when the quantity ordered was less than 30? "year(orderDate) = '2003'; quantityOrdered < 30;"
SQL: SELECT COUNT(DISTINCT T1.orderNumber) FROM orderdetails AS T1 INNER JOIN orders AS T2 ON T1.orderNumber = T2.orderNumber WHERE T1.quantityOrdered < 30 AND STRFTIME('%Y', T2.orderDate) = '2003'
#reason:  The question requires display in order: "How many distinct orders". " in 2003", "less than 30" are filtering conditions.
#columns: orderdetails.orderNumber, orderdetails.quantityOrdered, orders.orderDate
#SELECT: How many distinct orders refer to COUNT(DISTINCT orderdetails.orderNumber)
#values: 30 refer to quantityOrdered < 30, 2003 refer to year(orderDate) = '2003'
#SQL-like: Show COUNT(DISTINCT orderdetails.orderNumber), where orders.orderDate = 2003 and orderdetails.quantityOrdered < 30

#Please provide answer based on the requirements below using the provided questions and SQL:
1. After #reason, follow the example above to analyze how to generate SQL based on question.
2. After #columns, Provide candidate columns for the question generate SQL
3. After #SELECT, provide the content that SQL should display in order
4. After #values, provide the filtering conditions that exist in SQL
5. After #SQL-like, rewrite the question to SQL-like in the format: "Show #SELECT (table.column), WHERE condition are xxx (refer to #values), Group by/Order By (refer to columns)
6. The text format you will receive is:
```
#question: {{question}}
SQL:{{SQL}}
#answer:
```
Please respond in the following format without any other content:
``` 
#reason: Analyze how to generate SQL based on the question.
#columns: All columns ultimately used in SQL
#SELECT: the content that SQL should display in order
#values: the filtering conditions that exist in SQL 
#SQL-like: SQL-like statements that ignore join conditions
```

Now, you need to process the following text:
#question: {question}
SQL: {sql}
#answer:
````
Alignment LLM prompts (inline f-strings in `src/runner/check_and_correct.py`, Chinese) [V]:
```
# is_not_null (style)
请你为下面SQL ORDER BY的条件加上WHERE IS NOT NULL限制:
SQL:{SQL}

请直接给出新的SQL, 不要回复任何其他内容:
#SQL:

# func_check2 (function): ORDER BY MAX()/MIN() ... LIMIT
对于下面的qustion和SQL:
#question: {question}
#SQL: {SQL}

ERROR: {res.group()} 是一种不正确的用法, 请对SQL进行修正, 注意如果SQL中存在GROUP BY, 请判断{res.groups()[0]}的内容是否需要使用 SUM({res.groups()[2]})

请直接给出新的SQL, 不要回复任何其他内容:

# func_check (style): nested MAX/MIN subquery
对于下面的问题和SQL, 请根据ERROR和#change ambuity修改:
#question: {question}
#SQL: {sql}
ERROR:{",".join(origin_f)} 不符合要求, 请使用 JOIN ORDER BY LIMIT 形式代替
#change ambuity: {func_amb}

请直接给出新的SQL, 不要回复任何其他内容:

# values_check (agent alignment)
Database Schema:
{new_db_info}

#question: {question}
#SQL: {sql}
ERROR: 数据库中不存在: {', '.join(badval_l)}
请用以下条件重写SQL:\n{v_l}

请直接给出新的SQL,不要回复任何其他内容:
#SQL:
```
(Gloss [INFERENCE]: add WHERE IS NOT NULL to ORDER BY condition; "X is an incorrect usage, fix it; if GROUP BY exists decide whether SUM(...) is needed"; "replace nested form with JOIN ORDER BY LIMIT"; "values not in database: …, rewrite SQL with these conditions"; all end "output only the new SQL".) `vote_prompt` (LLM pick among SQLs, Chinese) exists but `vote.py` uses the execution-result vote.

#### 3.3 Numbers (https://arxiv.org/html/2502.14913)

- Table 2 (BIRD leaderboard): OpenSearch-SQL+GPT-4o dev 69.30, test 72.28, R-VES 69.36; +GPT-4 dev 66.62; GPT-4o w/o Self-Consistency & Vote dev 67.80. Baselines: DAIL-SQL+GPT-4 54.76/57.41/54.02; MCS-SQL+GPT-4 63.36/65.45/61.23; CHESS 65.00/66.69/62.77; Distillery+GPT-4o(ft) 67.21/71.83/67.41.
- Table 3 (Spider test): OpenSearch-SQL+GPT-4 86.8; +GPT-4o 87.1.
- Fig. 3: SC & vote gives +7.64 abs on challenging questions, little on easy/medium.
- Table 4 (BIRD Mini-Dev; EX_G single generated SQL / EX_R single SQL after refinement / EX final):

| Setup | EX_G | ΔEX_G | EX_R | ΔEX_R | EX_R−EX_G | EX | ΔEX | EX−EX_R |
|---|---|---|---|---|---|---|---|---|
| Full pipeline | 65.8 | – | 68.2 | – | +2.4 | 70.6 | – | +2.4 |
| w/o Extraction | 61.6 | −4.2 | 66.2 | −2.0 | +4.6 | 67.4 | −3.2 | +1.4 |
| w/o Values Retrieval | 64.4 | −1.4 | 66.6 | −1.6 | +2.2 | 69.2 | −1.4 | +2.6 |
| w/o column filtering | 63.2 | −2.6 | 65.0 | −3.2 | +1.8 | 68.6 | −2.0 | +3.6 |
| w/o Info Alignment | 62.8 | −3.0 | 67.6 | −0.6 | +4.8 | 68.6 | −2.0 | +1.0 |
| w/o Few-shot (generation) | 60.4 | −5.4 | 63.0 | −5.3 | +2.6 | 66.0 | −4.6 | +3.0 |
| w/o CoT | 63.0 | −2.8 | 66.2 | −2.0 | +3.2 | 69.2 | −1.4 | +2.6 |
| w/o Alignments | 65.8 | – | 67.0 | −1.2 | +1.2 | 69.6 | −1.0 | +2.6 |
| w/o Refinement | 65.8 | – | 67.0 | −1.2 | +1.2 | 67.0 | – | – |
| w/o Correction | 65.8 | – | 67.0 | −1.2 | +1.0 | 69.8 | −0.8 | +2.8 |
| w/o Few-Shot (refinement) | 65.8 | – | 67.6 | −0.6 | +1.6 | 69.4 | −1.2 | +1.8 |
| w/o Self-Consistency & Vote | 65.8 | – | 68.2 | – | – | 68.2 | – | – |

- Table 5 (few-shot format, Mini-Dev): Query-CoT-SQL 65.8 / 68.2 / 70.6; w/o few-shot of Generation 59.6 (−6.2) / 63.0 / 66.0 (−4.6); Query-SQL pairs 63.0 (−2.8) / 66.2 / 69.2 (−1.4); w/o few-shot of Refinement 65.8 / 67.6 / 69.4; w/o both 59.6 / 62.8 / 66.0. (§4.4 text says "+3.0%" vs Query-SQL and "+6.4%" vs none — table shows 2.8 and 6.2; mismatch.)
- Table 7 (CoT, no few-shot): w/o CoT EX_G 57.6, EX_V 59.2; unstructured CoT ("let's think step by step") 58.2 / 63.0; structured CoT 58.8 / 65.0.
- §4.5: GPT-4o EX rises monotonically over N={1,3,7,15,21}; GPT-4o-mini best at 7 and 15.
- Table 6 (cost, GPT-4o): Extraction 4–9 s, 5k–10k tok; Generation 5–15 s, 4k–8k tok; Refinement 0–25 s, 0–5k tok; Alignments 0–15 s, 500–2000 tok (SELECT Alignment 1–3 s every time); vote <0.01 s; pipeline 7–60 s, 9k–25k tok.

**API-only reimplementable?** Yes — entirely prompted general LLM + rules + an embedding retriever (paper: bge-large-en-v1.5, local) + execution; 21 samples/question at T=0.7 (if the API has no `n`, 21 separate calls [INFERENCE]).

---

### 4. Agentar-Scale-SQL (arXiv 2509.24403; repo github.com/antgroup/Agentar-Scale-SQL)

#### 4.1 Mechanism

- Offline (§3.1): two schema views — Markdown "light schema" for ICL with general LLMs, standard DDL schema for the fine-tuned code model; textual cell values indexed in a vector store VD_cell; training set indexed in VD_example keyed by **skeleton-extracted question** embeddings. Implementation: LangChain/LangGraph, chroma, all-MiniLM-L6-v2 embeddings (§4.1).
- Step 1 Task Understanding (§3.2): one LLM call (Gemini-2.5-Flash, T=0.2) extracts database literals + question skeleton → retrieve cells from VD_cell and few-shot examples from VD_example.
- Step 2 SQL Generation Scaling:
  - **Internal scaling** — Reasoning generator M_reasoning: fine-tuned from OmniSQL-32B with GRPO (Arctic-Text2SQL-R1-style), BIRD train only; reward R_G = 1 if execution matches gold, 0.1 if SQL executable, 0 otherwise; KL to SFT reference. Uses DDL schema. Released as Agentar-Scale-SQL-Generation-32B (HF/ModelScope, 2025-11-27 per repo README).
  - **Parallel scaling / diverse synthesis** — ICL generator M_ICL: proprietary LLMs (Gemini-2.5-Pro at T=0.5 and T=1.8; GPT-5 minimal reasoning effort) with light schema + retrieved examples; diversity via varied prompts (three styles: direct, CoT, problem decomposition), randomized example order, multiple LLMs, temperatures.
  - Default candidate pool: **9 ICL + 8 reasoning = 17** (§4.1).
  - **Sequential scaling / iterative refinement** (§3.3.3): SQL fixer (LLM, conditionally activated on syntax errors) + SQL revisor (LLM agent for logical flaws); queries grouped by execution outcome and one random query per group is refined. Both use Gemini-2.5-Pro.
- Step 3 SQL Selection Scaling (§3.4) [V]: "First, we consolidate an initial pool of queries by grouping them based on identical execution results on a database D. A single representative is chosen from each group to form a candidate set C′={c_1,…,c_m}. Second, these candidates compete in a pairwise round-robin tournament. For each pair (c_i,c_j), a reasoning selector ℳ_selection determines a winner based on the question, light schema, and execution results, incrementing the winner’s score W_i. The final query is the one with the maximum score". Selector = Qwen2.5-Coder-32B-Instruct + GRPO on 8.5k constructed samples; reward R_S = 1 if selection correct else 0. Selector checkpoint not released yet (repo roadmap unchecked "Release Agentar-Scale-SQL-Selection-32B").
- Prompted general LLMs: Task Understanding, ICL generator, fixer, revisor. Fine-tuned (RL): reasoning generator, reasoning selector. No dedicated schema linking (App. D).
- Repo release status (README roadmap): released Light Schema Engine + offline preprocessing + generation-32B model; **not** released: task understanding/ICL generation code, reasoning-generation code, refinement, selection.

#### 4.2 Light schema format (Fig. 2, https://arxiv.org/html/2509.24403v6/light_schema.svg) [T]
```
## Table: yearmonth
### Column information
| column_name   | column_type   | column_description   | value_examples                       |
|:--------------|:--------------|:---------------------|:-------------------------------------|
| CustomerID    | integer       | Customer ID          | [32993, 40937, 39582]                |
| Date          | text          | Date                 | ['201209', '201311', '201308']       |
| Consumption   | real          | Consumption          | [5422.18, 5457.75, 57.97]            |
### Primary keys
['CustomerID', 'Date']
### Foreign keys
['yearmonth.CustomerID = customers.CustomerID']
```
DDL view in the same figure [T]:
```
CREATE TABLE yearmonth (
    CustomerID INTEGER, -- example: [32993, 40937, 39582]
    Date TEXT, -- example: ['201209', '201311', '201308']
    Consumption REAL, -- example: [5422.18, 5457.75, 57.97]
    PRIMARY KEY (CustomerID, Date),
    CONSTRAINT fk_yearmonth_customerid FOREIGN KEY (CustomerID) REFERENCES customers (CustomerID)
);
```

#### 4.3 Prompts — verbatim (Appendix F; decoded from the listing data URLs in https://arxiv.org/html/2509.24403, Figs. 9–18) [V]

Fig. 9 Task Understanding — system:
````
# Task Description
You are a text-to-SQL expert who is excellent in analysing text-to-SQL question. You are given ['Database Schema', 'Question', 'Evidence'], you need to **comprehensively analyse the question** by:
1. Identifying the database literals appeared in the question or the evidence. Database literal refers to a specific value that belongs to a column (e.g., "Japan", "Chinese Grand Prix"). These values are used in the WHERE clause to conduct effective filtering.
2. Generating a question skeleton. The question skeleton contains the question structure while ignoring the detailed database information (entity names, column names).

# Guideline for identifying database literals
1. Taking both the question and the evidence into account.

# Guideline for generating a question skeleton
1. Replace **all the database literals** in the question with the database column it belongs to.
2. Replace **all the database columns** with the placeholder <COLUMN>.
3. Keep SQL keywords such as "average", "total", "difference", "count" in the question skeleton.

# Example of the question mapping to skeleton
Question: Name movie titles released in year 1945. Sort the listing by the descending order of movie popularity.
Skeleton: Name <COLUMN> released in <YEAR>. Sort the listing by the descending order of <COLUMN>.

Question: In August of 1996, how many orders were placed by the customer with the highest amount of orders?
Skeleton: In <MONTH> of <YEAR>, how many <COLUMN> were placed by the <COLUMN> with the the highest amount of <COLUMN>?

Question: Calculate the total production for each product which were supplied from Japan.
Skeleton: Calculate the total <COLUMN> for each <COLUMN> which were supplied from <COUNTRY>.

Question: Calculate the difference in the average number of low-priority orders shipped by truck in each month of 1995 and 1996.
Skeleton: Calculate the difference in the average number of <COLUMN> in each month of <YEAR> and <YEAR>.

# About Output
**Do not return explanations or reasoning process.**
The output should be formatted as a JSON instance that conforms to the JSON schema below.

As an example, for the schema {"properties": {"foo": {"title": "Foo", "description": "a list of strings", "type": "array", "items": {"type": "string"}}}, "required": ["foo"]}
the object {"foo": ["bar", "baz"]} is a well-formatted instance of the schema. The object {"properties": {"foo": ["bar", "baz"]}} is not well-formatted.

Here is the output schema:
```
{"properties": {"database_literals": {"description": "The database literals extracted from the question and evidence.", "items": {"type": "string"}, "title": "Database Literals", "type": "array"}, "question_skeleton": {"description": "the generated question skeleton", "title": "Question Skeleton", "type": "string"}}, "required": ["database_literals", "question_skeleton"]}
```
````
Fig. 10 Task Understanding — user:
```
# Database Schema
{Database Schema}

# Question
{Question}

# Evidence
{Evidence}

Begin! Take a deep breath and think logically.
[no prose][output json Only]
```
Fig. 11 Reasoning Generator (fine-tuned model input):
````
Task Overview:
You are a data science expert. Below, you are provided with a database schema and a natural language question. Your task is to understand the schema and generate a valid SQL query to answer the question.

Database Engine:
{dialect}

Database Schema:
{Database Schema}
This schema describes the database's structure, including tables, columns, primary keys, foreign keys, and any relevant relationships or constraints.
Matched contents:
{matched_contents}
Matched contents presents values related to the question, together with their source table and column, for your reference in SQL generation.
Question:
{evidence}
{question}

Instructions:
- If Matched contents is provided, you can use it as reference when generating the SQL query.
- Make sure you only output the information that is asked in the question. If the question asks for a specific column, make sure to only include that column in the SELECT clause, nothing more.
- The generated query should return all of the information asked in the question without any missing or extra information.
- Before generating the final SQL query, please think through the steps of how to write the query.

Output Format:
In your answer, please enclose the generated SQL query in a code block:
```sql
-- Your SQL query
```

Take a deep breath and think step by step to find the correct SQL query.
````
Fig. 12 Database Admin Instruction (fills `{Database Admin Instruction}` in Fig. 13):
```
1. **SELECT Clause:**
    - Only select columns mentioned in the user's question.
    - Avoid unnecessary columns or values.
2. **Aggregation (MAX/MIN):**
    - Always perform JOINs before using MAX() or MIN().
3. **ORDER BY with Distinct Values:**
    - Use `GROUP BY <column>` before `ORDER BY <column> ASC|DESC` to ensure distinct values.
4. **Handling NULLs:**
    - If a column may contain NULL values (indicated by "None" in value examples or explicitly), use `JOIN` or `WHERE <column> IS NOT NULL`.
    - When a field is sorted in ascending order, also apply a NOT NULL filter to it.
    - When using the MIN() function on a column, also include a WHERE clause to filter NULL values from that column.
5. **FROM/JOIN Clauses:**
    - Only include tables essential to answer the question.
6. **Strictly Follow evidences:**
    - Adhere to all provided evidences.
7. **Thorough Question Analysis:**
    - Address all conditions mentioned in the question.
8. **DISTINCT Keyword:**
    - Use `SELECT DISTINCT` when the question requires unique values (e.g., IDs, URLs).
    - Refer to column statistics ("Value Statics") to determine if `DISTINCT` is necessary.
9. **Column Selection:**
    - Carefully analyze column descriptions and evidences to choose the correct column when similar columns exist across tables.
10. **String Concatenation:**
    - Never use `|| ' ' ||` or any other method to concatenate strings in the `SELECT` clause.
11. **JOIN Preference:**
    - Prioritize `INNER JOIN` over nested `SELECT` statements.
12. **SQLite Functions Only:**
    - Use only functions available in SQLite.
13. **Date Processing:**
    - Utilize `STRFTIME()` for date manipulation (e.g., `STRFTIME('%Y', SOMETIME)` to extract the year).
14. **Formatting:**
    - Pay close attention to any formatting requirements in the question, such as specific decimal places or percentage representation. These are not just suggestions; they are critical parts of the final answer and must be implemented using appropriate SQL functions (e.g., ROUND() and multiplying by 100).
    - Use `ROUND()` to round the result to a specific number of decimal places.
    - Use `* 100` to convert a fraction to a percent (%).
```
Fig. 13 ICL Generator with CoT — system:
````
# Your Role
You are an experienced database expert. As a SQL expert, formulate a precise SQL query to resolve the user's question. You must carefully analyze the database schema, the question's intent, and any provided examples or experience to ensure correctness and efficiency.
The database stores millions of cell values, you need to write a SQL query that can be executed in **less than 20.0 seconds**. Otherwise the business will be effected and lose millions of dollars.

# Database Engine
{dialect}

# Database Admin Instruction
{Database Admin Instruction}

# Input Information
You are provided with ['Examples', 'Database Schema', 'Question', 'Evidence'].
**Examples** are the similar question-SQL pairs which are annotated by other experienced database experts.
**Database schema** are the database structure. It contains table names, column names, column types, primary key and foreign key relationship. It also contains some relevant database cell values to the question.
**Question** is your task to answer.
**Evidence** contains expert experience about the question. It is **very important reference** to answer the question.

# About Output
Please return your analysis and then write the SQL query in a code block:
1. Decompose the question and evidence, then map the question and evidence to the schema.
2. [Important] If the SQL query does not require any subqueries, write the complete SQL query directly.
3. [Important] If the SQL query does require subqueries, **first write the subquery (or subqueries), then write the main (outer) query that uses them**.
4. You need to enclose the final SQL query in a code block using the following format:
```sql

```

## Here is an example about the process of analysing question and generating SQL query
### Question
How many users have rated the most popular movie?
### Evidence

### Answer
Step 1: Decompose the question.
- We are asked to count the number of users who have rated the most popular movie.
- This requires us to first identify the most popular movie (a subquery is needed), then count the ratings for that movie.

Step 2: Write the subquery to find the most popular movie.
```sql
SELECT movie_id
FROM movies
ORDER BY movie_popularity DESC
LIMIT 1
```

Step 3: Write the main query to count the ratings for that movie.
```sql
SELECT COUNT(rating_id)
FROM ratings
WHERE movie_id = (
    SELECT movie_id
    FROM movies
    ORDER BY movie_popularity DESC
    LIMIT 1
)
```
````
Fig. 14 ICL Generator with CoT — user:
```
# Examples
{Examples}

# Database Schema
{Database Schema}

# Question
{Question}

# Evidence
{Evidence}

Begin! Take a deep breath and think logically.
```
Fig. 15 SQL Fixer — system:
````
# About Role
You are a database expert excellent in writing SQL query. Your task is to correct a wrong SQL query.

# SQL Engine
{dialect}

# Input Information
- Database schema: Contains the full structure of the database.
- Question: The natural language question that needs to be answered.
- Evidence: Key information extracted from the question and/or database that helps answer it.
- Original SQL: The SQL query that was previously executed but resulted in an error or empty result.
- Execution Result: The outcome of executing the original SQL. It can be a database error or an empty result.

# Task Description:
Correct the SQL query accordingly:
   - Fix any syntax errors.
   - Adjust filtering conditions or column references based on evidence.
   - Remove unnecessary JOINs if they lead to empty intersections.
   - Ensure the corrected SQL still corresponds one-to-one with the targets and conditions in the question.

# About Output
Directly output the SQL query in the code block:
```sql
```
````
Fig. 16 SQL Fixer — user:
```
# Database Schema
{Database Schema}

# Question
{Question}

# Evidence
{Evidence}

# Original SQL
{Original SQL}

# Execution Result
{Execution Result}

Begin! Take a deep breath and think logically.
[no prose][output result Only]
```
Fig. 17 Reasoning Selector — system:
```
You are an advanced SQL evaluation assistant. Your task is to evaluate multiple SQL query candidates in response to a schema-related question. For each candidate, you will be provided with the SQL query and its execution result. Carefully analyze the query and its result for correctness, completeness, and relevance to the question and schema. Select the candidate that best answers the question, and briefly explain your reasoning.

# SQL Engine
sqlite

# About Input
The user will provide you with ['Database Schema', 'Matched contents', 'Evidence', 'Question', 'SQL Candidates']. Use this information to evaluate which SQL candidate best answers the question.

# About Output
- You are encouraged to provide your reasoning process before giving the final answer.
- For the final answer, output only the selected SQL label, wrapped clearly
    within `\\boxed{}` for easy identification and extraction.
- Example: If you select SQL candidate 2, output: `\\boxed{2}`
```
Fig. 18 Reasoning Selector — user:
```
# Database Schema:
{Database Schema}
# Matched contents:
Matched contents present values related to the question, together with their source table and column, for your reference in SQL selection.
{matched_contents}
# Evidence:
{evidence}
# Question:
{question}
# SQL Candidates:
{candidates}
```
Not published: SQL revisor prompt, direct and decomposition ICL prompt styles ("For the complete list, please refer to the code repository" — that code is not yet released).

#### 4.4 Numbers (https://arxiv.org/html/2509.24403)

- Table 1: BIRD dev 74.90, test 81.67, R-VES 77.00 (rank #1, "dated November 27, 2025"). Prior: AskData+GPT-4o 76.14/80.88/76.24; CHASE-SQL+Gemini 74.90/76.02/69.94; XiYan-SQL 73.34/75.63/71.41; Gemini-SQL single model 72.62/76.13.
- Table 2 ablation (BIRD dev; Simple/Moderate/Challenging/Total, Δ):
  - Full 79.35 / 69.40 / 64.14 / 74.90
  - w/o Task Understanding 79.14 / 68.32 / 64.14 / 74.45 (−0.45)
  - w/o Reasoning SQL Generator 74.92 / 63.79 / 58.62 / 70.01 (−4.89)
  - w/o ICL SQL Generator 75.89 / 66.38 / 55.86 / 71.12 (−3.78)
  - w/o Iterative Refinement 78.92 / 68.75 / 63.45 / 74.38 (−0.52)
  - w/o SQL Selection Scaling (= execution-result majority vote) 77.95 / 66.59 / 62.76 / 73.08 (−1.82)
- §4.4 upper bounds: ICL generator 81.36%, reasoning generator 75.88%, both 84.29%; reasoning better on simple/moderate, ICL better on challenging.
- §4.5: Pass@k over 1–16 candidates; gains largest up to 8, then diminish; biggest on challenging.
- Table 3 (BIRD test): Simple 949 q EX 86.83, Moderate 555 q 78.20, Challenging 285 q 71.23, total 1789 q 81.67; Soft F1 82.65; R-VES 77.00.
- Table 5 estimated LLM calls/question: Task Understanding 1, Generation 17, Refinement 1–51, Selection 1–561, total 20–630 (vs CHASE-SQL+Gemini 297, Contextual-SQL 2048).

**API-only reimplementable?** Partially: task understanding, ICL generator (3 prompt styles × temps × models), fixer/revisor and the execution-grouped round-robin tournament are prompt/code-only (selector prompts published); the GRPO-trained reasoning generator and selector are not (generator weights are public but need self-hosting; a prompted reasoning model would stand in for both).

---

### 5. Mismatches and caveats (DAIL-SQL, XiYan-SQL, OpenSearch-SQL, Agentar-Scale-SQL)

1. DAIL-SQL: §3.3 Euclidean vs Algorithm 1 cosine (code = Euclidean); τ 0.9 (paper) vs 0.85 (leaderboard + code); example-prefix text differs between paper Listing 8 and code; released `count_tokens()` returns 0 (context budget never enforced).
2. XiYan preview Table 8 "All" 71.58 vs text 71.51; XiYan-2507 majority voting 69.94/70.21 (Table VIII) vs text 69.82; "Appendix I/II" (ICL generator, data construction) referenced but absent from arXiv v2.
3. M-Schema: code puts `Primary Key` after the description, figures put it before; "【Foreign Keys】" (paper text) vs "【Foreign keys】" (code/figures).
4. OpenSearch-SQL: few-shot gains in §4.4 text (+3.0/+6.4) ≠ Table 5 (2.8/6.2); "BeamSearch" in paper vs `n=21`, T=0.7 sampling in repo config; released correction code blanks the per-error few-shot/advice; several alignment prompts are Chinese.
5. Agentar-Scale-SQL: ablation text says w/o Task Understanding "improves by 0.45" while the table shows a drop; most pipeline code (ICL, refinement, selection) and the selector model are unreleased as of the README read.
