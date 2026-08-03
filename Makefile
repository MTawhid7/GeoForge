.PHONY: setup lint typecheck test schema bench-batch cross-validate bank bank-strict clean

# Everything runs inside the project-local .venv via uv. Never install into system Python.

setup:
	uv sync

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy
	uv run python -m geoforge.schema_emit --check

# Regenerate the TypeScript types and JSON Schema from src/geoforge/schema.py.
schema:
	uv run python -m geoforge.schema_emit --emit

test:
	uv run pytest

# Fixed-seed pipeline run + attrition report diff (per stage and band). Wired in M5.
bench-batch:
	uv run python -m geoforge.generator.batch --seed 42 --n 200 --report

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
