# ADR-018: CI workflows and the Docker image

Status: accepted
Date: 2026-10-16

## Context

CI on GitHub Actions covers lint, type check, unit and property tests, grammar coverage on fixtures, the safety suite, a 30-question offline smoke eval from the committed cache and a Docker build, with one badge each. Security hygiene adds `pip-audit` in CI, `.env.example` only, and a demo server that binds to localhost. `uv sync && make test` must pass on a clean Linux machine and in CI.

Constraints that shaped the design:

- CI has no OpenAI key. Everything must run from local code and the committed response cache.
- GitHub's workflow status badge is per workflow file, filtered only by branch and event; there is no per-job badge.
- BIRD arrives as about 1.15 GB of zip archives from bird-bench.oss-cn-beijing.aliyuncs.com and Hugging Face and extracts to about 2.8 GB. The BIRD-gated tests and the smoke eval need it; nothing else does.
- Eval results are execution accuracy, which depends on SQLite's behavior. The development machine runs uv's managed CPython 3.12.12 with its bundled SQLite 3.50.4 (the version ADR-007 measured against). The official `python:3.12-slim-trixie` image, pulled on 2026-10-16, ships Python 3.12.15 with Debian's SQLite 3.46.1.
- `text2sql.config.REPO_ROOT` is derived from the location of the source file, and prompts, the pricing table and the response cache are found relative to it. Eval reports record the git SHA of the code, which `current_git_sha()` reads from git.

## Decision

One workflow per check, so that each gets its own badge: `lint.yml`, `typecheck.yml`, `tests.yml`, `grammar-coverage.yml`, `safety.yml`, `smoke-eval.yml`, `docker.yml` and `audit.yml` under `.github/workflows/`. We chose this over a single `.github/workflows/ci.yml` because a single file can only have one badge. Shields.io can draw per-check badges, but only for repositories it can read, which rules it out here. The shared setup (pinned uv, `uv sync --frozen`) is a composite action in `.github/actions/setup/action.yml`, so changing it is a one-file edit.

Every workflow runs on push and pull request to `main`, calls the same make targets a developer runs locally, and sets `permissions: contents: read`, `persist-credentials: false` on checkout, and a per-ref concurrency group that cancels superseded runs. No workflow references a secret. The ones that touch the pipeline set `OFFLINE=true`, so a cache miss raises instead of attempting an API call, and `T2SQL_PHASE=ci`. Third-party actions are pinned to the commit SHA of their latest release as of 2026-10-16, with the tag in a comment: actions/checkout v7.0.1, astral-sh/setup-uv v10.3.0, actions/cache v6.1.0, actions/upload-artifact v7.0.2, docker/setup-buildx-action v4.4.1, docker/build-push-action v7.4.0.

uv is pinned to 0.10.6 in setup-uv and in the Dockerfile. That is the version on the development machine, and it also decides which CPython 3.12 build `.python-version` resolves to, so local runs, CI and the image all use 3.12.12 with SQLite 3.50.4.

What each workflow runs:

- Lint: `uv lock --check` (the lockfile matches `pyproject.toml`), then `make lint` (`ruff check` and `ruff format --check` on src, tests, scripts).
- Type check: `make typecheck` (`mypy --strict` over the package).
- Tests: generates the seeded SaaS database, then `make coverage`: every test not marked `live`, with branch coverage, and separate `coverage report --fail-under` gates of 85% on `safety/`, `grammar/` and `execution/` and 100% on `safety/validator.py`. BIRD-gated tests skip here because the data is absent.
- Grammar coverage: `make grammar-coverage-fixture`, which runs the grammar size and coverage tests against `tests/grammar/fixtures/bird_dev_gold.json`. The fixture holds the table and column names of the 11 dev-split databases and the 699 dev gold queries (BIRD and Arcwise), so no download is needed; the test requires at least 95% coverage per gold source, agreement between lark and llguidance, and every grammar within the API size estimate. A `bird`-marked test fails if the fixture drifts from the data.
- Safety suite: `make safety` (`text2sql safety`), which generates the SaaS database in a temporary directory and fails unless no adversarial case reaches the database. Its report under `reports/safety/` is uploaded as an artifact even when the job fails.
- Smoke eval: `make data`, `make catalog`, then the `bird`-marked tests, then `make smoke-offline`, which runs `text2sql reproduce $(SMOKE_REPORT)` with `OFFLINE=true`: it replays the committed 30-question smoke report and fails on any per-question or summary difference, on a cache miss, or when RESULTS.md is out of date with `reports/`. A fresh `text2sql eval --limit 30 --offline` would also prove the cache covers those questions, but would compare its numbers to nothing. CI does not run `make eval-offline`, the replay of every committed report: the full replay grows with every ablation and sweep, so CI runs the 30-question smoke and the full replay stays a local check that every number in RESULTS.md reproduces from the committed cache without an API key. BIRD is restored with `actions/cache/restore` under a key derived from the pinned sha256 values and extraction layout in `text2sql.data.download`, not from a file hash, so editing unrelated code in that module keeps the cache. On a hit the downloader re-verifies the three small files and finds the extraction markers, so nothing is fetched; on a miss it downloads and verifies everything. The archives are deleted before saving because the extracted trees and their markers are all the downloader needs. The cache is saved by a separate `actions/cache/save` step right after the download, so a failure in a later step does not throw the download away, and only on push events, because a repository has 10 GB of cache and a pull-request-scoped duplicate of a gigabyte entry would only push out the copy on `main`, which pull requests can already read. Catalogs are rebuilt each run, their LLM column descriptions replayed from the cache. Value and few-shot indexes are not built: the smoke run uses the baseline preset, which reads neither, so a smoke report from a preset with retrieval would need `make index` added to the workflow.
- Docker build: builds the image with Buildx and the GitHub Actions layer cache, passing the commit as `GIT_SHA`, then checks that it runs as uid 10001, that `text2sql --help` starts, and runs `text2sql safety` inside the image, which needs neither data nor a key and exercises the image's interpreter, SQLite and all four safety layers.
- Dependency audit: `make audit` exports `uv.lock` (runtime and dev groups, every platform, with hashes, without the project itself) and runs `pip-audit --strict --disable-pip --require-hashes` on it. Auditing the lockfile rather than the installed environment covers packages that only install on other platforms and skips the local project, which is not on PyPI.

The Docker image is two stages on `debian:trixie-slim`, following uv's standalone example. The builder copies the uv 0.10.6 binary, installs the managed CPython from `.python-version` into `/python`, syncs the dependencies with `uv sync --frozen --no-dev --no-install-project` from bind-mounted lock files (a layer that changes only with the lockfile), then copies the project and syncs it. The runtime stage copies `/python` and `/app` without uv. The project stays an editable install so `REPO_ROOT` is `/app`. The process runs as an unprivileged `text2sql` user (uid 10001); code, prompts, pricing and the interpreter are root-owned, and the user can write only `data/`, `runs/`, `cache/`, `reports/` and `RESULTS.md`. `/app/data` and `/app/runs` are volumes; BIRD and the generated databases are never baked in. The entry point is `text2sql`, with `--help` as the default command. `.dockerignore` keeps `.env` and `.env.*` (except `.env.example`), `data/`, `runs/` except the committed spend ledger, the virtualenv, tool caches, `.git`, tests, docs and scripts out of the build context. The committed ledger stays in the image so the lifetime spend cap still holds when `runs/` is not mounted.

The image has no git, so the build takes a `GIT_SHA` argument and exposes it as `T2SQL_GIT_SHA`, which `current_git_sha()` uses only when no git checkout is available; an eval in an image built without it stops with `GitShaError` instead of writing a report with no provenance.

The demo server binds 127.0.0.1 by default, inside the container as well, so publishing a port does not by itself expose anything. To reach it from the host, one passes `--host 0.0.0.0` to bind inside the container's network namespace and publishes on the host loopback only, `-p 127.0.0.1:8000:8000`. The Dockerfile declares no `EXPOSE`, so `docker run -P` does not publish the demo on every host interface.

## Consequences

Each push starts eight workflow runs instead of one. They run in parallel, and a red check names the make target that reproduces it.

The smoke eval passes only once a smoke run has been recorded with a key and committed together with the response-cache shards (`make cache-export`, then `cache/llm/shards/`), its `reports/` directory and the regenerated RESULTS.md. `SMOKE_REPORT` in the Makefile names the committed 30-question run; without a committed run the workflow is red by design. Any change to a prompt, grammar or pipeline setting that alters a request for the smoke questions also turns it red, because the request is no longer in the cache; that is the intended signal to re-record the run.

The first smoke-eval run, and any run more than a week after the last cache access (GitHub evicts unused caches after seven days), downloads about 1.15 GB from servers in Beijing and on Hugging Face. How long that takes from GitHub's runners has not been measured.

The coverage gate is enforced on the whole non-live suite, so a module added without tests can turn the tests workflow red even when every test passes. That happened during development: `safety/` measured 83% and 81% while the guard modules were being written, below the 85% gate. In the last local run on 2026-10-16, after their tests landed, `safety/` measured 100% branch coverage, `grammar/` 96%, `execution/` 96% and the validator 100% of statements and branches.

Base images are pinned by tag (`debian:trixie-slim`, `ghcr.io/astral-sh/uv:0.10.6`), not by digest, so rebuilds pick up Debian security updates but two builds of the same commit can differ below the Python layer. Python, SQLite and every Python package are fixed by uv and the lockfile.

Running `text2sql eval` in the container needs mounts for `cache/`, `runs/` and `reports/` (and `--user` matching the host owner) for the results to land in the checkout; CONTRIBUTING.md has the command. Numbers that go into RESULTS.md are still expected to come from a git checkout.

None of these workflows had run on GitHub when this ADR was written. They were checked with actionlint 1.7.12 (with shellcheck 0.11.0), the Dockerfile with hadolint 2.15.1, and each workflow's make targets were run locally. Inside the built image the safety suite gave the same result as on the host (224 cases, none reaching the database), and the demo answered on a published loopback port only when started with `--host 0.0.0.0`.

## Sources

All accessed 2026-10-16.

- GitHub, "Adding a workflow status badge" (badge URL per workflow file, `branch` and `event` parameters): https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge
- uv, "Using uv in GitHub Actions" (setup-uv, pinning a uv version, `uv sync`): https://docs.astral.sh/uv/guides/integration/github/
- uv, "Using uv in Docker" (copying the uv binary, `--no-install-project` intermediate layer with bind-mounted lock files, cache mounts, `UV_LINK_MODE=copy`, `UV_COMPILE_BYTECODE`, non-editable vs editable installs): https://docs.astral.sh/uv/guides/integration/docker/
- astral-sh/uv-docker-example, `standalone.Dockerfile` (managed Python in `/python` with `UV_PYTHON_INSTALL_DIR` and `UV_PYTHON_PREFERENCE=only-managed`, copied into a `debian:trixie-slim` runtime stage with a non-root user): https://github.com/astral-sh/uv-docker-example/blob/main/standalone.Dockerfile
- astral-sh/setup-uv README (`version`, `enable-cache` inputs): https://github.com/astral-sh/setup-uv
- actions/cache v6.1.0 README (cache scopes, default-branch caches readable from other branches, 10 GB per repository, eviction after a week without access) and `save/README.md` ("Always save cache" with separate restore and save steps): https://github.com/actions/cache/blob/v6.1.0/README.md, https://github.com/actions/cache/blob/v6.1.0/save/README.md
- Release tags and commit SHAs of every pinned action, from the GitHub REST API (`repos/<owner>/<repo>/releases/latest`, `repos/<owner>/<repo>/git/ref/tags/<tag>`).
- `pip-audit --help` for pip-audit 2.10.1, the locked version (`--strict`, `--disable-pip`, `--require-hashes`, `-r`).
- Interpreter and SQLite versions: `python:3.12-slim-trixie` pulled 2026-10-16 (`PYTHON_VERSION=3.12.15`, `sqlite3.sqlite_version` 3.46.1); the built image and the local `.venv` both report 3.12.12 and SQLite 3.50.4.
