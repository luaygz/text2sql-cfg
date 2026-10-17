# Contributing

This repository is a grammar-constrained text-to-SQL system evaluated on BIRD Mini-Dev and a synthetic multi-tenant SaaS database. `docs/adr/` records the design decisions and the evidence behind them. Read the ADRs of the modules you touch before changing them.

## Setup

You need git, make and [uv](https://docs.astral.sh/uv/) 0.10.6 (the version CI and the Docker image pin; uv also decides which CPython 3.12 build `.python-version` resolves to, and with it the bundled SQLite that eval results depend on). Docker is optional.

```sh
make setup                 # uv sync --frozen, then install the pre-commit hooks
cp .env.example .env       # add OPENAI_API_KEY only if you will make live calls
make data                  # BIRD download (~1.15 GB, every file sha256-checked) + seeded SaaS DB
make catalog               # schema catalogs; LLM column descriptions replay from the cache
make index                 # value and few-shot indexes; embeddings replay from the cache
```

Always run Python through `uv run --frozen ...` (the Makefile does). `--frozen` installs exactly what `uv.lock` pins; add dependencies with `uv add <pkg>` or `uv add --dev <pkg>`, never by editing `pyproject.toml` and the lockfile by hand.

Never commit `.env`. It is in `.gitignore`, the pre-commit hook `no-dotenv` refuses it, and `.dockerignore` keeps it out of images. Only `.env.example` belongs in git. The response cache stores response bodies only, never headers or the key.

## Make targets

| Target | What it does |
| --- | --- |
| `setup` | install the locked environment and git hooks |
| `data` | download BIRD (checksummed) and generate the SaaS database |
| `catalog` | build schema catalogs under `data/catalog/` |
| `index` | build value and few-shot indexes under `data/indexes/` |
| `grammar-coverage` | gold-SQL coverage of the full-schema grammar on the BIRD dev split (needs `make data`) |
| `grammar-coverage-fixture` | the same check on the committed fixture `tests/grammar/fixtures/bird_dev_gold.json`, no download |
| `eval` | evaluate `PRESET` on `DATASET`/`SPLIT`, e.g. `make eval PRESET=baseline DATASET=saas`; calls the API |
| `eval-offline` | replay every committed report from the response cache with `OFFLINE=true` and fail on any difference |
| `smoke-offline` | replay only the committed smoke run (`SMOKE_REPORT`); what CI runs |
| `safety` | adversarial suite against the four safety layers; no API calls |
| `demo` | local web demo on http://127.0.0.1:8000 |
| `lint` / `format` | `ruff check` and `ruff format --check`, or apply both |
| `typecheck` | `mypy --strict` |
| `test` | every test not marked `live` |
| `coverage` | the tests with branch coverage, gated at 85% on `safety/`, `grammar/`, `execution/` and 100% on the validator |
| `audit` | `pip-audit` of every package in `uv.lock`, by exact version and hash |
| `check` | `lint`, `typecheck` and `test`; run it before opening a pull request |

## Code standards

Python 3.12 with `from __future__ import annotations`, fully typed, clean under `mypy --strict` and `ruff` (lint rules and formatting are configured in `pyproject.toml`, line length 100). Use pydantic models at I/O boundaries (files, API payloads, CLI output), keep modules small, and leave no dead code or placeholder stubs. Comments explain why, not what.

Tests live under `tests/<area>/`. Tests that call OpenAI are marked `@pytest.mark.live` and skip unless `T2SQL_LIVE_TESTS=1`; tests that need `data/bird` are marked `@pytest.mark.bird` and skip when it is absent. Everything else runs without network. A test should fail when behavior a caller can see breaks: results, boundaries, error types and messages. A test that restates the implementation, or only checks that a mock was called, does not count. Use hypothesis for properties that hold over many inputs (the validator and the tenant rewriter already do).

## Prompts

Every prompt lives in `prompts/<name>.yaml` and is loaded with `text2sql.prompts.load_prompt(name)`; no prompt text is written inline in Python. A file has `name`, `version`, `description`, `changelog` and `sections`, and placeholders use `string.Template` syntax (`$question`, `${schema}`).

Any change to a prompt's text bumps `version` and appends a changelog entry with that version, the date and a one-line reason. The loader refuses a file whose last changelog entry does not match `version`. Calls record `template.tag` (`name@version`) so every run can be traced to the prompt text that produced it. Because the response cache keys on the rendered text, an edited prompt never replays an old answer, which also means `make eval-offline` will report cache misses for committed runs that used the old text until they are re-recorded.

## ADRs

Add one when you make a decision a reviewer would otherwise have to reverse-engineer. Take the next free number, `docs/adr/NNN-short-title.md`, and follow the existing ones: a title line `# ADR-NNN: ...`, then `Status:` and `Date:`, then Context, Decision, Consequences and Sources sections. Sources are live URLs you actually read, with the access date; if something could not be verified, say so rather than guess. To change a past decision, write a new ADR and set the old one's status to `superseded by ADR-NNN`; do not rewrite history.

## Response cache and spend ledger

Every model response, embedding and grammar-acceptance result is cached by content. The key is the SHA-256 of everything that shapes a model's output (model, input items, tools including the grammar, tool choice, reasoning settings, output cap) plus a sample index; transport settings such as the service tier are left out, so switching tiers keeps hits. With `OFFLINE=true` (or `--offline`), every call is served from the cache and a miss raises `CacheMiss` instead of calling the API. That is how `make eval-offline` reproduces every committed number with no key, and how CI replays the smoke run.

The cache lives in two forms. Your working copy is `cache/llm/responses.sqlite`, which git ignores. Git holds `cache/llm/shards/*.jsonl.gz`: immutable, append-only gzip files that are never rewritten, so history grows only by new rows and no file approaches GitHub's 100 MB limit. The client loads any shard your SQLite file has not seen yet whenever it starts, so after a clone or a pull there is nothing to run (`make cache-import` does the same by hand). When you record new runs, run `make cache-export`, which writes the rows no shard holds yet into a new shard file (split at 45 MB; a second run writes nothing), and commit it together with the `reports/` directories the runs produced and the regenerated `RESULTS.md` (`text2sql report`). A replay fails when `RESULTS.md` is out of date with `reports/`, and a clone fails with `CacheMiss` if you forgot the export.

`runs/spend_ledger.jsonl` is also committed. Every billed call appends one line with its token counts, cost, model, `run_id` and phase (set `T2SQL_PHASE`, e.g. `T2SQL_PHASE=eval-dev`). Cache hits are free and are not written. Before each call the client checks two caps: `MAX_SPEND_USD` for the current run and `TOTAL_SPEND_CAP_USD` for the ledger total plus this run; a call that could cross either is refused with `BudgetExceeded`. `uv run --frozen text2sql spend` summarizes the ledger by phase. Spend is real money, so keep smoke runs to a few questions and set a low `MAX_SPEND_USD` while developing.

## CI

Each check is its own workflow under `.github/workflows/`, so each has its own status badge. They run on pushes and pull requests to `main`, with `OFFLINE=true` and no API key or other secret.

| Workflow | Runs |
| --- | --- |
| `lint.yml` | `uv lock --check`, `make lint` |
| `typecheck.yml` | `make typecheck` |
| `tests.yml` | SaaS generator, then `make coverage` |
| `grammar-coverage.yml` | `make grammar-coverage-fixture` |
| `safety.yml` | `make safety` |
| `smoke-eval.yml` | `make data` (BIRD restored from the Actions cache, keyed on the pinned checksums), `make catalog`, the `bird`-marked tests, `make smoke-offline` |
| `docker.yml` | image build, non-root check, `--help`, the safety suite inside the image |
| `audit.yml` | `make audit` |

Every workflow calls the same make targets you run locally, so a red check reproduces with the same command. Actions are pinned to commit SHAs, with the release tag in a comment.

## Docker

The image holds the code, the prompts, the pricing table and the committed response cache; data, run logs and reports come from mounts. Build it with the commit so eval reports can record the code version (the image has no git):

```sh
docker build -t text2sql-cfg \
    --build-arg GIT_SHA="$(git rev-parse HEAD)$(git diff --quiet HEAD || echo -dirty)" .
docker run --rm text2sql-cfg safety
```

The container runs as uid 10001. Bind mounts are written with host permissions, so run as your own user when mounting the checkout's directories; mount `cache/`, `runs/` and `reports/` when a run should leave its cache entries, ledger lines and reports in the checkout:

```sh
docker run --rm --user "$(id -u):$(id -g)" --env-file .env \
    -v "$PWD/data:/app/data" -v "$PWD/cache:/app/cache" \
    -v "$PWD/runs:/app/runs" -v "$PWD/reports:/app/reports" \
    text2sql-cfg eval --dataset bird_minidev --split dev --preset baseline --limit 10
```

The demo server binds 127.0.0.1, inside the container too, so `-p` alone exposes nothing. To open it from the host, bind all interfaces inside the container and publish the port on the host's loopback only:

```sh
docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD/data:/app/data" --env-file .env \
    text2sql-cfg demo --host 0.0.0.0
```

Publishing on `0.0.0.0` instead would let anyone on your network run queries billed to your API key; do that only behind something that authenticates.
