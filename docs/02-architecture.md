# 02 — Architecture

## System overview

Offline Python pipeline → validated JSON puzzle bank → static TypeScript/React frontend. The reasoning
core is **imported** (AlphaGeometry-lineage engines) behind a thin adapter; everything downstream of the
adapter is ours.

```
┌──────────────────────────── OFFLINE (Python) ────────────────────────────────┐
│                                                                              │
│ sampler ─▶ SOLVER ABSTRACTION LAYER ─▶ puzzle former ─▶ gates ─▶ bank        │
│  (ours)    ┌──────────────────────┐     (ours)          (ours)   (ours)      │
│            │ newclid/yuclid  ◀────┼── primary engine: closure + proof DAG    │
│            │ ag2 ddar        ◀────┼── independent validator (bank build)     │
│            │ (future backends)    │                                          │
│            └──────────────────────┘                                          │
│  puzzle former: goal selection · traceback · premise minimization ·          │
│                 trace→readable-steps translation                             │
│  gates: degeneracy · well-posedness · difficulty · interestingness · dedupe  │
│  bank: layout/anti-leak · shard packing · cross-engine validation            │
└──────────────────────────────────────────────────────────────────────────────┘
                       │ puzzle bank (JSON, versioned schema)
                       ▼
┌──────────────────────────── ONLINE (TS/React) ───────────────────────────────┐
│ web/: SVG diagram renderer · puzzle player · solution stepper · hints        │
│ static hosting; zero geometry logic                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### `src/geoforge/solvers/` — Solver Abstraction Layer (SAL)
The pivot's central artifact. Interface (spec in doc 03):
`solve(construction, opts) -> SolveResult{facts, proof_dag, numeric_model}`.
Backends: `newclid` (primary), `ag2ddar` (validator), stubs for future engines. All downstream code
depends only on this interface — engine churn becomes an upgrade, not a rewrite.

### `src/geoforge/generator/` — puzzle synthesis
Construction sampling (JGEX-compatible DSL), engine-backed closure, quantity-goal selection driven by the
**quantity-type registry** (doc 04 §QTR — angle/length/ratio/area as pluggable goal families), traceback,
premise minimization with **configuration facts** (doc 04 §stage-6), well-posedness gate (including scale
pinning for dimensional quantities), readable-steps translation. Pipeline spec: doc 04.

### `src/geoforge/scoring/` — quality control
Difficulty score, hard filters, interestingness (including the TongGeometry elegance ratio), per doc 05.
Consumes the traced sub-DAG; never re-runs deduction.

### `src/geoforge/bank/` — bank building
Isomorphism dedupe · **independent validation** (re-derive every puzzle via the AG2 DDAR backend — a
genuinely uncorrelated codebase — plus numeric re-check; optional SymPy/Gröbner spot-check) · layout with
anti-leak perturbation (doc 06 §6.3) · versioned JSON shards + manifest.

### `web/` — frontend
Static React app rendering JSON as-is; zero geometry logic. Doc 06.

## Data flow contract: puzzle JSON

The schema is **quantity-generic**: `given` and `goal` are typed quantity statements drawn from the
quantity-type registry (doc 04 §QTR), never angle-specific structures. Schema sketch (code-level schema
in `src/geoforge/schema.py` + generated TS types are authoritative):

```jsonc
{
  "id": "gf-000123",
  "schema_version": 2,
  "quantity_type": "angle",              // primary goal type; one per puzzle
  "difficulty": { "score": 6.2, "band": "hard", "depth": 7, "distinct_rules": 5 },
  "figure": {
    "points": [{ "id": "A", "x": 120.5, "y": 44.2, "label_dx": -8, "label_dy": -6 }],
    "segments": [["A","B"]],
    "circles": [{ "center": "O", "through": "A" }],
    "regions": [],                       // for area puzzles: closed boundaries, shading flags
    "marks": { "equal_segments": [], "parallel": [], "right_angles": [],
               "length_labels": [] }     // for length puzzles: labeled given lengths
  },
  "given": [
    { "quantity": { "kind": "angle", "at": ["B","A","C"] },
      "value": { "exact": "40", "approx": 40.0 }, "display": "∠BAC = 40°" }
    // other kinds: {"kind":"length","of":["A","B"]} · {"kind":"ratio","of":[["A","B"],["C","D"]]}
    //              {"kind":"area","of":"region:R1"}
  ],
  "goal": {
    "quantity": { "kind": "angle", "at": ["B","D","C"] },
    "answer": { "exact": "20", "approx": 20.0, "display": "20°" },
    "input": { "mode": "integer", "unit": "deg" }   // per-type answer-input policy, see below
  },
  "solution": [
    { "step": 1, "rule": "isosceles_base_angles",
      "text": "AB = AC, so the base angles are equal: ∠ABC = ∠ACB.",
      "derives": "eqangle:b:a:b:c:c:a:c:b", "highlights": ["seg:A:B","seg:A:C","angle:A:B:C"] }
  ],
  "reference_figure": {                  // build-time only, stripped from shipped banks
    "points": [{ "id": "a", "x": 0.31, "y": 0.87 }]
  },
  "provenance": { "generator_version": "…", "engine": "newclid-3.0.1", "seed": 991, "construction": "…" }
}
```

**`reference_figure` vs `figure` (added M6).** Two different things, deliberately not merged.
`figure` is player-facing: laid-out display coordinates, produced by Phase 2's layout with anti-leak
perturbation (doc 06 §6.3), point ids in the uppercase display labels. `reference_figure` is the
**engine's** diagram — the exact float64 coordinates, in lowercase engine names, over which the goal
was derived — and exists so cross-engine validation can re-derive the puzzle from the emitted JSON
alone (doc 04 §V). It is build-time data, stripped from shipped banks alongside `provenance`.
Perturbing it would break validation; perturbing `figure` is the whole point of `figure`.
It carries the **pruned** point set: a validator given scaffolding the drawn figure no longer shows
could reach the goal through a point the player never sees.

**Exact values:** `exact` is a canonical symbolic string in a closed grammar (rationals and
quadratic-surd forms like `3*sqrt(2)`; grammar owned by `schema.py`, values produced by the exact layer
and SymPy-normalized). `approx` is float64 for input checking and rendering only — never for truth.

**Answer-input policy** (`goal.input`, set per quantity type in config): `angle` → integer degrees;
`ratio` → small fraction `p/q`; `length`/`area` → decimal, checked against `approx` with a per-puzzle
tolerance, exact form revealed after solving. Recorded trade-off: doc 07 T8.

**Highlight ID grammar (normative):** `point:<ID>` · `seg:<ID>:<ID>` · `angle:<P>:<VERTEX>:<P>` ·
`circle:<CENTER>:<THROUGH>` · `arc:<CENTER>:<P>:<P>` · `region:<ID>`. Nothing else may appear in
`highlights`. Point ids are the player-facing uppercase labels (engine `a1` → `A1`).

**`derives`** carries the canonical engine-neutral **fact id** (`solvers/types.py`: `kind:args[=value]`,
lowercase engine point names), not a second display-space id grammar. It is a trace handle — it links a
published step back to the exact node of the proof DAG, which is what makes a shipped puzzle auditable
against a re-derivation. Only `text`, `display` and `highlights` are player-facing. (Amended M4; the
pre-implementation sketch showed a display-style `angle_eq:ABC:ACB`, which would have meant inventing
and maintaining a second identifier scheme for no gain.)

**Localization decision:** `display`/`text` are pre-rendered strings; banks are built per locale from the
rule→template string table (v1 ships English only). The frontend never composes sentences. Translating
the app means rebuilding banks — recorded trade-off, doc 07 T4.

Schema rules: additive change ⇒ minor bump; breaking ⇒ major bump + frontend migration. `provenance` is
stripped from shipped banks, kept in the build archive.

## Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Engine | `newclid` 3.x (+ `yuclid` C++ core) — Apache-2.0 | AG-class solver, maintained, Python API, traced proofs; licenses verified in the vendored clones |
| Validator engine | AG2 DDAR — Apache-2.0 | Uncorrelated second derivation for every banked puzzle |
| Generation scaffold | `ncdgen` (Newclid monorepo, Apache-2.0, by Harmonic) | Synthetic JGEX problem generation on Newclid; adapt rather than rebuild |
| Pipeline | Python 3.12, NumPy, SymPy | SymPy: exact rationals + Gröbner spot-checks in validation |
| Formal tier (optional, later) | Lean 4 + mathlib + LeanGeo | Machine-checked certificates for featured puzzles |
| Frontend | TypeScript, React, Vite, SVG | Crisp scalable diagrams, per-element highlighting, static hosting |
| Types across boundary | JSON Schema → generated TS types | CI fails on drift |
| CI | GitHub Actions: lint, typecheck, tests, bank-validation gate | A bank that fails validation cannot deploy |

## Repository layout

```
GeoForge/
  CLAUDE.md  docs/  research/          # research/ = permanent research record
  src/geoforge/{solvers/, generator/, scoring/, bank/, schema.py, config/}
  tests/                               # mirrors package layout; fixtures/
  web/                                 # TS workspace (vite + react)
  banks/                               # built artifacts (never hand-edited)
  Newclid/ alphageometry/ alphageometry2/  mathlib4/ penrose/ sympy/ tong-geometry/
                                       # READ-ONLY reference clones — see policy below
```

**Reference-clone policy:** the cloned repos are for study and vendored use only. Never modify them in
place; never copy code from `tong-geometry/` (GPL-3.0 — ideas only, doc 07 P2); `penrose/` and
`mathlib4/` are reading material. `Newclid` and `alphageometry2` are Apache-2.0 and may be depended on
(via pip pin / vendored fork) and patched via upstream PRs. Add all clones to `.gitignore` when the repo
is initialized; pin exact versions in `pyproject.toml` / a vendor manifest instead.

## Key architectural invariants

1. **One-way dependency:** web depends only on the JSON schema; scoring/bank consume SAL outputs; nothing
   outside `solvers/` imports an engine directly.
2. **Determinism:** every artifact reproducible from `(generator_version, engine_version, seed)`. Engine
   seed plumbing is verified by a CI double-run diff.
3. **Independent validation:** bank validation re-derives every puzzle with a *different engine* than the
   one that generated it. Correlated blind spots are treated as the top failure mode (doc 04 §V).
   Enforced in code, not by configuration: `bank/validate.py` refuses a validator whose engine is the
   generating one, because that failure is silent — a bank "validated" by its own generator passes
   everything and proves nothing. Scope of the guarantee: codebase independence, not method
   independence (doc 07 T14).
4. **Numeric verifies, never derives:** all published facts come from symbolic derivations; numerics gate
   and check only.
5. **LLM boundary:** LLM output never enters `given`, `goal`, `answer_deg`, `derives`, `highlights`, or
   difficulty. (Allowed roles: doc 01 non-goals.)
