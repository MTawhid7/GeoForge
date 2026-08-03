.PHONY: setup lint typecheck test schema bench-batch calibrate cross-validate bank bank-strict \
        web-setup web-dev web-build web-test web-e2e web-fixtures clean

# Everything runs inside the project-local .venv via uv. Never install into system Python.

setup:
	uv sync
	cd web && npm install

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	cd web && npx eslint .

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy
	uv run python -m geoforge.schema_emit --check
	cd web && npx tsc -b

# Regenerate the TypeScript types and JSON Schema from src/geoforge/schema.py.
schema:
	uv run python -m geoforge.schema_emit --emit

test:
	uv run pytest
	cd web && npm run test

# Fixed-seed pipeline run + attrition report diff (per stage and band).
bench-batch:
	uv run python -m geoforge.generator.batch --seed 42 --n 200 --report

# docs/05 §5.1 calibration protocol: stratified spot check + batch distribution. A weight
# change has to cite one of these, which is why it is a command and not a paragraph.
calibrate:
	uv run python -m geoforge.scoring.report --n 400 --seed 42 --sample 50

# Generate, then re-derive every puzzle on the second engine (AG2 DDAR). Any disagreement
# exits non-zero: two engines differing means one is wrong and we cannot tell which. Wired in M6.
cross-validate:
	uv run python -m geoforge.generator.batch --seed 42 --n 400 --validate

# Bank build + cross-engine validation; fails the build on any invalid puzzle.
# NOT YET SHIPPABLE: scoring, dedupe, interestingness and anti-leak layout are still to land,
# and the manifest says so. `--strict` refuses to build until they do.
bank:
	uv run python -m geoforge.bank.build --seed 42

bank-strict:
	uv run python -m geoforge.bank.build --seed 42 --strict

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find src tests -name __pycache__ -type d -exec rm -rf {} +

# ---------------------------------------------------------------- frontend

web-setup:
	cd web && npm install && npx playwright install chromium

# Copies the bank built by `make bank` into web/public/ and starts the dev server.
web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

web-test:
	cd web && npm run test

# Real-browser happy path. Serves the committed fixture bank, not `banks/v2` — a happy path
# that changes meaning when the generator's corpus moves is not a test.
web-e2e:
	cd web && npm run e2e

# Re-cut the committed fixture bank from the current build. Run after a schema change.
web-fixtures:
	cd web && node scripts/make-fixture-bank.mjs
