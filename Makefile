# Every target runs through uv against the pinned lockfile.
UV := uv run --frozen

# `make eval` settings; override on the command line, e.g. `make eval DATASET=saas`.
DATASET ?= bird_minidev
SPLIT ?= dev
PRESET ?= best
# The committed smoke run CI replays (bird_minidev dev, baseline preset, seeded --limit sample).
SMOKE_REPORT ?= reports/smoke/20261016-212245-70b12ce

.PHONY: setup data catalog index grammar-coverage grammar-coverage-fixture eval eval-offline \
	smoke-offline cache-export cache-import safety demo lint format typecheck test coverage \
	audit check

setup:  ## install the pinned environment and git hooks
	uv sync --frozen
	$(UV) pre-commit install

data:  ## download BIRD Mini-Dev (checksummed) and generate the SaaS database
	$(UV) python -m text2sql.data.download bird
	$(UV) python -m text2sql.data.saas.generate --out data/saas/crm.sqlite

catalog:  ## build schema catalogs; LLM column descriptions replay from the response cache
	$(UV) python -m text2sql.catalog build --dataset bird
	$(UV) python -m text2sql.catalog build --dataset saas

index:  ## value and few-shot indexes under data/indexes/; embeddings replay from the response cache
	$(UV) text2sql index build --dataset bird
	$(UV) text2sql index build --dataset saas

grammar-coverage:  ## gold-SQL coverage of the full-schema grammar on the BIRD dev split
	$(UV) python -m text2sql.grammar.coverage --dataset bird --split dev

grammar-coverage-fixture:  ## gold-SQL coverage on the committed dev fixture (no BIRD download)
	$(UV) pytest tests/grammar/test_size_and_coverage.py -m "not live and not bird"

eval:  ## evaluate PRESET on DATASET/SPLIT (default: best on the BIRD Mini-Dev dev split)
	$(UV) text2sql eval --dataset $(DATASET) --split $(SPLIT) --preset $(PRESET)

eval-offline:  ## replay every committed report from the response cache and check it matches
	OFFLINE=true $(UV) text2sql reproduce

smoke-offline:  ## replay only the committed smoke run from the cache (what CI runs)
	OFFLINE=true $(UV) text2sql reproduce $(SMOKE_REPORT)

cache-export:  ## write cached responses not yet in git to a new cache/llm/shards/ file; commit it
	$(UV) text2sql cache export

cache-import:  ## load the committed cache shards into the local store (clients also do this)
	$(UV) text2sql cache import

safety:  ## adversarial suite against the four safety layers; no API calls
	$(UV) text2sql safety

demo:  ## local web demo of the live pipeline trace (http://127.0.0.1:8000)
	$(UV) text2sql demo

lint:
	$(UV) ruff check src tests scripts
	$(UV) ruff format --check src tests scripts

format:
	$(UV) ruff check --fix src tests scripts
	$(UV) ruff format src tests scripts

typecheck:
	$(UV) mypy

test:  ## unit, property and safety tests; no network
	$(UV) pytest -m "not live"

coverage:  ## tests with branch coverage, gated per package (safety, grammar, execution, validator)
	$(UV) coverage erase
	$(UV) pytest -m "not live" --cov=text2sql --cov-branch --cov-report=term-missing:skip-covered
	$(UV) coverage report --include='src/text2sql/safety/*' --fail-under=85
	$(UV) coverage report --include='src/text2sql/grammar/*' --fail-under=85
	$(UV) coverage report --include='src/text2sql/execution/*' --fail-under=85
	$(UV) coverage report --include='src/text2sql/safety/validator.py' --fail-under=100

audit:  ## pip-audit every locked package (runtime and dev) by exact version and hash
	uv export --frozen --all-groups --no-emit-project --format requirements-txt --quiet \
		| $(UV) pip-audit --strict --disable-pip --require-hashes --progress-spinner off -r /dev/stdin

check: lint typecheck test

.PHONY: demo-gif
demo-gif:  ## re-record docs/img/demo.gif offline from the response cache; needs vhs and ttyd
	OFFLINE=true vhs docs/demo.tape
