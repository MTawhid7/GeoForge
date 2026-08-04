# GeoForge

**Read `ONBOARDING.md` first** — current status, verified commands, and the gotchas that
otherwise cost hours. Then read the doc governing your subsystem.

Geometry puzzle generator built on imported AlphaGeometry-lineage engines: offline Python
pipeline (sampler → Solver Abstraction Layer [Newclid/Yuclid primary, AG2 DDAR validator] →
puzzle former → gates → bank) produces validated puzzle JSON; static React/TS frontend renders it.
Authoritative specs live in docs/ — read the doc for the subsystem you're touching:
overview 01, architecture 02, solver integration 03, generation 04, scoring 05, frontend 06,
recorded trade-offs 07 (do not reverse silently), guidelines 08, roadmap 09.
research/ is the frozen research record behind the 2026 pivot — reference, don't rewrite.

## Commands

- Environment: `uv` + project-local `.venv` (Python 3.12). Run everything via `uv run`.
  **Never install into system Python.** Spikes: see `ONBOARDING.md` §5.
- `make setup` — install Python deps (incl. pinned newclid) + web deps
- `pytest -q` — all Python tests; `pytest tests/solvers -q` for SAL contract suite only
- `make typecheck` — mypy --strict (src/geoforge) + tsc
- `make lint` — ruff + eslint
- `make bench-batch` — fixed-seed pipeline run + attrition report diff (per stage and band)
- `make bank` — full bank build + cross-engine validation (fails build on any invalid puzzle)
- `cd web && npm run dev` — frontend dev server

## Hard rules

- Correctness path (src/geoforge/solvers/, generator/, bank/validate.py): no change without
  tests in the same commit; numeric layer VERIFIES, never DERIVES facts.
- Engines are read-only dependencies: never modify reference clones in place; only
  src/geoforge/solvers/ imports engine code; bank validation must use a different engine
  backend than generation.
- License policy: never import or copy code from tong-geometry/ or other GPL sources
  (ideas only — docs/07 P2). Apache/MIT/BSD deps are fine.
- All randomness takes an explicit seed (including engine seed plumbing); pipeline output
  reproducible from (generator_version, engine_version, seed).
- All thresholds/weights live in src/geoforge/config/ — no inline magic numbers.
- Step `rule` values are public API (template id, or the namespaced engine rule id when a rule has
  no template); renaming one — or adding a template to a rule that shipped without one — is a
  schema change.
- LLM output may populate ONLY `solution[].text` and `given[].display` (docs/02 invariant 5 is the
  exhaustive list). Never send the renderer a goal, an answer, or a figure. Never make a live API
  call in a path a bank build depends on — prose is a content-keyed cache committed with the bank,
  and that is what keeps builds reproducible. No test may make a live API call.
- Never hand-edit generated artifacts (web/src/types/generated/, banks/) or reference clones.
- Frontend contains no geometry logic; it renders JSON as-is.
- Measure before you write it down: any claim about the corpus goes in a doc with the number and the
  seed behind it. Difficulty is gated (shortcut resistance, answer entropy) before it is scored.
- If code must deviate from docs/, edit the doc in the same commit (trade-off reversals go in
  docs/07-limitations-tradeoffs.md).

## Style

- Python 3.12, ruff, mypy --strict, frozen dataclasses for facts/steps/DAG/SAL types.
- TS strict; no state library; no hardcoded UI strings (string table only).
- Conventional commits, one logical change each.
