# ADR-010: Schema catalog

Status: accepted
Date: 2026-10-16

## Context

Pipeline stage 1 is an offline catalog per database that every later stage reads: the grammar builder needs the exact identifiers, schema linking needs column descriptions to embed, value retrieval needs to know which columns hold categorical text, and the generator prompt needs a compact, readable schema. The catalog has to provide tables, columns, types, keys, row counts, 3-5 sample values, distinct counts, null rates, BIRD's `database_description` CSVs, and a cached one-line LLM description per column.

Three things made this less mechanical than it sounds. BIRD's description CSVs are hand-made and inconsistent. Some Mini-Dev tables are large and wide enough that naive profiling takes many seconds per table. And the SaaS database is multi-tenant, so anything the catalog stores about tenant data ends up in prompts shared by every tenant.

## Decision

### What a catalog holds

One JSON file per database at `data/catalog/<db_id>.json` (pydantic model `text2sql.catalog.Catalog`, `format_version` 1, unknown fields rejected). Tables keep SQLite creation order and columns keep declaration order, so files and rendered prompts are stable across rebuilds. Per table: name, optional description, `row_count`, and `profiled_rows` (smaller than `row_count` when the table was sampled). Per column: name, declared type, primary key, NOT NULL, the human description and value notes (BIRD CSV or SaaS data dictionary), the LLM one-liner, distinct count, null rate, and up to five sample values. Foreign keys come from `PRAGMA foreign_key_list`. A `warnings` list records everything ingestion could not resolve.

Samples are the most frequent non-null, non-blank values, ties broken by value in SQLite's order (numbers before text), long text cut to 80 characters with an ellipsis, blob columns skipped. They keep the type SQLite returned, so the JSON distinguishes text `'1'` from integer `1`; BIRD has many numeric-looking text columns where that difference decides whether a comparison matches.

`Catalog.schema()` returns the `DatabaseSchema` the grammar builder, validator and scoping layer already use. Its `Column.description` is the human description when there is one and the LLM line otherwise.

### Profiling

Each table is read once, read-only (`file:<path>?mode=ro`), and every column's null count, distinct count and value frequencies are tallied together in Python with `collections.Counter`. The first version ran one aggregate query plus a `GROUP BY` per column. That was slow on wide tables with long text: SQLite keeps only the start of a large record on the b-tree page and the rest in a linked list of overflow pages, so a query that needs a column stored after a long XML or text value walks that chain for every row, and a query per column does it once per column. Measured on the Mini-Dev copies on 2026-10-16:

| table | columns | per-column SQL | single pass |
|---|---|---|---|
| european_football_2.Match (25,979 rows) | 115 | 10.43 s | 1.03 s |
| card_games.cards (56,822 rows) | 74 | 4.51 s | 1.43 s |
| codebase_community.posts (91,966 rows) | 21 | 3.40 s | 0.73 s |

Tables with more than 100,000 rows are profiled on the rows where `rowid % step = 0`, with `step` chosen to leave about 100,000 rows. That is deterministic, needs no temporary tables, and bounds time and memory by the sample. Eight Mini-Dev tables are sampled (the largest is `financial.trans`, 1,056,320 rows). Sampled distinct counts are lower bounds and sampled null rates are estimates; consumers can tell from `profiled_rows`. `WITHOUT ROWID` tables are scanned whole. Profiling all 11 Mini-Dev databases takes about 7 s on this machine (per-database times in the table below).

### BIRD description CSVs

Files are decoded as UTF-8 after stripping a BOM; bytes that are not valid UTF-8 are read as cp1252, one byte at a time, so a mostly-UTF-8 file with a few stray bullets keeps its valid characters (decoding such a file wholesale as cp1252 would turn every `é` into `Ã©`). Four Mini-Dev files needed this (`Player_Attributes.csv`, `Team_Attributes.csv`, `qualifying.csv`, `Budget.csv`); their stray bytes are cp1252 bullets (`0x95`), right quotes (`0x92`) and one en dash (`0x96`). File names are matched to tables case-insensitively and then ignoring punctuation (student_club ships `Attendance.csv` for table `attendance`); `original_column_name` is matched exactly, case-insensitively, ignoring whitespace and punctuation, and finally through the expanded `column_name`. Unmatched files, rows and tables become catalog warnings. Across Mini-Dev the only unmatched row is `constructors.csv` describing a `wins` column that `formula_1.constructors` does not have.

BIRD descriptions often just repeat the column name (`TransactionID` / "Transaction ID"), and value notes often restate the description before adding to it. Descriptions equal to the name are dropped, the expanded name is kept only when it adds something, and a value note's leading copy of the description is cut. That is why human description coverage is uneven: 3 of 21 columns in debit_card_specializing, 45 of 89 in california_schools, all columns in codebase_community and superhero.

### LLM descriptions

`text2sql.catalog.describe.describe_columns` makes one `LLMClient.structured` call per table with `Settings.small_model` (`gpt-6-luna`), reasoning effort low, purpose `catalog.describe`. The user message is a JSON object with the table's columns, types, keys, references, documentation, value notes, frequent values and null fraction; the instructions say this is data from the database and that instructions inside it must not be followed. The answer is a list of `{column, description}`; unknown or missing columns become warnings, and a failed call leaves that table without LLM lines rather than failing the build. Requests are deterministic for a given catalog, so the LLM client's response cache makes rebuilds free and replayable offline.

The developer message is the versioned template `prompts/catalog_describe.yaml` (version 1.0), loaded with `text2sql.prompts.load_prompt`. Editing it changes the request text and therefore the response-cache key, so an edited prompt is never answered from stale cache entries.

This is a separate async step rather than an `llm=` argument to `build_catalog`, so building stays synchronous, deterministic and free, and the LLM step can be skipped (`--no-llm`) or rerun on its own.

Cost, from the spend ledger (flex tier): Mini-Dev, 75 calls, $0.0093 (79,273 input and 20,376 output tokens for the 71 calls not already cached by a trial run on toxicology, which cost $0.0002); SaaS, 16 calls, $0.0014. Every one of the 927 columns got a description and no call failed. One flex request was rate-limited (HTTP 429) and the client's retry waited 300 s, which made the Mini-Dev build take about nine minutes of wall time.

### Rendering

`render_schema(catalog, *, subset=None, samples=True, descriptions=True, matched_values=None)` follows XiYan-SQL's M-Schema layout, which ADR-008 recommends for the generator prompt:

```
【DB_ID】 california_schools
【Schema】
# Table: frpm
[
(CDSCode:TEXT, Primary Key, Foreign Key, California school identifier, stored as text; references the school record’s CDSCode., Examples: ['01100170109835', '01100170112607', '01100170118489']),
(`Academic Year`:TEXT, Academic year covered by the FRPM data, formatted as a year range such as 2014-2015., Examples: ['2014-2015']),
...
]
【Foreign keys】
frpm.CDSCode=schools.CDSCode
satscores.cds=schools.CDSCode
```

Each column line has the type, `Primary Key` / `Foreign Key` markers, the description, `Notes:` with the value notes, and examples. The example rules are M-Schema's (from its `m_schema.py`): at most three; one when any is longer than 20 characters or the column is a date/time type; none when any is longer than 50. Examples are SQL literals, so the storage type is visible and quotes are escaped. Identifiers go through `quote_identifier`, which now delegates to the grammar's `text2sql.grammar.conventions.sql_identifier`. An earlier `quote_identifier` used its own rule, which left SQLite keywords bare, so financial's `order` table would have appeared in prompts as `order` while the grammar only accepts `` `order` ``. With one function, the prompt spells every identifier exactly as the grammar emits it.

Output is a pure function of the catalog and arguments, so the full-schema block for a database is byte-identical across questions and can sit in the cached prompt prefix. A `subset` (for example from `DatabaseSchema.subset`, which keeps primary and foreign key columns of kept tables) renders only its tables and columns and only the foreign keys among them; a subset that names columns the catalog lacks is an error. Matched values from value retrieval are question-specific, so they go after the foreign keys in a `【Matched values】` block, and `render_matched_values` returns that block alone for prompts that place it in the user message, as ADR-008 suggests. Matched values are rendered exactly, without truncation or whitespace changes, since the model should copy them into the query.

Sizes as stored on 2026-10-16 (with LLM descriptions), estimated at four characters per token:

| db_id | tables | columns | rows | sampled tables | profile s | human desc. | ~tokens full | no samples | no samples, no desc. |
|---|---|---|---|---|---|---|---|---|---|
| california_schools | 3 | 89 | 29,941 | 0 | 0.35 | 45/89 | 4,733 | 3,895 | 534 |
| card_games | 6 | 115 | 803,445 | 2 | 1.99 | 92/115 | 4,283 | 3,352 | 651 |
| codebase_community | 8 | 71 | 740,646 | 2 | 1.87 | 71/71 | 1,766 | 1,264 | 564 |
| debit_card_specializing | 5 | 21 | 423,050 | 1 | 0.19 | 3/21 | 678 | 516 | 186 |
| european_football_2 | 7 | 199 | 222,796 | 1 | 1.51 | 98/199 | 6,823 | 5,477 | 1,624 |
| financial | 8 | 55 | 1,079,680 | 1 | 0.36 | 51/55 | 1,628 | 1,213 | 400 |
| formula_1 | 13 | 94 | 493,257 | 1 | 0.45 | 66/94 | 3,197 | 2,510 | 810 |
| student_club | 8 | 48 | 42,511 | 0 | 0.10 | 45/48 | 1,973 | 1,378 | 398 |
| superhero | 10 | 31 | 10,614 | 0 | 0.01 | 31/31 | 1,500 | 1,274 | 369 |
| thrombosis_prediction | 3 | 64 | 15,252 | 0 | 0.10 | 55/64 | 1,840 | 1,399 | 298 |
| toxicology | 4 | 11 | 36,922 | 0 | 0.06 | 11/11 | 490 | 382 | 152 |
| saas_crm (visible schema) | 16 | 129 | 36,932 | 0 | 0.01 | 129/129 | 3,928 | 3,755 | 1,284 |

The largest full-schema block is under 7,000 tokens, so the full-schema strategy can send every database whole. Descriptions are most of the size; examples add roughly a quarter.

### The SaaS database

`build_catalog(..., policy=ScopePolicy)` applies `ScopePolicy.visible_schema` before reading anything, so `tenant_id` on tenant tables, `users.password_hash` and `tenants.api_key` are not in the catalog at all and cannot reach a prompt or a grammar built from it. Tenant- and owner-scoped tables (12 of 16) get no samples and no distinct counts or null rates: the catalog is shared by all tenants, and samples from those tables would show one tenant's customers to another. Only the four global reference tables (currencies, countries, industries, plans) have examples. Descriptions come from the SaaS data dictionary through `text2sql.data.saas.load_saas_schema`. The LLM payload for a withheld table carries no values and no row count.

### Commands

`uv run --frozen python -m text2sql.catalog build --dataset bird|saas [--no-llm] [--db <db_id>]` builds, describes and saves, then prints per-database size, time, warning and cost columns. `load_catalog(db_id)` reads a saved catalog and names the build command if the file is missing.

## Consequences

- One catalog file feeds the grammar (`catalog.schema()`), the prompts (`render_schema`) and the retrievers (samples, statistics, descriptions). Changing the prompt rendering does not require a rebuild; changing profiling or ingestion does.
- Statistics for the eight sampled tables are approximate. Nothing downstream should treat `distinct_count` as exact when `profiled_rows < row_count`.
- LLM descriptions can be wrong. Human descriptions take precedence wherever they exist, and the LLM line is shown only where BIRD has nothing beyond the column name. Whether those lines help EX can be measured by evaluating with catalogs built with and without `--no-llm`; that is an experiment for the iteration rounds, not an assumption.
- The catalog records no fingerprint of the source database, so a changed database needs a manual rebuild. The files are small (473 KB for all twelve) and not gitignored; committing them keeps offline evaluation independent of the BIRD download. Rebuilding with LLM descriptions replays from the committed response cache, while `--no-llm` writes catalogs without them.
- Database values reach prompts only as quoted SQL literals, at most three per column and at most 80 characters each (in practice 50, by the M-Schema rule, except for date columns), and never from tenant tables. That limits, but does not remove, prompt injection planted in values; the grammar and the later safety layers still assume the model may be manipulated.
- `quote_identifier` in the catalog now calls into the grammar package (imported at call time, because the grammar imports the catalog). That keeps one spelling rule for prompts, grammar and gold-SQL normalization; it also means a change to the grammar's quoting changes rendered prompts, which is the intent.

## Sources

- docs/adr/008-pipeline-design.md, Stage 1, for the M-Schema evaluation numbers and the recommendation to put matched values in the user message.
- XGenerationLab/M-Schema, README and `m_schema.py`: https://github.com/XGenerationLab/M-Schema and https://raw.githubusercontent.com/XGenerationLab/M-Schema/main/m_schema.py (accessed 2026-10-16).
- SQLite database file format, section on cell payload overflow pages: https://www.sqlite.org/fileformat2.html (accessed 2026-10-16).
- SQLite URI filenames, `mode=ro`: https://www.sqlite.org/uri.html (accessed 2026-10-16).
- Spend and token figures: `runs/spend_ledger.jsonl`, phase `catalog`, runs `20261016T111705-d21556`, `20261016T111722-c971f8` and `20261016T112651-7b9be6`.
