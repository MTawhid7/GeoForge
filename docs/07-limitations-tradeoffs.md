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

## 7.4 Open risks (monitored, not yet mitigated)

- ~~**O1 — Translation coverage unknown.**~~ **RESOLVED by Phase 0 (2026-08-01).** Measured: 86% of
  proof steps translate; 82% of puzzles translate fully at `max_ar_chain=5`; only 13 distinct engine
  rules fire across the corpus. Gate passed, hybrid fallback not needed. Residual work is the idiom
  collapser and the directed→vertex angle converter (`docs/03 §3.5`), both specified.
- **O7 — Cross-engine convention mismatch.** AG2 DDAR's directed-angle orientation is *inverted*
  relative to Newclid (verified). The validator adapter must calibrate (θ vs 180−θ) or it reports a
  soundness failure on every puzzle. Full cross-validation is deferred to Phase 1 (needs the
  coordinate exporter).
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
