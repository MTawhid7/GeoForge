.PHONY: setup lint typecheck test bench-batch bank clean

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

test:
	uv run pytest

# Fixed-seed pipeline run + attrition report diff (per stage and band). Wired in M5.
bench-batch:
	uv run python -m geoforge.generator.batch --seed 42 --n 200 --report

# Full bank build + cross-engine validation; fails on any invalid puzzle. Wired in Phase 2.
bank:
	uv run python -m geoforge.bank.build

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find src tests -name __pycache__ -type d -exec rm -rf {} +
