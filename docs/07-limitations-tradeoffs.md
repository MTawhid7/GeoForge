# 07 — Known Limitations, Trade-offs, and Recorded Decisions

Record of deliberate decisions. When revisiting any entry, update this document in the same commit.
"We chose X over Y because Z" entries here outrank fresh instincts in a coding session — change the doc
first if you disagree. Decisions from the pre-pivot spec that survive are re-recorded here; the research
basis for the pivot itself is `research/`.

## 7.1 Pivot decisions (P)

**P1 — Build on existing engines; reverse of the original "build from scratch" decision.** The pre-pivot
spec explicitly rejected reusing provers (learning goals, integration cost, licensing risk). Reversed
2026-08: AG2's DDAR was open-sourced (Apache-2.0, Jan 2026), Newclid 3 provides a maintained Apache-2.0
engine + `ncdgen` generation scaffold, and the research record (`research/01`) shows a from-scratch
engine would trail these systems permanently. Consequences: we accept third-party dependency risk,
mitigated by the SAL (doc 03) and the last-resort homegrown-backend slot. **The owner's original
learning-by-building goal is consciously traded** for systems-integration learning; the homegrown SAL
backend slot remains the sanctioned sandbox if the itch returns.

**P1a — Dependency tiers (settled 2026-08-01, after Phase 0 evidence).**
*Depend, hard-pinned:* `newclid==3.0.1` + `py-yuclid==3.0.0` (21.5k LOC Python + 7.9k LOC C++ we do
not want to own; a hard pin already gives full isolation from upstream churn).
*Vendor:* AG2 DDAR (`vendor/ag2_ddar/`, 2.4k LOC, unpackaged so there is nothing to pin).
*Vendor & diverge:* the generation loop (ncdgen is a model, not a dependency).
*Ideas only:* GPL sources.
**Amendment from Phase 0:** we also permanently own `newclid_patches` — a small module fixing
upstream defects in the pure-Python path. Upstream CI exercises only the Yuclid backend, so that
path is under-tested; the patch module is standing infrastructure, not a stopgap. Escape hatch
unchanged: newclid is Apache-2.0 and the clone is retained, so full vendoring remains available if
upstream is abandoned or a deeper patch is needed.
**Amendment from Phase 1 M3:** the patch module is no longer only about the pure-Python path.
BUG-3 (`ProofState.justify` raising `ValueError` where its caller catches `JustificationError`,
making the "goal is unprovable" path dead code) affects *every* backend, Yuclid included. It
surfaced immediately once we started asking questions whose expected answer is "no" — which is
what premise minimization does all day. Expect the patch set to keep growing as we use the engine
in ways its own test suite does not.

**P1b — Performance strategy: no second language.** Phase 0 measured 95% of wall time inside the
engine and 23–26× speedups from Yuclid's existing C++ core. Our own code is orchestration. A
Rust/Go/C++ component is justified only if profiling later shows > 30% of wall time in *our* Python
**and** throughput misses the per-band target in `docs/01`; revisit here at that point.

**P2 — License policy.** Apache/MIT/BSD dependencies may be linked (newclid, yuclid, ncdgen, AG2 DDAR,
SymPy, Penrose-as-reading). GPL code (`tong-geometry/`, FormalGeo) is **ideas-only**: no copied code, no
imports; subprocess isolation if ever unavoidable. LGPL (GeoCoq) unused. Verified license files live in
the reference clones; re-verify on every engine upgrade.

**P3 — Engines are consumed, not extended.** If an engine gap blocks a puzzle family, the family waits
(doc 03 §3.7). Deviating (patching an engine) requires an upstream-PR-first policy and an entry here.

## 7.2 Fundamental limitations (L)

**L1 — No auxiliary-construction puzzles in v1.** Forward chaining only derives facts about existing
points. v1's ceiling is "hard angle chase", not olympiad. Mitigation path (doc 09 P3): generate *with*
the auxiliary element via Newclid's agent API (heuristics now, LLM proposer later), then hide it.
Clarification from the old spec's Langley confusion: a Langley-class figure **with its auxiliary line
included in the construction** is forward-chainable and serves as an engine fixture (doc 03 §3.3); the
classic statement *without* the line stays out of scope until the hide mechanism exists.

**L2 — Generated ≠ curated.** The median generated puzzle is workmanlike; outliers are surfaced by the
elegance ratio + gem promotion (doc 05), not oversold.

**L3 — Rule-vocabulary-bounded readability.** A puzzle can only ship if its proof translates through our
readable-step whitelist (doc 03 §3.5). Coverage grows by extending the whitelist, driven by the discard
log. Difficulty ceiling grows the same way — deliberate, incremental work.

## 7.3 Accepted technical trade-offs (T)

**T1 — Human-natural undirected angles in presentation.** Engines internally use robust representations;
our translation layer presents undirected angles in (0°,180°) because directed/full-angle prose is alien
to the audience. Cost: configuration side-conditions become *our* problem at the presentation and
well-posedness layers — handled by T2.

**T2 — The figure is part of the puzzle statement.** "Solvable from exactly the information shown" means
premises **plus the figure's topological configuration** (arc sides, betweenness, orientation), which the
metrically-consistent figure conveys. Configuration facts are therefore first-class in traceback and
well-posedness (doc 04 stage 6/8). This is standard human puzzle-culture semantics, now explicit instead
of accidental.

**T3 — Well-posedness sampling is construction-parameterized.** Stage-8 resampling explores the
construction's parameterization of the premise manifold, not the whole manifold; exotic
premise-satisfying configurations unreachable by the construction are not sampled. Compensating controls:
cross-engine §V validation, configuration-fact matching, optional SMT/Gröbner checks on samples. Accepted
residual risk; revisit if §V ever catches a class of misses.

**T4 — Pre-rendered solution text; per-locale banks.** Solution sentences are baked into bank JSON from
the string table at build time (frontend stays logic-free and replay-verbatim). Cost: translation = bank
rebuild per locale. Accepted for v1 (English only).

**T5 — To-scale figures make answers measurable.** Metrically consistent figures + integer answers mean
a player can protractor-measure the goal to within a degree or two. Accepted: single-player app, honor
system — measuring only cheats yourself (same stance as sudoku apps and chess trainers). Revisit only if
competitive/leaderboard features appear.

**T6 — No CAS in the hot loop.** SymPy is validation-layer only (spot checks, Gröbner third opinions) —
plus exact-value normalization and the wave-3 area layer's *arithmetic on engine-certified quantities*
(doc 03 §3.7), which is bookkeeping, not derivation. The generation loop stays engine + exact values.

**T7 — Quantity-generic core, phased enablement.** Schema, gates, scoring, and frontend are written
against the quantity-type registry (doc 04 §QTR); types are enabled in waves (angle → length/ratio →
area) strictly by engine-support maturity (doc 03 §3.7), never by editing core pipeline code. Dimensional
quantities require scale pinning (one stated unit length as a derivation leaf); scale-free quantities
forbid it. Areas are not engine-derivable and wait for the custom decomposition layer — shipping them
earlier via coordinate computation would violate "numeric verifies, never derives".

**T8 — Answer input by exactness class.** Angles: integer keypad. Ratios: p/q fraction input. Lengths/
areas: decimal input checked within a per-puzzle tolerance against `approx`, with the exact surd form
revealed on solve. Rejected alternative: structured exact-form input (`a + b√c` fields) — hostile on
mobile and gatekeeps on notation rather than geometry; revisit only if tolerance collisions (two
plausible answers within tolerance) ever appear in practice, which the bank builder checks per puzzle.

**T9 — Line-and-circle figure universe; conics rejected for the synthetic engine.** The construction
DSL and sampler cover points, lines, all polygon families, circles, and arcs — the engines' native
domain and the classical puzzle universe. Conics are excluded because (a) no AG-lineage engine's fact
vocabulary contains them, so support would mean writing our own deduction rules — the exact path P3
forbids; and (b) puzzle-culture conic problems are coordinate/algebraic in nature and belong to the
future coordinate-geometry/algebra domain (doc 09 P6), where SymPy-verified generation handles them
cheaply. Revisit only if an upstream engine ships conic support.

**T10 — Difficulty is a phased capability (honest ladder).** v1's ceiling without auxiliary
constructions is "hard chase" (challenges strong amateurs; below true olympiad). The ladder to
olympiad-entry runs through aux-construction hiding (doc 09 P4) — the mechanism validated by
TongGeometry's competition-selected problems — and the top rung (olympiad-grade via value-guided search
at scale) is an architected aspiration, not a commitment. Full ladder: doc 01 §Difficulty ambition.
Bands are never inflated to fake the upper rungs.

**T11 — Premise minimization is greedy, so locally minimal (settled Phase 1 M3).** Premises are
tried for removal in canonical order and every successful drop is kept, which yields a set with no
removable member but not necessarily the smallest such set — a different order could find a smaller
one. Finding the true minimum means searching subsets, exponential in the premise count, and buys
little: puzzles carry a handful of premises, and "no given is redundant" is the property that
matters to a solver. What is *not* optional is determinism, so the ordering is canonical rather than
incidental (doc 02 invariant 2). Revisit only if generated puzzles are observed carrying givens a
human would call redundant.

## 7.4 Open risks (monitored, not yet mitigated)

- ~~**O1 — Translation coverage unknown.**~~ **RESOLVED by Phase 0 (2026-08-01).** Measured: 86% of
  proof steps translate; 82% of puzzles translate fully at `max_ar_chain=5`; only 13 distinct engine
  rules fire across the corpus. Gate passed, hybrid fallback not needed. Residual work is the idiom
  collapser and the directed→vertex angle converter (`docs/03 §3.5`), both specified.
- ~~**O7 — Cross-engine convention mismatch.**~~ **RESOLVED by Phase 1 M6 (2026-08-02).** Calibrated:
  DDAR reads a valued angle's two line pairs in the opposite order, so the exporter swaps them
  (doc 03 §3.2a). Only `aconst` is affected — `eqangle`/`para`/`perp` are differences of directed
  angles and survive negation. Negative control: without the swap, 25 of 129 puzzles validated, exactly
  the 25 answering 90° (its own supplement). Pinned from both directions by a unit test on a
  non-right-angled figure. Full cross-validation now runs: 129/129 re-derived, zero disagreements.
- **O2 — Attrition economics per band unknown**, especially expert. Order of response: better early
  rejection → grammar re-weighting → parallel scale-out → only then engine-level work.
- **O3 — Difficulty calibration vs. human perception** — weights are informed guesses until spot-check
  data accumulates; the contract is the feature set, not the weights.
- **O4 — Layout quality plateau** — automated layout may stall at "acceptable, not beautiful"; budget a
  dedicated iteration before adding puzzle types if spot checks flag it.
- **O5 — Dedup misses semantic duplicates** — isomorphism hashing catches relabelings, not "same idea,
  different figure". Monitor via spot checks.
- **O6 — Upstream engine churn** — Newclid/AG2 release cadence may break adapters; pinned versions +
  contract tests + attrition-diff on upgrade are the guards.


**T12 — AR steps are narrated by their premises, not by their arithmetic (settled Phase 1 M4).**
Newclid does expose the explicit linear-combination coefficients behind an algebraic step (e.g.
`½·(∠OAC=∠ACO) − ½·(∠OBC=∠BCO) − ½·(AO∥BO) ⟹ ∠ACB = 90°`), and doc 03 §3.5 originally anticipated
using them to render arithmetic. We do not: coefficient-faithful text reads like linear algebra, not
geometry, and half-integer multipliers on angle *equalities* are not how anyone writes an angle
chase. Steps instead read "Combining ∠CAO = ∠OCA and ∠CBO = ∠OCB, we get ∠ACB = 90°", which is true,
checkable, and the standard human presentation. The coefficients remain available if playtesting
shows these steps read as hand-waving; the premise-count budget (`max_ar_chain`) already keeps them
short enough to follow. Revisit trigger: playtest feedback that AR steps feel unjustified.


**T13 — Configuration facts do not fully pin a figure; underdetermination is attrition, not a bug
(settled Phase 1 M5; amends doc 04 Stage 8 item 3).** Doc 04 originally treated a goal that moves
between configuration-matching resamples as an upstream soundness bug, on the assumption that the
recorded configuration facts describe the figure completely. M5 measured that they do not. The
engine surfaces the numerical checks its *rules* required, not a full description of the
configuration, and some are tautologies (`sameclock a f i a f i`) that constrain nothing; separately,
an angle-chased `aconst` can depend on the reference diagram's angle atoms without any recorded fact
capturing that dependence. Verified on a concrete case (`tests/generator/test_wellposed.py`
`UNDERDETERMINED`): every stated premise and every recorded configuration fact holds in a second
figure where the answer is 15° instead of 75°. Consequence: these puzzles are **discarded as ordinary
attrition** (~1.7% of formed puzzles) rather than failing the build. Calling each one a soundness bug
would cry wolf and bury the one failure that genuinely indicts the engine — a fact proved
symbolically that is false in its own diagram — which is what now fails the build, and which measured
zero across 1,200 constructions. Revisit if a richer configuration vocabulary (explicit side-of-line
facts) ever makes the recorded set complete.


**T14 — Cross-validation certifies the answer over the reference diagram, not over the whole premise
manifold (settled Phase 1 M6).** The second engine is handed the puzzle's premises *and its exact
coordinates*, and asked whether the goal follows. It is not handed the configuration facts: DDAR has
no `sameclock` or `sameside` vocabulary, and it does not need one, because the diagram it receives
already has a configuration. The consequence is a real boundary on what the check buys. It catches a
wrong answer, a non-following goal, and a corrupted artifact — independently of Newclid, which is the
point. It does *not* re-run the well-posedness argument: whether some *other* diagram satisfying the
same premises would give a different answer is Stage 8's question, answered on the generation side by
resampling, and cross-validation does not second it. Both engines are also diagram-guided in the same
paradigm (DDAR's similar-triangle search reads orientation off the coordinates exactly as Newclid's
numerical checks do), so the independence claimed here is *codebase* independence, not independence of
method. That is still the property that matters — doc 02 invariant 3 exists so a bug in one engine is
not mirrored in the other — but it should not be over-read. Alternative rejected: reconstructing a
configuration-free premise set for DDAR to solve from scratch, which would need a betweenness/side-of-
line vocabulary neither engine exposes, and would test our reconstruction rather than the puzzle.
Revisit if the optional SMT/Gröbner spot-check (doc 04 §V) lands, since that one *is* method-independent.


**T15 — The SAL has two roles, not one (settled Phase 1 M6).** Doc 03 originally specified a single
backend contract that every engine implements, and the M1 contract suite was written expecting the AG2
adapter to inherit it unchanged. It cannot: DDAR has no construction language (no `solve` on JGEX, no
`realize`), no proof recorder (`proof_dag.steps` is permanently empty), and no configuration predicates
(no `check_facts`). Forcing it into `SolverBackend` would have meant three methods that raise and a
contract suite silently skipping most of itself — the shape of a test suite that looks green because it
is not running. So `ValidatorBackend` (`name`, `engine_version`, `solve_facts`) is now a separate,
smaller protocol, `SolverBackend` extends it, `isinstance(validator, SolverBackend)` is deliberately
False, and the validator carries its own contract suite. This costs the ability to run one shared
fixture corpus across both engines, which is a smaller loss than it sounds: the corpus is expressed as
JGEX constructions, and DDAR could never have consumed those anyway. Revisit if a future validator
engine (Seed-Geometry?) turns out to record proofs, in which case it can implement the larger protocol
without changing the smaller one.
