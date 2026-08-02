# 04 — Generation Pipeline

The generator turns random constructions into validated candidate puzzles. Expect brutal attrition
(> 90% of samples discarded is normal); throughput comes from cheap early rejection. The readability gate
(doc 03 §3.5) adds a new attrition stage the old design didn't have.

## §QTR — Quantity-type registry

The pipeline is parameterized by a registry of **quantity types**; nothing outside the registry may
special-case "angle". Each registered type declares:

| Field | Meaning | `angle` (v1) | `length`/`ratio` (wave 2) | `area` (wave 3) |
|---|---|---|---|---|
| `goal_extractor` | Which derived facts qualify as goals | numeric-valued angle atoms | AR length/ratio atoms | custom area layer output (doc 03 §3.7) |
| `dimension` | Scale behavior | scale-free | length: **scale-pinned**; ratio: scale-free | scale-pinned (dimension 2) |
| `nice_values` | Given-value palette per band | integer degrees | integer / small-surd lengths, small ratios | — (derived) |
| `answer_policy` | Exactness class + input mode (doc 02) | integer, keypad | fraction / decimal+tolerance | decimal+tolerance |
| `templates` | Readable-step template family (doc 03 §3.5) | angle family | similarity/metric family | decomposition family |
| `marks` | Figure mark kinds it may state | arcs, ticks | length labels | shaded regions |

Enabling a type = registering these six things + its config block. The registry keeps schema, gates,
scoring, and frontend generic while rollout stays deliberate (doc 09).

## Pipeline stages

```
sample construction ─▶ assign numeric givens ─▶ numeric pre-checks ─▶ SAL closure (engine)
  ─▶ goal selection ─▶ traceback + premise minimization (incl. configuration facts)
  ─▶ readable-steps translation gate ─▶ well-posedness gate ─▶ emit CandidatePuzzle
  ─▶ (scoring/filters, doc 05) ─▶ (bank build + cross-engine validation, §V)
```

### Stage 1 — Sample construction
3–9 JGEX-compatible steps from a weighted grammar (weights in `config/`; start from `ncdgen`'s sampler
and re-weight). Difficulty targeting starts here: deeper constructions and circle steps correlate with
harder puzzles. Later upgrade (doc 09 P3): corpus-weighted grammar à la Seed-Geometry.

### Stage 2 — Assign numeric givens
Choose 1–3 free parameters; assign exact values from the target quantity type's `nice_values` palette
for the band (angles: multiples of 10 → arbitrary integers; lengths: small integers/surds; ratios: small
fractions). Remaining parameters stay free — they power the well-posedness check. **Scale pinning:** if
the target quantity type is dimensional (`length`, `area`), exactly one given must fix the figure's
scale (a stated segment length); scale-free types must have *no* length givens (they'd be redundant and
fail Stage-6 minimization anyway).

### Stage 3 — Numeric pre-checks (before the engine call)
Instantiate once with a fixed reference seed. Reject: point pairs closer than ε_sep; triangle areas below
ε_area; angles within ε_deg of 0°/180°; **undeclared near-coincidences** (accidental near-collinearity /
near-equality the construction didn't declare — they confuse diagrams and destabilize side conditions).
All thresholds in `config/`, never inline.

### Stage 4 — Closure via SAL
One `solve()` call (doc 03). Discard on resource-cap hit (logged with seed). A numeric contradiction
between the engine's derived values and the reference model is a **hard bug** — abort with a serialized
reproduction, never skip.

### Stage 5 — Goal selection (quantity-goal adapter)
Candidate goals = facts extracted by the enabled quantity types' `goal_extractor`s (§QTR) with exact
values, produced by the **numeric-propose / symbolic-verify** sweep of `docs/03 §3.3a` (measure on the
reference diagram → snap to an exact value → require symbolic verification). Closure-scanning is a
secondary source only. Two rejections that are easy to get wrong (M3): a goal identical to one of the
construction's **own stated givens** is not a puzzle, and catching it requires comparing *canonical*
facts — the engine reorders an angle's points, so the proposal's spelling need not match the given's.
And candidates are **all verified before any is chosen**, then ranked; taking the first N as they
verify selects on the extractor's enumeration order rather than on the puzzle being any good. Prefer goals whose minimal derivation: depth within the target band; ≥ 3 distinct rules;
late-introduced element; answer satisfying the type's `answer_policy` exactness class. For dimensional
goals, verify the scale-pinning given is a *leaf of the goal's derivation* (a length goal whose proof
never uses the stated unit is a ratio goal in disguise — retype it). Up to N_goals per construction
become independent candidates (dedupe later). Thresholds live in `config/`, shared with doc 05's
filters — single source.

### Stage 6 — Traceback + premise minimization + configuration facts
- Extract the minimal-cost sub-DAG for the goal (shortest hyperpath; ties → fewer distinct premises).
- **Configuration facts are first-class.** The figure's topological configuration — betweenness, arc
  side, orientation region for every rule application whose validity depends on it — is recorded as
  explicit facts attached to the sub-DAG. **Source (verified in Phase 0):** Newclid's
  `NUMERICAL_PREDICATES` — `sameside`, `nsameside`, `sameclock`, `obtuse_angle`, `ncoll`, `npara`,
  `nperp` — which surface in proofs as "Numerical checks" (`N*` ids). They are premises for
  well-posedness purposes even though no rule consumes them symbolically, and they are what
  disambiguates the directed→vertex angle conversion (`docs/03 §3.5`). *This closes the old design's
  central soundness hole: minimization silently stripping configuration information.*
- **Three kinds of leaf, not two** (M3): stated premises, configuration facts, and the engine's own
  *tautologies* (`eqangle a o c o a o c o` and friends, arriving as "trivial predicates"). Tautologies
  are leaves of the derivation but they are neither givens nor configuration: the puzzle must not state
  them, and they must never be fed back as assumptions — Yuclid aborts the process with "Trying to
  re-prove a statement" when asked to assume what it derives as trivially true.
- **Greedy premise minimization** over stated (non-configuration) leaves only: drop a leaf, re-run a
  restricted closure over the *same fixed coordinates* (`solve_facts`, doc 03 §3.3), keep dropping while
  the goal survives. Redundant givens feel sloppy and leak hints. Ordering is canonical, and the result
  is locally rather than globally minimal — doc 07 T11. After minimization the derivation is **re-derived
  from the surviving premises**: the recorded proof must be the proof the stated givens support, or a
  solution step could cite a given the puzzle no longer makes.
- The surviving leaves + goal define the stated givens **and the drawn figure**; scaffolding no surviving
  fact references is pruned — *plus* any element a translated solution step highlights (steps may
  reference segments their premises only imply).

### Stage 7 — Readable-steps translation gate
Translate the sub-DAG per doc 03 §3.5. Untranslatable ⇒ discard, log offending rule. Output: final
`solution[]` steps.

### Stage 8 — Well-posedness gate (critical correctness gate)
Stated premises **+ configuration facts** must uniquely determine the goal value. For scale-free
quantity types the check runs modulo similarity (resampled figures may differ in scale/pose); for
dimensional types the resampler holds the pinned unit fixed and the goal value must be invariant
absolutely.
1. Resample M = 64 instantiations: re-run the construction with fresh free parameters, **rejecting any
   sample whose configuration facts differ from the reference** (a configuration flip is a legitimate
   different figure, not evidence of ill-posedness — and not a bug).
2. Accept iff the goal's numeric value deviates < ε_wp across all accepted samples.
3. A deviation *within* matching configurations ⇒ discard **and** file a high-priority reproduction case
   (soundness bug upstream). Deviation across flipped configurations ⇒ normal discard of the sample, not
   the puzzle.
4. Known residual limit: construction-based sampling explores the construction's parameterization of the
   premise manifold, not the whole manifold. Recorded as accepted risk (doc 07 T3) with the cross-engine
   validation and optional SMT check as compensating controls.

### Stage 9 — Emit
`CandidatePuzzle` (construction, premises, configuration facts, goal, exact answer, translated steps,
provenance incl. engine version). Hand to scoring (doc 05).

## §V — Bank-build validation (doc 02 invariant 3)
Every accepted puzzle is re-derived from scratch by the **ag2ddar** backend (uncorrelated codebase):
premises + coordinates in, goal fact must be derivable out, answer must match exactly. Plus: schema
validation, numeric re-check at bank tolerances, optional SymPy/Gröbner spot-check on a sample, and
mutation tests (corrupt an answer / drop a premise ⇒ validator must reject — a validator that never fails
is untested).

## Tolerance policy (single source of truth)
Exact layer: derived values are exact rationals; equality is exact. Numeric layer: absolute tolerance on
normalized quantities (radians, unit-scale coords) from `config/`; degeneracy uses Stage-3 ε's. Never
compare floats for equality; never let a numeric check pass a fact no symbolic derivation produced.

## Determinism and parallelism
Pipeline is a pure function of `(config, engine_version, master_seed)`; seed-sharded across processes.
Every discard logs `(stage, reason, seed)`; the attrition report per stage **and per band** is the primary
regression signal — drift between builds means a sampler/engine/translator change did something.

## Failure-mode checklist
| Failure | Guard |
|---|---|
| Degenerate figure | Stage 3 |
| Engine soundness bug | Stage 4 numeric guard + §V cross-engine + mutation tests |
| Unreadable solution | Stage 7 gate (attrition, never shipped) |
| Configuration-dependent ambiguity | Stage 6 configuration facts + Stage 8 matching-configuration sampling |
| Redundant givens | Stage 6 minimization |
| Under-determined goal | Stage 8 |
| Scale-unpinned dimensional goal (answer depends on drawing size) | Stage 2 scale pinning + Stage 5 leaf check + Stage 8 |
| Figure leaks undeclared info | Stage 6 pruning + doc 06 anti-leak layout |
| Duplicates | bank dedupe (canonical hash over type-refined labeled premise/goal hypergraph — algorithm specified in `bank/dedupe.py`) |
| Correlated generator/validator bugs | different engines for generation vs validation |
