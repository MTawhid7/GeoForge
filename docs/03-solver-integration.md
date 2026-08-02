# 03 — Solver Integration (replaces the former hand-built core engine)

We do not write deduction rules. The reasoning core is imported from the AlphaGeometry lineage and wrapped
behind the Solver Abstraction Layer (SAL). This doc specifies the SAL, the engine backends, and the
trace-to-readable-steps translator — the three pieces that make an external prover usable as a puzzle
factory.

## 3.1 How the engines work (what we're consuming)

AG-lineage engines combine:
- **DD (deductive database):** forward chaining to fixpoint over a few hundred geometric rules —
  the industrial version of what the old spec planned to hand-write (~25 rules).
- **AR (algebraic reasoning):** Gaussian elimination over exact linear relations among angle, ratio, and
  distance atoms — the completed version of the old spec's deferred "AR-lite".
- **Proof recording:** every derivation is a hyperedge (premises → rule → conclusion); tracing back from
  any fact yields its minimal derivation. This DAG is the raw material for solutions and difficulty.
- **Numeric diagram model:** engines carry coordinates for degeneracy/side-condition checking — aligned
  with our "numeric verifies, never derives" invariant.

## 3.2 Engine backends

| Backend | Source | License (verified) | Role |
|---|---|---|---|
| `newclid` + **Yuclid** | `newclid==3.0.1` (PyPI, pinned) + `py-yuclid==3.0.0` (prebuilt wheel) | Apache-2.0 | **Primary**: generation-time closure + traced proofs; JGEX and GeoGebra input |
| `newclid` pure-Python | same package, `api_default=PythonDefault()` | Apache-2.0 | **Debug/fallback only** — see the Phase 0 findings below |
| `ag2ddar` | vendored at `vendor/ag2_ddar/` | Apache-2.0 | **Validator only** (`ValidatorBackend`, M6): independent re-derivation of banked puzzles from premises + coordinates. Angle convention is inverted — calibrate (§3.2a) |
| (future) | Seed-Geometry if released; homegrown mini-engine as last resort | — | Swap-in via SAL |

**Phase 0 measured findings (see `spikes/p0/REPORT.md`) — these override earlier assumptions:**
- **Yuclid is primary, not optional.** It is 23–26× faster on non-trivial problems and solved
  11/23 of the spike set vs 8/23 pure-Python. Prebuilt wheels exist, so no cmake/Boost build.
- **The pure-Python path carries real upstream bugs** (its AR deductor and rule matcher are
  replaced by Yuclid in upstream CI, so they are effectively untested). `MappingMatcher` cannot
  apply any rule containing a numeric constant. We keep a permanent `newclid_patches` module for
  the fixable ones; the matcher defect is why pure-Python is not the primary backend.
- **Yuclid rejects `acompute`/`lcompute`/`rcompute` — and we do not need them** (§3.3a).

Also in the Newclid monorepo: **`ncdgen`** (Apache-2.0, contributed by Harmonic) — synthetic JGEX problem
data generation on top of Newclid, hydra-configured. Our generator (doc 04) starts as an adaptation of
`ncdgen`'s loop with our goal-selection and gating stages replacing its dataset-oriented output. Study
`Newclid/ncdgen/src/ncdgen/generation_configuration.py` first.

## 3.2a Cross-engine convention calibration (measured, M6)

DDAR's `aconst p q r s` asserts `dir(pq) − dir(rs) = value`; Newclid's — and therefore GeoForge's
normative convention (`solvers/types.py`) — asserts `dir(rs) − dir(pq) = value`. Every valued angle
handed to the validator must therefore have its **two line pairs swapped**. Swapping is preferred to
rewriting the value as `180 − value`: it is exact on `Fraction`s and needs no mod-180 normalization
at value 0.

Only *valued* angles need it. `eqangle`, `para` and `perp` reduce to a **difference** of directed
angles, which inverting the orientation merely negates — and a negated zero is still zero, a negated
right angle is still a right angle. So exactly one predicate family is affected, which is what makes
the calibration testable rather than a pervasive sign convention.

**Negative control (the number that makes this real):** validating the 129-puzzle acceptance bank
*without* the swap accepted 25 of 129 — precisely the 25 whose answer is 90°, the one angle equal to
its own supplement. An uncalibrated validator would have rejected every non-right-angle puzzle and looked
exactly like a catastrophic generator soundness bug. This is why `tests/solvers/test_ag2_contract.py`
pins the convention on an equilateral figure (60° ≠ 120°) from **both** directions: the calibrated
spelling must be accepted and the uncalibrated one rejected. A right-angled fixture would agree with
itself either way and prove nothing.

Coordinates must not travel as text. DDAR's `AGProblem.pstring` round-trips points through `name@x_y`
and asserts premises numerically at ~1e-6, so the adapter builds `AGPoint` objects from float64
directly; the string form exists only for reproduction cases.

## 3.3a Quantity extraction: numeric proposes, symbolic verifies

The engines' `*compute` query predicates are **not** used. Instead the SAL replicates what
`acompute` does internally, which both frees us from Yuclid's limitation and keeps soundness
symbolic:

1. Measure the candidate quantity on the reference diagram (numpy over the engine's coordinates).
2. Snap it to an exact value using the quantity type's own nice-value rule (`docs/04 §QTR`). For
   angles that is **a whole number of degrees within an absolute tolerance**
   (`config.EXTRACTION.angle_snap_tolerance_degrees`), which is also the type's `answer_policy`.
3. Ask the engine to **symbolically verify** the explicit `aconst` / `lconst` / `rconst`.

**Amended in Phase 1 M3 — do not use `newclid.tools.get_quotient` as the nice-value filter.** Its
tolerance is *relative*, so the effective acceptance window grows with the denominator and it will
snap almost any value given denominators up to 1e6: on the Phase 0 tangent-chord figure it returned
17/19 for a generic angle. Soundness was never at risk (step 3 rejected it), but every junk
candidate costs an engine call, and a denominator like 19 is not an answer any human would accept.
Measured on realized figures: a genuinely exact angle lands within 1e-13 of its integer-degree
value while an arbitrary one is ~1e-2 away, so an absolute filter separates them with seven orders
of margin.

Numerics only ever *propose* a candidate; the accepted value is always symbolically derived.
Validated in Phase 0 (`spikes/p0/s1b_aconst_probe.py`): 6/6 behaviourally correct — 4 verified,
and 2 correctly rejected because the angle was genuinely underdetermined by the premises.

**Verification runs over fixed coordinates** (`SolverBackend.solve_facts`, §3.3), never by
re-parsing the construction with the goal attached: `JGEXProblemBuilder.build()` retries until every
stated goal holds numerically, so handing it an under-determined candidate produces a hang instead
of a rejection.

Corollary for `docs/04` Stage 5: goal candidates come from this sweep over point tuples.
Scanning the saturated closure for `aconst` facts is a *secondary* source only — Phase 0 found
just 3 explicit `aconst` facts across 6 saturated constructions.

## 3.3 The SAL contract

```python
@dataclass(frozen=True)
class SolveResult:
    facts: FactStore          # canonical facts incl. numeric-valued angle atoms
    proof_dag: ProofDAG       # hyperedges: (premise_ids, rule_name, conclusion_id)
    numeric_model: CoordMap   # the engine's reference coordinates
    stats: SolveStats         # wall time, fact count, saturation/cap status

def solve(construction: Construction, opts: SolveOptions) -> SolveResult: ...
def solve_facts(spec: PremiseSpec, opts: SolveOptions) -> SolveResult: ...
def realize(construction: Construction, opts: SolveOptions) -> RealizedFigure: ...
```

`solve_facts` states a problem as **facts over a fixed point set** rather than as a construction
(added in M3). Stage 6's "drop a premise and re-run a restricted closure" cannot be expressed any
other way — there is no construction for "the same figure, minus one hypothesis" — and holding the
coordinates fixed is what keeps configuration facts available to the engine's numerical checks no
matter which premises are dropped. It suits the M6 validator too: DDAR consumes premises and
coordinates natively. `realize` instantiates coordinates without running deduction, so Stage 3 can
reject a degenerate figure before paying for a closure.

**Two roles, two protocols (amended M6).** The SAL is not one interface implemented by every
engine. `SolverBackend` is the *generation* contract — `solve`, `solve_facts`, `realize`,
`check_facts`. `ValidatorBackend` is the strictly smaller *validation* contract: `name`,
`engine_version`, `solve_facts`, and nothing else. AG2 DDAR implements only the second, because it
genuinely has only that much: no construction language (so no `solve` on JGEX and no `realize`), no
proof recorder (so `proof_dag.steps` is always empty), and no configuration predicates (so no
`check_facts`). Declaring it a full `SolverBackend` would have meant three methods that raise and a
contract suite quietly skipping most of itself, so `isinstance(validator, SolverBackend)` is
deliberately False and the validator carries its own contract suite
(`tests/solvers/test_ag2_contract.py`). Re-derivation is all bank validation asks for; the readable
proof always comes from the generation engine.

Requirements on every **generation** backend adapter:
- **Determinism:** same `(construction, seed, engine_version)` ⇒ identical `SolveResult`. Verified by a
  contract test that runs each backend twice and diffs.
- **Fact normalization:** adapter maps engine-native facts into our canonical fact vocabulary (angle
  values as exact rationals, symmetric facts sorted) so downstream code is engine-agnostic.
- **Trace fidelity:** every fact in `facts` must be reachable in `proof_dag` from construction-contributed
  premises; asserted by a DAG-integrity contract test.
- **Resource caps:** wall-time and fact-count caps surfaced in `stats`; cap hits are generator-level
  discards with logged seeds, never silent.

A **validator** backend must additionally raise on any fact it cannot express (`UnsupportedByValidator`)
rather than dropping it. Dropping a premise hands the second engine a weaker problem than the puzzle
claims, so its "yes" would certify something the puzzle never stated — the one way cross-validation
can pass without being a check at all.

Contract tests run against **all** generation backends on a shared fixture corpus: classic
configurations (isosceles chains, cyclic quadrilaterals, Thales, a Langley-class figure *with its
auxiliary line included in the construction* — solvable by pure forward chaining in that form).

## 3.4 Construction DSL

Surface syntax is **JGEX-compatible** (the lingua franca of AG1/AG2/Newclid — see
`Newclid/newclid/problems_datasets/` for corpora). Our `Construction` type is a thin typed layer over it:
ordered steps, named points, explicit free parameters, plus **configuration facts** (doc 04 §stage-6)
that JGEX leaves implicit. Serializes to provenance strings. We gain for free: engine input, benchmark
problems as test fixtures, and interchange with every tool in the ecosystem.

## 3.5 Trace → readable steps (the pivot's hardest component)

Engine proofs are correct but not player-ready. The translator converts a traced sub-DAG into the
`solution[]` steps of doc 02's schema:

1. **Rule whitelist:** a curated map `engine_rule → (template_id, highlight builder)` for rules with
   natural one-sentence readings ("base angles of an isosceles triangle", "angles subtending the same
   arc", "corresponding sides of similar triangles", "Pythagoras in the right triangle ABC").
   Maintained in `src/geoforge/generator/translation/`; templates are organized per quantity family, and
   enabling a new quantity type (doc 04 §QTR) requires its template set to exist. There is
   deliberately **no generic fallback**: a rule nobody has read is a rule nobody can vouch for the
   prose of, so an unlisted rule fails the gate.
   *Rule ids are engine-specific* (M4): the ids that fire come from the 87-rule catalogue in
   `newclid.all_rules`, not the 58-rule `DEFAULT_RULES`. The whitelist is therefore coupled to the
   generating backend — harmless today, since the AG2 backend validates and never translates, but it
   means a backend swap needs a whitelist review, not just an adapter.
1b. **Suppression, distinct from failure.** A few rules are correct, load-bearing, and unfit to
   print: `r82 Parallel from collinear` reports two segments of one straight line as parallel, and
   `r56 Properties of midpoint (coll)` concludes that a midpoint lies on its own segment. Their steps
   are dropped from the text while their conclusions stay available to later steps. Suppression is
   narrow and each entry carries a written reason; the default for an unknown rule is to fail.
2. **AR step shaping:** AR derivations (linear combinations of angle relations) are re-expressed as
   bounded chains of readable arithmetic ("∠1 + ∠2 = 110° and ∠1 = 40°, so ∠2 = 70°"). Chains using
   more than `config.max_ar_chain` premises are deemed unreadable.
   **`max_ar_chain = 5`** (Phase 0 measured sensitivity: budget 3 → 46% of puzzles fully
   translatable, 4 → 55%, **5 → 82%**, 7 → 91%. The gate needs ≥ 80%.)
   **Re-measured in M4 on generated puzzles**, independently reproducing the curve's shape:
   3 → 42%, 4 → 81%, **5 → 91%**, 6 → 95%, 7 → 100%. The value 5 stands.
   AR steps are narrated by listing their premises and conclusion ("Combining X, Y and Z, we get
   W") rather than by rendering the linear combination itself — recorded trade-off, doc 07 T12.
2b. **Idiom collapsing (required).** Engine proofs contain fixed multi-step idioms that must map to
   *one* human step, not one each. The dominant one (15 of 95 steps in the Phase 0 corpus): an AR
   ratio restatement → `SAS Similarity (Reverse)` of a triangle **with itself** → `Properties of
   similar triangles` is always just "isosceles ⇒ base angles equal". Translation is therefore
   compression: measured in M4, 257 machine steps become 186 sentences, and the 10-step machine
   proof of Thales becomes 6.
   **Generalized in M4.** Both measured idioms share one shape — the engine manufactures a
   *degenerate intermediate* (a statement trivially true and saying nothing) to fit the shape of a
   general rule. So the implementation keys on **scaffolding facts** rather than on step patterns:
   a triangle similar to itself; a ratio equal to its own reciprocal (`AO:CO = CO:AO`); a ratio of
   something to itself (`AJ:AJ = HJ:IJ`, which is the shared-side similarity idiom). Any step
   consuming one absorbs the derivation behind it and cites that derivation's real inputs.
   Two traps found while implementing: absorbing must stop at genuine reasoning (an early version
   recursed through *any* equal-angle premise and swallowed real steps), and the isosceles template
   may only override a step that concludes an **angle** — `r53` reads ratio consequences out of the
   same similarity, and "the base angles are equal: AC : AD = AD : CD" is nonsense.
2c. **Directed→vertex angle conversion (required, universal).** Every angle fact the engines emit is
   a directed line-to-line angle `∠(XY,ZW)` mod π — **48 of 48** in the Phase 0 corpus — never a
   human vertex angle `∠ABC`. `∠(BA,BC) = 40°` renders as ∠ABC = 40° **or** 140° depending on
   configuration, so every published step needs conversion disambiguated by the configuration facts
   of `docs/04` Stage 6. This is the translator's central job, not an edge case.
   **Mechanism (M4).** The reference diagram is a model of (premises + configuration facts), so the
   vertex angle is read off it and *checked* to be one of the two values the proved directed fact
   allows; a measurement matching neither is refused rather than guessed. This is a presentation
   choice resolved by a model — the mathematical content stays the directed fact the engine proved.
   Two lines that do not meet at a named point yield no vertex angle at all: that step is
   untranslatable, and its puzzle is discarded rather than described awkwardly.
   **This creates a dependency on Stage 8** (`docs/04`, amended): the gate must resample and check
   the vertex angles of *solution steps*, not only the goal value.
3. **Readability gate:** a puzzle is accepted **only if every step of its minimal derivation translates**
   via 1–2. Untranslatable puzzles are discarded and logged by offending rule — the discard log is the
   priority queue for extending the whitelist. This converts the readability risk into attrition, never
   into shipped ugliness (doc 01 success criteria).
4. Translated text comes from the per-locale string table keyed by `template_id` (doc 02 localization
   decision).

## 3.6 Engine upgrade & patching policy

- Pin exact engine versions; record in bank provenance. Upgrades go through the full contract-test suite
  + a fixed-seed bench batch with attrition-report diff (doc 08).
- Bugs found in engines: minimal reproduction upstream (both projects are active); temporary workarounds
  live in the adapter, never scattered downstream; tracked in `docs/07` §open-risks until resolved.
- Never fork silently: divergence from upstream must be a vendored fork with a patch list.

## 3.7 Quantity-type support matrix

What each quantity type needs from the engine layer, and where it comes from. This matrix — not
enthusiasm — decides the enabling order in doc 09.

| Quantity type | Derivation source | Status |
|---|---|---|
| `angle` | Engine DD rules + AR (linear relations over angle atoms) | **Native.** Enabled first |
| `ratio` | Engine AR over log-length atoms (`rconst`, `eqratio`, similar triangles) | **Native.** Scale-free — no unit needed. Second wave |
| `length` | Same AR machinery + a stated unit length pinning the scale; Pythagoras/metric rules present in Newclid's DDARN | **Native given scale pinning** (doc 04 stage 5). Second wave |
| `area` | **Not engine-derived.** Custom verified layer: decompose the target region into triangles whose sides/angles the engine has derived; compute exact areas symbolically (SymPy) from engine-certified quantities; each decomposition step becomes a readable solution step | Third wave; design doc required before build (doc 09) |
| future (arc length, perimeter, …) | Composition over engine-certified lengths/angles | Follows the area layer's pattern |

The area layer must obey the same invariants as everything else: inputs are engine-certified exact
quantities, every step translates through the readability gate, numeric checks verify but never derive,
and the cross-engine validator re-certifies the underlying engine facts. "SymPy computed it" is
acceptable only for *arithmetic on already-certified quantities*, never for geometric truth.

## 3.8 What we explicitly do NOT build

Deduction rules; algebraic angle reasoning; proof search; auxiliary-point heuristics (Newclid's agent API
provides these; an LLM proposer plugs into the same API later). If an engine gap blocks a puzzle family,
the default answer is "that family waits", not "we extend the engine" — deviations from this need a doc 07
entry.
