# GeoForge — Session Onboarding

**Read this first in every new session.** It is the current state of the project, written from
what has actually been built and measured — not from plans. Last updated: **2026-08-01**, end of
Phase 0.

---

## 1. What GeoForge is

An offline Python pipeline that generates an unlimited supply of **valid, well-posed geometry
puzzles** — find an unknown angle, length, ratio, or shaded area — each with a machine-verified,
human-readable step-by-step solution, served by a static React/TS web app from a pre-built JSON
puzzle bank.

**Why build it when frontier LLMs solve olympiad geometry?** We are not competing on solving.
An LLM asked for 10,000 puzzles produces an unknowable fraction of subtly broken ones, and
detecting them requires exactly this machinery. Our defensible claims: validity *by construction*
(the puzzle is emitted from the derivation that is its solution), difficulty grading that is
measurable and reproducible, zero marginal cost per user, and a compounding validated content
bank. The chess-app precedent: Stockfish surpassed humans decades ago; chess puzzle apps thrive.

## 2. Architecture in brief

```
sampler → Solver Abstraction Layer → puzzle former → gates → bank → static frontend
          (imported engines)          (ours)         (ours)  (ours)   (ours)
```
We **do not write deduction rules**. The reasoning core is imported from the AlphaGeometry
lineage; everything downstream of the SAL is ours. Full specs in `docs/` — read the doc that
governs the subsystem you touch (map in §8).

Key design decisions you must not silently reverse (all in `docs/07`):
- LLMs never touch the correctness path (they may propose auxiliary constructions, which the
  engine then verifies, and may rephrase prose).
- Numerics **verify**, never **derive**.
- Bank validation uses a *different engine* than generation.
- The figure is part of the puzzle statement (configuration facts are first-class).
- Quantity types are pluggable via a registry (`docs/04 §QTR`); angles ship first.

## 3. Current status — Phase 0 complete, gate PASSED

Phase 0 was a decision gate: can imported engines actually carry this product? **Yes.** Full
evidence in `spikes/p0/REPORT.md`; headline numbers:

| Question | Measured result |
|---|---|
| Readability gate (**the** risk) | **86%** of proof steps translate; **82%** of puzzles fully translate at AR budget 5 (target ≥ 80%) |
| Goal extraction without `acompute` | Works — 6/6 behaviourally correct (4 verified, 2 *correctly* rejected as underdetermined) |
| Engine choice | **Yuclid (C++) is primary** — 23–26× faster, solved 11/23 vs 8/23 pure-Python |
| Generation loop | 6/6 constructions saturated; two runs at one seed are byte-identical |
| Performance | 95% of wall time is inside the engine ⇒ **no Rust/Go/C++ work justified** |

**Phase 1 progress — M0–M4 done, M5–M6 remaining.** The pipeline runs Stages 1–7 end to end:
sample → realize → degeneracy → extract goal → traceback → minimize → prune → translate.
Measured over 300 sampled constructions at seed 42, reproducible across processes: 43 puzzles
formed, **39 pass the readability gate (91%)**, 257 machine proof steps compress to 186 sentences.

| Milestone | State | What landed |
|---|---|---|
| M0 | done | git + `pyproject.toml` (hard pins) + `Makefile` + `src/geoforge/config/` |
| M1 | done | SAL: `types`, `interface`, `newclid_backend`, `_patches`; contract suite |
| M2 | done | `construction`, `sampler` (circle-biased), `degeneracy` (Stage 3) |
| M3 | done | `quantities` (§QTR registry, angle), `extract` (Stage 5), `traceback` (Stage 6) |
| M4 | done | `translation/` — templates, idiom collapsing, vertex angles, readability gate |
| M5 | next | well-posedness, provisional banding, batch runner, the four P1 criteria |
| M6 | | AG2 cross-engine validation (angle-convention calibration is mandatory) |

**What does not exist yet:** `web/`, `banks/`, `src/geoforge/{scoring,bank}/`, `schema.py`.

## 4. What's next — M5, gates and the acceptance criteria

Stage 8 well-posedness (resample, discard configuration-flipped samples, require goal invariance —
**and step vertex-angle invariance**, `docs/04` Stage 8 item 2b), provisional depth banding, and the
seed-sharded batch runner with its per-stage attrition report. Then the four `docs/09` P1 criteria,
each with evidence.

**Phase 1 acceptance criteria (all still open, verified in M5):** fixed seed ⇒ byte-identical batch;
100 validated puzzles across ≥ 2 difficulty bands; every shipped solution passes the readability
gate; zero soundness failures in a 1,000-construction run.

Carry these Phase 0 outputs forward rather than redoing them: the idiom-collapsing insight and the
spike problem corpus. (The S1b extraction mechanism is already promoted, in `generator/extract.py`.)

## 5. How to run things (all verified working)

```bash
# Environment: uv + project-local .venv (Python 3.12.13). NEVER install into system Python.
uv run python -c "import newclid; print('ok')"

cd spikes/p0
uv run python s1_solve.py --compare-yuclid                     # solve rates + timing split
uv run python s1b_aconst_probe.py                              # goal-extraction mechanism
uv run python s2_traces.py --backend yuclid --max-ar-chain 5   # the readability gate
uv run python s3_generate.py --seed 42 --n 6 --backend yuclid --out out/a.json
```
Work through the SAL, not the engine — only `src/geoforge/solvers/` may import engine code:
```python
from geoforge.solvers import get_backend, ProblemSpec
from geoforge.solvers.types import PremiseSpec, SolveOptions

backend, opts = get_backend(), SolveOptions(seed=42)
figure = backend.realize(ProblemSpec(construction=jgex), opts)   # coordinates, no deduction
result = backend.solve(ProblemSpec(construction=jgex, goals=(...,)), opts)
# Fixed coordinates, explicit premises — goal verification and premise minimization:
result = backend.solve_facts(PremiseSpec(points=figure.points, premises=..., goals=...), opts)
```
Stages 1–7 for one construction:
```python
from geoforge.generator.extract import extract_goals
from geoforge.generator.traceback import derive, prune_figure
from geoforge.generator.translation import translate

for goal in extract_goals(backend, figure, opts).goals:
    d = derive(backend, figure.points, goal.result.proof_dag, goal.fact, opts)
    solution = translate(d.subdag, figure.coords())      # .ok is the readability gate
    if not solution.ok:
        continue                                        # attrition; .failures says why
    pruning = prune_figure(construction, d.needed_points() | solution.highlighted_points())
```
The underlying engine API, for reference (`JGEXProblemBuilder` → `GeometricSolverBuilder` →
`.run()` → `.proof()`) lives in `newclid_backend.py` and nowhere else.

## 6. Gotchas that cost real time — do not rediscover these

1. **`solver.proof()`**, not `write_proof_steps()` — the upstream README is stale.
2. **Yuclid rejects `acompute`/`lcompute`/`rcompute`.** Don't use them. Measure the value
   yourself and verify an explicit `aconst`/`lconst`/`rconst` (`docs/03 §3.3a`).
3. **The pure-Python backend has real upstream bugs** (BUG-1 patched in `newclid_patches.py`;
   BUG-2, the rule matcher choking on numeric constants like `1/2`, is unpatched). Use Yuclid.
   Upstream CI only exercises Yuclid, so the Python path is under-tested — expect more.
4. **`newclid==3.0.1`'s wheel omits `pyyaml`** — install it explicitly or `import newclid` fails.
4b. **"Goal is unprovable" arrives as a crash upstream** (BUG-3, patched). `ProofState.justify`
   raises `ValueError` but its caller catches `JustificationError`, so the intended
   report-it-as-unproven path is dead code. Affects Yuclid too, not just the Python path.
4c. **Never pass the engine's own tautologies back as assumptions.** Yuclid aborts the process
   (`std::logic_error: Trying to re-prove a statement`). Proof leaves come in three kinds —
   premises, configuration facts, trivia — and only the first two are premises.
4d. **A determinism test that runs twice in one process proves nothing** about reproducibility.
   Python randomizes string hashing per process, so anything leaking `set`/`dict` order over
   strings varies between runs while agreeing within a run. That blind spot hid BUG-4 (`cong`
   canonicalization did `segs.sort()` then `list(set(segs))`, discarding its own sort) through
   two milestones. Compare across **subprocesses with different `PYTHONHASHSEED`** —
   `tests/solvers/test_contract.py::TestCrossProcessDeterminism`. Never "fix" a flaky
   reproducibility check by pinning `PYTHONHASHSEED`; that hides the bug rather than finding it.
5. **Angles are directed line-to-line, mod π** (`∠(AB,CD)`), *never* human vertex angles.
   All 48/48 angle facts in the Phase 0 corpus were directed. Conversion needs configuration facts.
6. **AG2 DDAR's angle orientation is inverted vs Newclid.** Calibrate before cross-validating.
7. **Saturate by building goal-free** (`goals = ()`); `JGEXProblemBuilder.build()` retries until
   stated goals hold numerically, so a placeholder goal makes it spin and fail.
8. **Do NOT use `get_quotient` as the nice-value filter** (corrected in M3; it was listed here as
   one). Its tolerance is *relative*, so the window widens with the denominator and it snaps almost
   anything — it returned 17/19 for a generic angle. Snap to whole degrees with an absolute
   tolerance instead (`config.EXTRACTION`).
9. **No area predicate exists in any engine.** Areas need our own verified layer (`docs/03 §3.7`).
10. **Translation is compression, not 1:1.** Collapse engine idioms (the self-similar-triangle
    triple = "isosceles ⇒ base angles equal") into single human steps.

## 7. Dependency and licence policy (`docs/07` P1a/P2)

| Tier | What | Rule |
|---|---|---|
| Depend, hard-pinned | `newclid==3.0.1`, `py-yuclid==3.0.0` | Pin exactly; a pin gives full isolation from upstream churn |
| Vendor | `vendor/ag2_ddar/` | Unpackaged upstream; keep LICENSE + PROVENANCE; record any modification |
| We own | `newclid_patches` | Permanent — upstream's pure-Python path is under-tested |
| **Ideas only — never copy** | `tong-geometry/`, `FormalGeo/` (**GPL-3.0**) | Copying makes GeoForge GPL. Use MIT `FGPS/` instead for FormalGeo-style ideas |

Reference clones (`Newclid/`, `alphageometry*/`, `mathlib4/`, `penrose/`, `sympy/`, `FGPS/`,
`FormalGeo/`, `InterGPS/`, `2d_geometric_constraint_solver/`) are **read-only study material**,
gitignored, never modified in place, never dependencies.

## 8. Doc map

| Doc | Governs |
|---|---|
| `docs/01` | Vision, scope, why-worth-building, difficulty ladder, success criteria |
| `docs/02` | Architecture, JSON schema, repo layout, invariants |
| `docs/03` | **Solver integration**: SAL contract, backends, quantity extraction, translator |
| `docs/04` | Generation pipeline stages + quantity-type registry |
| `docs/05` | Difficulty scoring, filters, interestingness |
| `docs/06` | Frontend, diagram layout, anti-leak perturbation |
| `docs/07` | **Recorded decisions — do not reverse silently** |
| `docs/08` | Coding standards, testing policy, session workflow |
| `docs/09` | Roadmap and phase acceptance criteria |
| `research/` | Frozen research behind the 2026 pivot (reference, don't rewrite) |
| `spikes/p0/REPORT.md` | Phase 0 measured evidence |

**Standing rule:** update this file at the end of every phase (`docs/08` definition of done).
