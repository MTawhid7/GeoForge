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
points. v1's ceiling is "hard angle chase", not olympiad. Mitigation path (doc 09 P5): generate *with*
the auxiliary element via Newclid's agent API (heuristics now, LLM proposer later), then hide it.
~~**Amended 2026-08-04:** L1 is about *hiding*, and it conflated two things. **Detecting** that a
puzzle's minimal derivation already requires a point no given names is free and lands in P3 M5 (T10) —
forward chaining derives facts about existing points, but nothing stopped those points from being
scaffolding the player is never told about. Whether current output contains any is unmeasured, and that
measurement is the milestone.~~
**Amendment retracted 2026-08-04 by M5 (T22); the original L1 was right and the amendment split a hair
that does not exist.** "A point no given names" cannot occur: the construction step that introduces a
point contributes its facts as premises, so the moment the proof uses the point, a given names it.
Detection and hiding are not two things — there is nothing to detect *until* something is hidden, which
is what L1 said before the amendment. Measured 0/163 at seed 42, and the `langley_with_auxiliary`
fixture reports empty despite genuinely needing its auxiliary line. L1 stands unqualified.
Clarification from the old spec's Langley confusion: a Langley-class figure **with its auxiliary line
included in the construction** is forward-chainable and serves as an engine fixture (doc 03 §3.3); the
classic statement *without* the line stays out of scope until the hide mechanism exists.

**L2 — Generated ≠ curated.** The median generated puzzle is workmanlike; outliers are surfaced by the
elegance ratio + gem promotion (doc 05), not oversold.

**~~L3 — Rule-vocabulary-bounded readability.~~ REVERSED 2026-08-04 — see T17.** L3 read: "a puzzle can
only ship if its proof translates through our readable-step whitelist (doc 03 §3.5); the difficulty
ceiling grows the same way — deliberate, incremental work." Measured in Phase 2 M3, that ceiling turned
out to be the binding constraint on the entire product, not a growth curve. The whitelist covers **19 of
Newclid's 93 rules**, and since a puzzle ships only if *every* step is sayable, the pipeline selects for
proofs assembled from the 19 things we can pronounce — which are, by construction, the elementary ones.
13 distinct rules appear across the whole corpus; circle theorems fire 10 times in 98 puzzles. The
discard log was supposed to drive whitelist growth, but it stayed nearly empty *because the
constructions were too simple to need better theorems* — a loop with no way out from inside. Replaced by
LLM rendering (T17), which makes all 93 rules shippable.

**L4 — The difficulty ceiling is now the generator, not the translator (2026-08-04).** With T17 removing
the translation gate, the binding constraint moves upstream to Stage 1: a weighted grammar growing
clauses at random over 87 primitives produces small, symmetric, right-angle-heavy figures, and 86% of
what it produces is degenerate (344 of 546 discards at seed 42 — degenerate_triangle 148, unrealizable
98, flat_angle 75). Nothing downstream can add difficulty a construction does not contain. Mitigation is
doc 09 P5 (configuration-seeded and backward generation); L4 is expected to be the standing limitation
for the next several phases, and saying so is the point of recording it.

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

**T5 — To-scale figures make answers measurable. AMENDED 2026-08-04: the mitigation was wrong, and the
problem is worse than "measurable".** The original entry read: metrically consistent figures + integer
answers mean a player can protractor-measure the goal to within a degree or two; accepted on the honor
system, since measuring only cheats yourself.

Two things were missed. First, **no protractor is needed when the answer is 45°** — and on the first
real bank, 71 of 98 answers were 45° and another 15 were 90°, so blind-guessing "45" beat the app 72% of
the time. That is not a player cheating themselves; that is the artifact being invalid. Second, the
honor-system defence assumes measuring is *harder* than solving. For a right angle or a half-right angle
in a to-scale figure it is strictly easier, and the puzzle has no content left.

The revised position keeps to-scale figures (doc 06 §6.3 item 2 — a not-to-scale figure would break
every premise) and attacks measurability from four other directions:
- **Reject the two values that are *recognised* rather than measured.** Nobody estimates a right angle;
  they see one, and 45° is a square's diagonal. Landed M4 as a Stage-5 rejection. Everything else on the
  round list is *guessable* but not *readable* — nobody tells 60° from 65° by eye — and belongs to the
  entropy cap below. Measured over 3,000 constructions: rejecting {45, 90} takes the modal answer share
  from 71.8% to 36.0%; extending to every multiple of 30 reaches 30.8% but halves the yield again, which
  is a bad trade and permanently excludes hard puzzles that happen to answer 60°.
- **Answer entropy is a build gate**, not an aesthetic: per-band caps on the share of the bank any single
  answer value may hold (doc 05 §5.2 filter 8). A share cap is the right instrument for the merely-round
  values precisely because it is adaptive — it deletes surplus, not a category.
- **Non-round angle values.** `aconst` carries a `Fraction` of π, so 7π/8 is as cheap as 90° — the round
  palette was our config, not a constraint (T18). Landed M4, with the caveat that it only reaches
  puzzles that state an angle at all, which was 2 in 22 before M4's `angle_weight`.
- ~~**Quantity types whose answers are not eyeball-readable.**~~ **WITHDRAWN 2026-08-04 (M4a), and this
  bullet contains its own refutation.** The argument was: angles have *recognisable landmarks* — 90°,
  45°, and in a symmetric figure 60° — while lengths, ratios and areas essentially do not, "the only
  comparable landmarks being 1:1 and 1:2, and both are normally *stated* as givens rather than being the
  answer." The first clause is right. The parenthetical was the whole finding and it was waved past:
  measured, **the only ratios this engine derives are 2 and ½** — precisely the 1:2 landmark — because
  r51 (midpoint, always ½) is the sole rule of 93 concluding a ratio constant and AR composes ratios
  multiplicatively (T21). "You cannot look at a figure and recognise √2" is also true and also moot: no
  quantity type derives √2 (T18, reversed). Ratio's modal answer share is 52.9% against angle's 36.0%,
  so as a T5 mitigation this one points the wrong way.

Three mitigations remain, not four. Revisit the fourth if a rule extension ever widens the derivable
ratio set — the argument becomes sound again the moment the landmarks stop being the whole codomain.

**T6 — No CAS in the hot loop.** SymPy is validation-layer only (spot checks, Gröbner third opinions) —
plus exact-value normalization and the wave-3 area layer's *arithmetic on engine-certified quantities*
(doc 03 §3.7), which is bookkeeping, not derivation. The generation loop stays engine + exact values.

**T7 — Quantity-generic core, phased enablement. AMENDED 2026-08-04: waves 1 and 2 merge.** The
mechanism is unchanged — schema, gates, scoring, and frontend are written against the quantity-type
registry (doc 04 §QTR); types are enabled by registration, never by editing core pipeline code.
Dimensional quantities require scale pinning (one stated unit length as a derivation leaf); scale-free
quantities forbid it. Areas are still not engine-derivable and still wait for the custom decomposition
layer — shipping them via coordinate computation would violate "numeric verifies, never derives".

~~What changed is the *ordering rationale*. Waves were sequenced by engine-support maturity on the
assumption that angle alone made a viable product. It does not (T5): angle-only means every answer is
eyeball-readable on a to-scale figure. `ratio` and `length` are therefore promoted from "second wave,
post-v1" to the same phase as the difficulty rebuild, and their justification is now **difficulty**
rather than variety. The engine cost is lower than the original sequencing assumed — see T18.~~

**RE-REVERSED 2026-08-04 by the M4a spike — the promotion is withdrawn; the mechanism above is not.**
The premise held (angle-only is eyeball-readable, T5) but the inference did not: promoting `ratio` and
`length` on *difficulty* grounds assumed their answers are harder to guess than angles', and measurement
says the opposite — 3 reachable values at 52.9% modal share against angle's 9 at 36.0%. The engine cost
really is low, which is what T18 got right; the engine *yield* is what matters and it is near-empty
(T21). Both types return to "later wave", now blocked on a rule set that concludes ratio constants
rather than on our sequencing. Note what this leaves standing: the registry mechanism was exercised by
the spike and needs no change, so the cost of enabling them stays low whenever the block clears.

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
future coordinate-geometry/algebra domain (doc 09 P7), where SymPy-verified generation handles them
cheaply. Revisit only if an upstream engine ships conic support.

**T10 — Difficulty is a phased capability (honest ladder). AMENDED 2026-08-04: the target audience
moved, and aux-construction detection moved earlier.** The entry stands in its essentials — bands are
never inflated to fake the upper rungs, and difficulty comes from proof structure rather than
presentation obstacles. Three changes:

1. **The audience is competition-trained, not "strong amateurs"** (doc 01). "Hard chase" is no longer an
   acceptable v1 ceiling; it is the thing the first bank did and it was solved at a glance.
2. ~~**Auxiliary constructions move from P4 to P3**~~ — **WITHDRAWN 2026-08-04 by M5 (see T22).** The
   claim was that detecting them is nearly free because "if the minimal premise set requires a point
   named in no given and not in the goal, the puzzle demands that construction to solve". The premise is
   false as a matter of definition, not of yield: a point the derivation uses is *always* named by a
   given, because the construction that introduces it contributes its facts as premises. The test is
   the repo's own `langley_with_auxiliary` fixture — genuine auxiliary line, auxiliary point in the
   proof, detector reports empty. Auxiliary constructions return to a later phase, and what stays hard
   is unchanged and now the whole of it: *generating* figures rich enough (L4) and the hide/rediscover
   mechanism. AlphaGeometry harvested that signal from a pipeline that adds points during *search*;
   ours draws the entire construction for the player, so there is nothing left to rediscover.
3. **The top rung is no longer purely aspirational.** TongGeometry (Nature Machine Intelligence, Jan
   2026) demonstrated value-guided proposing at olympiad grade with three problems selected for real
   competitions. It is GPL, so ideas only (P2), but the architecture is published and doc 09 P5 commits
   to the shape of it rather than to its scale.

Full ladder: doc 01 §Difficulty ambition.

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
  *First eyeball check (Phase 2 M2, figures rendered on a phone): readable, and one concrete defect.*
  The §6.3 objective rewards spreading points apart but nothing penalises a single **outlier point
  dominating the bounding box** — an expert figure with a far-off `E` compresses the quadrilateral
  that carries the whole proof into about 40% of the frame. Every point is separated, and the figure
  is still bad. Fix belongs with M5's layout pass: score the *used* area, not the point spread.
- **O5 — Dedup misses semantic duplicates** — isomorphism hashing catches relabelings, not "same idea,
  different figure". Monitor via spot checks.
- **O6 — Upstream engine churn** — Newclid/AG2 release cadence may break adapters; pinned versions +
  contract tests + attrition-diff on upgrade are the guards.
- **O8 — LLM prose quality is unmeasured, and its failure mode is fluent** (opened 2026-08-04 with T17).
  The entity-level check catches a sentence naming the wrong points; it does not catch one that names the
  right points and misstates the *relation* between them. Guards: golden-text fixtures on every rule the
  template table already covers (a regression there is machine-detectable), the sampled prose column in
  the §5.1 spot check, and a pinned model version in bank provenance so a provider-side change shows up
  as a diff rather than as drift. Escalate to a second-model cross-check if spot checks find a
  misstatement.
  *Known defect this supersedes:* the template renderer emits ratios with a shared term — "From AD = BE
  it follows that AD : AE = BE : AE", 28 steps across 11 puzzles in the first bank — where a human writes
  AD = BE. `idioms.py` has unit-ratio collapsing and does not catch this shape. Worth one golden fixture
  so the LLM path is checked against it rather than inheriting it.
- ~~**O9 — The shortcut filter's cost and yield are both unknown**~~ (opened 2026-08-04 with T19).
  **CLOSED 2026-08-04 by M5, and not by answering it.** The filter cannot be built on this engine at all
  (doc 05 §5.2 filter 9), so it has neither cost nor yield. The risk it stood for did not go away — it
  moved to the unmitigated row of doc 04's risk table.


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


**T16 — `configuration` is stripped from shipped shards (settled Phase 2).** Doc 02 originally listed
only `reference_figure` and `provenance` as build-time blocks. `configuration` joins them: it is not
player-facing, a shipped shard cannot be independently re-derived once `reference_figure` is gone
anyway, and its bytes count against doc 06 §6.5's under-2-second budget. The auditable artifact is the
build archive, which is what `bank/validate.py` actually promises ("pointed at a bank file months
later") — reachable via `make bank-verify ARCHIVE=<path>`.


**T17 — Solution prose is rendered by an LLM, and the readable-step whitelist stops being a gate
(settled 2026-08-04; reverses L3 and doc 01 primary goal 3 as a *gate*).**

The whitelist was the wrong place to spend the difficulty budget. Requiring every step to be sayable
from a 19-entry table meant the pipeline shipped only proofs built from elementary theorems (L3). The
replacement: the engine's structured step — rule id, premises, conclusion, all canonical facts — is
rendered into a sentence by an LLM at build time, and **all 93 of Newclid's rules become shippable**.

Four conditions make this safe, and none is optional:

1. **The LLM renders; it never derives.** Identical in force to the numeric-layer rule (doc 02 invariant
   4). The model receives a fact-level step that is already proved and returns English. It never decides
   what is true, never chooses a step, never sees a goal it could answer.
2. **Nothing the LLM writes enters the correctness path.** `fact`, `derives`, `given[].fact`, `goal`,
   `answer`, `highlights`, and every difficulty field remain machine-generated (doc 02 invariant 5,
   tightened rather than relaxed). The LLM writes `text` and `display` and nothing else.
3. **Reproducibility is preserved by caching, not by determinism.** Doc 02 invariant 2 requires every
   artifact reproducible from `(generator_version, engine_version, seed)`, and a network call to a
   sampling model satisfies no such thing. So rendered prose is a **build-time artifact keyed by a hash
   of the structured step**, cached in-repo and committed with the bank. A bank rebuild at the same seed
   re-uses the cache and is byte-identical; re-rendering is a separate, reviewable commit that shows up
   as a prose diff. The determinism guarantee attaches to the bank, which is the thing that ships.
4. **Every rendered sentence is machine-checked before it is accepted.** The realistic failure is not
   gibberish, it is a fluent sentence asserting something the step does not. The check: the sentence must
   name exactly the point set of the step's premises and conclusion — no point the step does not
   involve, none of the points it does involve missing — and must contain no numeral absent from the
   step. Cheap, mechanical, and it catches the class of error that matters. A failed render retries,
   then falls back to the existing template if the rule has one, then discards the puzzle. Sampled human
   review on every bank build (doc 05 §5.1's spot check gains a prose column).

**Provider: Gemini 3.6 Flash on the free tier.** Chosen because rendering is a build-time batch job with
no latency requirement and a cache in front of it, which makes free-tier rate limits (per-project, not
published — check AI Studio) a throughput matter rather than a design constraint. The renderer is
therefore written resumable and idempotent from the start. **Recorded caveat:** free-tier content is used
by the provider to improve its products. What we send is a structured geometry step, not user data or
anything proprietary, so this is accepted — but it is a reason the renderer must never be handed
anything else, and a reason to revisit if the corpus ever becomes a competitive asset in itself.

The template table is **not deleted**. It stays as the fallback for the rules it already covers, as the
source of `tier` metadata for scoring (doc 05 §5.1), and as the golden-text fixture set that catches an
LLM regression. What it stops being is a gate.

Rejected alternative: keeping the whitelist and growing it to 93 entries by hand. That is ~74 templates
each needing prose, highlight builders, tests and review, to reach a place where an LLM is already
adequate — and it would still fail on the AR chains, which have no fixed shape to template.


**T18 — Angle values are rational multiples of π by engine construction; irrational answers come from
lengths and ratios (settled 2026-08-04).** A request for "weird" angle values like √3·π cannot be
satisfied and never will be by this engine family. `newclid.predicates.constant_angle.ConstantAngle`
types its value as a `Fraction`, and AR is exact rational arithmetic over angle atoms mod π; an
irrational angle has no representation, and admitting one would break the closure that makes DDAR sound.

Two things follow, and they are good news:
- **Non-round rational angles are free.** 7π/8 (157.5°) and 11π/17 cost exactly what 90° costs. The
  multiples-of-10 palette was `GENERATION.nice_angle_degrees`, our own config, and Stage 1 never even
  passed a band to it — so every angle in the first bank came from the *easy* palette regardless of the
  puzzle's band. That is a bug, not a limitation.
- ~~**Irrational values are already reachable through other quantity types.** Newclid ships `l2const`
  and `r2const` (`squared_constant_length`, `squared_constant_ratio`): |AB|² = 3 states |AB| = √3, and a
  squared ratio of 2 states a ratio of √2. So √2 and √3 answers need no new engine work — they need the
  `length`/`ratio` quantity types enabled (T7).~~
  **REVERSED 2026-08-04 by the M4a spike.** The predicates exist and can be *stated*; nothing *derives*
  them, and an answer has to be derived. No rule among the 93 concludes `l2const` or `r2const`, and AR
  does not produce them. Measured at seed 42, n=600: all 5 squared-constant facts appearing in 117
  saturating closures were assumptions at depth 0 — every one traceable to an `l2const`/`r2const`
  primitive in its own construction. Verified independently: the engine cannot even close a 3-4-5
  triangle. With `perp` and both legs pinned by `lconst`, the closure is 3 facts and `lconst bc = 5` is
  not derivable; Pythagoras (r57) routes entirely through `lconst` and never fires under Yuclid. So
  √2 and √3 answers need engine work after all — this bullet asserted a capability from the existence of
  a predicate, which is exactly the inference doc 08 §8.1.8 exists to forbid. See T21.


**T19 — Shortcut resistance is a correctness property, not a difficulty tweak (settled 2026-08-04).**
Doc 05 §5.1 scored the published proof's structure — depth, width, distinct rules, tier mix, branch
joins — on the assumption that a longer proof is a harder puzzle. Playtesting refuted it directly: an
expert-banded puzzle with a 9-step machine proof through two similar-triangle chains was solved by
inspection, because the figure is a square and the answer is half a right angle. Machine depth 9, human
depth 0.

The failure is not that the model is imprecise; it is **anti-correlated in the regime that matters**.
DDAR finds long mechanical chains precisely in the symmetric configurations a human sight-reads, so
"more steps" and "harder for a person" pull apart exactly where the expert band lives. Stage 6 minimizes
*premises* and has never had any notion of minimizing *route length*, so a short alternate route the
published proof never mentions costs nothing and is invisible.

~~Consequence: a **shortcut check** joins the hard filters (doc 05 §5.2 filter 9) rather than the score.
Re-solve the goal from the stated givens under a small step budget; if it lands, discard the puzzle
whatever its published proof looks like.~~ **The consequence did not survive M5: the check cannot be
built on this engine** (doc 05 §5.2 filter 9 for the four blockers; T22 for what it means). The
*reasoning* above is untouched and is why T19 is still the phase's most important entry — a puzzle with
a two-step solution is not "less hard", it is *mis-stated*. What changed is that we have no way to
detect the mis-statement, so it stands as an unmitigated risk (doc 04's risk table) rather than as a
solved problem. Do not read the strikethrough as "the concern was overblown"; read it as "we know the
concern is real and cannot yet act on it".

Cost: this will delete a large fraction of the current corpus, and that is the intended outcome. The
number is the deliverable of the milestone that lands it.


**T20 — Backward generation supersedes the no-feedback-loop rule (settled 2026-08-04; supersedes doc 05
§5.5's second anti-goal).** §5.5 forbade scorer→sampler feedback in v1, allowing only band targeting in
Stage 1, on the reasoning that a feedback loop would let the scorer optimize against itself and drift
away from human perception. That reasoning is sound and the rule is still the right default for the
*score*. It is the wrong rule for **generation direction**.

Forward generation — sample a random figure, deduce everything, keep whatever goal survives — is why
the first bank is what it is (L4). TongGeometry and AlphaGeometry's own data pipeline both run the other
way: search *backward* from a target configuration, propose the problem by traceback, prove it by
forward chaining. That is not a scorer feedback loop; the search is guided by a *proposer*, and the
scorer stays a downstream judge that the proposer cannot see.

The distinction that keeps §5.5's protection intact: **the interestingness model may guide the search;
the difficulty score may not.** Difficulty stays a measurement made after the fact, on a corpus the
difficulty weights had no hand in producing, so the calibration protocol (doc 05 §5.1) keeps meaning what
it says. Committing to the shape of this is doc 09 P5.

**T21 — Ratio and length are rule-limited, not palette-limited, so the quantity waves are blocked on the
rule set rather than on the QTR (settled 2026-08-04 by the M4a spike; supersedes the sequencing
assumption in T7 and doc 09 P5).** The spike asked whether registering `ratio` and `length` would widen
the answer space that T5 and T18 are about. Measured at seed 42, n=600 constructions, 117 realized:

| | ratio (`rconst`) | angle (`aconst`), post-M4 |
|---|---|---|
| Constructions yielding a novel goal | 9 / 117 | — |
| Distinct answer values | **3** — {2 ×9, ½ ×6, ⅓ ×2} | 9 |
| Modal answer share | **52.9%** | 36.0% |
| Clearing `min_proof_depth = 3` | **3 of 17** | — |

Verification is not the problem: ratio facts are *harvested from the saturating closure* rather than
proposed-then-verified, so they are symbolically derived before we ever see them and verify at 100%.
The answer space is the problem, and two interventions failed to move it:

- **Widening the value palette made it worse.** Stage 2 draws every ratio given from `{2/1, 3/1}`.
  Replacing that with ten mixed fractions ({3/2, 5/2, 5/3, 4/3, 7/3, 5/4, 7/4, 7/5, 8/5, 9/4}) gave
  **2** distinct derived values at **58.3%** modal share. Stated ratios do not propagate.
- **Biasing the sampler 25× toward the 16 ratio-creating primitives** (`midpoint`, `rconst`, `shift`,
  `on_line`, `eqratio`, …) produced 5× the ratio facts (17 → 86), **still 3 distinct values**, modal
  share **74.4%**, and **still exactly 3** clearing the depth floor.

The cause is the rule set. **Exactly one of the 93 rules concludes a ratio constant** — r51, "midpoint
splits in two", which always concludes ½. Everything else is AR *Ratio Chasing*, which is
**multiplicative only**: `an/ab = ¼` proves (½ × ½), while `nb/ab = ¾` does not, because that needs
additive segment arithmetic AR does not do. From a bag of halves you can only ever build powers of two.
So ratio's answer distribution is *worse* than the angle corpus M4 just fixed, on the same metric.

**Length is strictly worse than ratio, not better.** It derives only when a stated `lconst` pins the
scale (verified: `lconst ab = 8` ∧ `midp m a b` ⊢ `lconst am = 4`, depth 2), and its answer is then the
pinned length times a derivable ratio — the same answer space, scaled, plus a scale-pinning given that
Stage 6 must keep as a derivation leaf (T7).

**Area and arc length are not expressible at all.** The engine's predicate vocabulary is the 33 types
`FactKind` already mirrors; there is no area or arc predicate to state, let alone derive.

Decision: **`angle` stays the only registered quantity type.** Not because the QTR is wrong — the spike
confirmed the registry design works, the extractor is ~30 lines and the closure harvest is cheaper than
the propose-verify path angles use — but because registering a type whose answers are {2, ½} would make
the guessability problem worse while adding schema surface, frontend input modes, and a scale-pinning
obligation. The quantity waves move behind whichever of these lands first: a rule extension concluding
ratio constants from similar triangles (the natural source of non-dyadic ratios), or the area layer's
own decomposition arithmetic (doc 03 §3.7), which does not route through DDAR at all.

**T22 — Three of P3's four difficulty instruments cannot be built or do not inform, and the common
cause is the corpus (settled 2026-08-04 by M5).** P3 was ordered by "build the measurement before the
mechanism" (doc 09). Having built them, the measurements say the mechanism was never the problem.

| Instrument | Spec | Outcome |
|---|---|---|
| `requires_auxiliary` (§5.1a) | point the proof needs that no given names | **Identically zero.** Not a corpus fact — a definitional one |
| Shortcut filter 9 / `shortcut_margin` (§5.2, §5.1a) | re-solve under a 2-step budget | **Unaskable.** Four independent blockers |
| `unused_points` (M5's replacement) | drawn points the proof does not need | **Varies, but is not difficulty.** ρ = +0.777 with figure size, −0.05 to −0.15 with every difficulty feature |
| Answer-entropy cap, filter 8 | per-band share cap on one answer value | **Buildable and still needed.** The one survivor |

Details are in the docs that own each. What matters here is the pattern.

`requires_auxiliary` fails because **the pipeline draws the whole construction**. Every point is given
to the player, so no point is ever discovered; the literature's strongest difficulty multiplier has no
referent in a product built this way. The shortcut filter fails because **the engine has one
justification per fact and never derives a constant angle by forward search** — there is no second
route, and no way to bound the search for one. `unused_points` fails as a difficulty term because
**a figure with unused structure is a figure the sampler wandered through**, which is a fact about
Stage 1, not about the solver's task.

All three trace to the same place. The generator produces figures by random clause growth and then
asks, afterwards, whether anything hard came out; the instruments were built to detect hardness that
generation never had a reason to produce. Doc 07 L4 said the difficulty ceiling is the generator; M4
showed the sampler caused the answer monoculture; M4a showed the sampler's palette could not widen the
quantity space; M5 shows the difficulty *instruments* degenerate on sampler output. Four milestones,
one finding.

Consequence for sequencing (doc 09 P3/P5): **stop building difficulty measurements and rebuild
generation.** The remaining P3 items are kept only where they earn their place independently — filter 8
because guessability is measured and real, and the LLM renderer because it *adds* puzzles by retiring
the whitelist rather than removing them. The configuration table is promoted, not dropped: with filter 9
dead it is the only remaining mechanism aimed at the sight-read failure.

What this does **not** license is lowering a cut to fake a band (T10) or reading "the instrument is
uninformative" as "the puzzles are fine". The playtest that opened this phase still stands.
