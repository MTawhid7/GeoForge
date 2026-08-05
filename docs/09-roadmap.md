# 09 — Roadmap

Ordered so an end-to-end pipeline exists as early as possible; every phase ships something runnable and
each has acceptance criteria (AC). Phase 0 is a **decision gate**: it can still send us back to a hybrid
design if trace readability disappoints.

> **Resequenced 2026-08-04.** The first playable bank was measured and rejected (doc 01 §Vision), and
> the remaining P2 work — dedupe, anti-leak layout, parallel builds, CI — all *industrialises* a bank
> whose contents are wrong. Building 2,000 of a puzzle nobody should ship is worse than building 98.
> So that tail is deferred and a new **P3 — Difficulty rebuild** takes its place, followed by
> **P4 — Bank industrialisation** (the deferred tail, unchanged in content) and **P5 — Backward
> generation**. Governing decisions: doc 07 T5, T7, T10, T17, T18, T19, T20, L3, L4.
>
> One ordering principle drives the whole resequence: **the measurement instrument comes first.**
> Until the shortcut filter and answer-entropy cap exist, we cannot tell a genuinely hard puzzle from a
> long-proof-obvious-answer one, so every downstream investment would be tuned blind.

## P0 — Feasibility spikes (≈ 2–3 weeks) · decision gate

- ~~License check~~ **resolved**: `newclid`, `yuclid`, `ncdgen`, AG2 DDAR all verified Apache-2.0 in the
  reference clones (doc 07 P2).
- **S1 Solve spike:** run Newclid and AG2 DDAR on ~20 hand-written Euclidea-style angle-chase problems
  (JGEX). Measure solve rate, wall time, and trace quality.
- **S2 Readability spike (the gate):** hand-translate 10 engine traces into player steps; estimate
  whitelist coverage and AR-chain lengths (doc 03 §3.5). Include 2–3 length/ratio traces (similar
  triangles, Pythagoras) to price the wave-2 template family early — informational, not a gate.
- **S3 Generation spike:** adapt `ncdgen`'s loop: sample → closure → enumerate numeric-valued goals →
  traceback. Confirm quantity-goal extraction and seed determinism through the engine.
- **AC / gate:** ≥ 80% of S2 traces translate with bounded effort ⇒ proceed. Below that ⇒ adopt the
  hybrid fallback (engine finds truths; a thin custom presentation layer re-derives display paths) and
  record it in doc 07 before Phase 1.

## P1 — Generator MVP — **DONE** (M0–M6, incl. cross-engine validation pulled forward from P2)

SAL with `newclid` backend + contract tests; typed construction layer over JGEX; sampler (adapted
`ncdgen`); Stages 1–9 of doc 04 incl. configuration facts, readability gate, well-posedness;
attrition report per stage/band.
**AC:** fixed seed ⇒ byte-identical batch; 100 validated puzzles across ≥ 2 bands; every puzzle's
solution readable per gate; zero soundness failures in a 1,000-construction run (failures found = bugs
fixed, rerun clean).

**Measured, 1,200 constructions at seed 42**
(`uv run python -m geoforge.generator.batch --n 1200 --seed 42 --report --out run.json`):

| Criterion | Result |
|---|---|
| Fixed seed ⇒ byte-identical batch | **Pass.** Identical puzzle payloads across two runs under different `PYTHONHASHSEED` (0 and 99991) — the weaker same-process check would have missed BUG-4 |
| ≥ 100 validated puzzles across ≥ 2 bands | **Pass.** 129 puzzles across 4 bands: easy 70, medium 5, hard 52, expert 2 |
| Every solution passes the readability gate | **Pass.** Enforced structurally (Stage 7 discards otherwise); re-validated independently from the emitted JSON — 0 violations over 129 puzzles, solution length 1–13 steps, median 4 |
| Zero soundness failures in ≥ 1,000 constructions | **Pass.** 0. Run exits non-zero if any is found |

Attrition: degeneracy 1035, extraction 645 (401 too-shallow, 239 surplus), translation 16 (all
over-budget AR chains), well-posedness 20. Throughput ≈ 79 s for 1,200 constructions.
Four rules were added to the whitelist from this run's discard log (r11, r19, r54, r77), which is
what the discard log is for; unknown-rule discards then went to zero.

**M6 — cross-engine validation** (`--validate`, doc 04 §V). Every emitted puzzle is re-derived from
its own JSON by the vendored AG2 DDAR, an uncorrelated codebase. Measured on the same run:

| Check | Result |
|---|---|
| Independent re-derivation | **129/129**, zero disagreements, 2.1 s total (16 ms/puzzle) |
| Mutation: goal value and answer shifted 1° | **129/129 rejected** |
| Mutation: published answer alone made to lie | **129/129 rejected** |
| Mutation: any single given dropped | **441/441 rejected** — a second engine independently confirming Stage 6 minimality |
| Angle-convention calibration | Uncalibrated, **25/129** validate — exactly the 25 answering 90°, the one angle equal to its own supplement (doc 03 §3.2a) |

The run exits non-zero on any disagreement. One real gap surfaced at full scale and was fixed: a
single puzzle carried a `contri` premise, which the exporter refused (loudly, as designed) rather
than skipping — congruent and similar triangles now expand to their SSS content.

## P2 — Product bank + frontend — **PARTIALLY DONE, tail deferred to P4**

**Done (M1–M3):** schema v2 + generated TS types with a CI drift check; display layout and the dev bank
builder; frontend v1 (renderer, player, hints, replay, home/daily/practice/settings, localStorage
stats) per doc 06; the doc 05 scorer, hard filters, and interestingness ranking.

**Outcome — the measurement that reset the roadmap.** A 98-puzzle bank, rendered and played on a phone:

| Measured | Result |
|---|---|
| Answer distribution | **45° × 71, 90° × 15**, 30° × 9, 135° × 2, 120° × 1 — guessing the mode beats the app 72% of the time |
| Circles in any figure | **0 of 98**, despite `circle_step_weight = 2.0` |
| Figure size | 4 or 5 points in 82% of puzzles |
| Distinct solution shapes, easy band | **2**, across 56 puzzles |
| Playtest | *expert* and *hard* puzzles solved by inspection (doc 07 T19) |
| Attrition | 86% degeneracy (344 of 546 at seed 42) — the sampler is the bottleneck (doc 07 L4) |

**Deferred to P4:** isomorphism dedupe, anti-leak layout, parallel seed-sharded generation, the full
bank builder, CI. All four make a bank *bigger, cleaner and faster to produce*; none makes it *good*,
and running dedupe on the corpus above would correctly collapse the easy band to two puzzles.

## P3 — Difficulty rebuild (**in progress; resequenced after M5**)

The phase this roadmap was resequenced to create. Ordered so each milestone produces the measurement
that justifies the next — which worked, and what it justified was cutting the phase short.

**Resequenced 2026-08-04, after M4, M4a and M5 (doc 07 T22).** The ordering principle was "build the
measurement before the mechanism". Three milestones in, the measurements agree on something the plan did
not anticipate: **the instruments degenerate on this corpus because generation is the problem, and no
further instrument will say anything new.**

| Milestone | What it was to measure | What it found |
|---|---|---|
| M4 | answer distribution after fixing the sampler | modal share 71.8% → 36.0%; **the cause was Stage 1 all along** |
| M4a | whether ratio/length widen the answer space | they narrow it; one rule of 93 derives a ratio constant |
| M5 | the auxiliary-construction rate | identically zero by definition; the shortcut filter unbuildable; the replacement feature anti-correlated with difficulty |

Four separate difficulty signals, four dead ends, one cause — doc 07 L4. So the remaining P3 work is cut
to the items that earn their place *without* assuming a better corpus, and the generator rebuild (P5)
is promoted to the critical path:

- **Kept — M6, the answer-entropy cap (filter 8).** Guessability is measured, real, and independent of
  how figures are generated. It is now the only surviving hard gate from the difficulty rebuild.
- **Kept and promoted — the configuration table.** It was a nice-to-have while filter 9 was expected to
  carry the sight-read failure. Filter 9 is dead, so this is the *only* remaining mechanism aimed at
  that failure, and doc 04's risk table lists the risk as unmitigated until it lands.
- **Kept — M7, LLM step rendering.** The one item that *adds* puzzles rather than removing them: it
  retires the whitelist gate over 74 untemplated rules, which raises both yield and the difficulty
  ceiling. On a corpus yielding 9 puzzles per 1,500 constructions, that matters more than another gate.
- **Dropped from P3 — layout anti-alignment.** Real but cosmetic beside a yield problem this size;
  it moves to P4 with the rest of the presentation work.
- **Promoted — P5.** Everything above is downstream of a sampler that grows clauses at random and
  discards 86% as degenerate. Start it as soon as M6 and M7 land.

The honest framing: P3 set out to *measure* difficulty and instead established that this generator
cannot produce enough of it to measure. That is a successful phase with an unwelcome result, and the
response is to fix generation — not to keep building instruments, and not to lower a cut (doc 07 T10).

**M4 — Sampler bias, band plumbing, and the sight-readable rejection — DONE.** Measured at seed 42:

| | before | after |
|---|---|---|
| Answers (n=3000) | 45°×117, 90°×22, 30°×9 | 30°×9, 72°×4, 60°×3, 36°×2, 55°×2, 40°×2, 50°, 70°, 63° |
| Modal answer share | **71.8%** | **36.0%** |
| Figures with a circle | 0 of 98 | 10 of 25 |
| Primitives flagged `introduces_circle` | 37 of 87 | 3 of 87 |
| Yield | 5.43% | 0.83% |
| Throughput | — | 29.9 constructions/s ⇒ 2,000 puzzles ≈ 25 min at 6 workers |

Four defects, three of them invisible until something else was fixed:
1. **`_CIRCLE_KEYWORDS` included `cong`** — how JGEX spells a circle *and* every square, parallelogram
   and isosceles triangle. The 2× "circle bias" was a 2× bias toward symmetry generators.
2. **The band never reached `sample_construction`**, so every construction drew from the easy palette.
3. **Almost nothing stated an angle** (2 of 22), so the palette governed 9% of the corpus — fixed with
   `angle_weight`, and the rest by rejecting the answers a player reads off the figure (doc 07 T5).
4. **`emit.frame` applied a reflection**, silently breaking any `aconst` given that was not 90° — the
   same signature as doc 03 §3.2a. Now a half-turn; pinned by `tests/generator/test_frame.py`.

Determinism holds: byte-identical batch across `PYTHONHASHSEED` 0 and 99991.

*Deferred out of M4 and into M5, having been measured as unimplementable or better placed there:* the
shortcut check (doc 07 T19 — the engine cannot be asked, see below) and the answer-entropy cap.

**M4a — Ratio and length spike. DONE 2026-08-04. Outcome: do not register either type; the quantity
waves are deferred behind a rule-set change (doc 07 T21).** The spike harvested `rconst`/`lconst` from
the closures Stage 4 already computes and measured verification rate, yield, depth and answer
distribution per type at seed 42, n=600 (117 realized figures).

| | ratio | angle, post-M4 |
|---|---|---|
| Constructions yielding a novel goal | 9 / 117 | — |
| Verification rate | 17 / 17 (harvested, so already derived) | — |
| Distinct answer values | **3** — {2, ½, ⅓} | 9 |
| Modal answer share | **52.9%** | 36.0% |
| Clearing `min_proof_depth = 3` | **3 of 17** | — |

The hypothesis was right about cost and wrong about value. Harvesting from the closure *is* cheaper than
the propose-then-verify path angles use — no speculative engine call per candidate — but the answer
space is {2, ½} plus whatever a construction states outright, and that is **more** guessable than the
corpus M4 just fixed. Two attempted fixes both failed: widening the given-value palette from `{2/1, 3/1}`
to ten mixed fractions dropped it to 2 distinct values at 58.3% modal, and biasing the sampler 25× toward
the 16 ratio-creating primitives produced 5× the ratio facts with **the same 3 values** at 74.4% modal
and still exactly 3 clearing the depth floor. Cause: one rule of 93 concludes a ratio constant (r51,
midpoint, always ½) and AR ratio chasing is multiplicative-only, so the reachable set is powers of two.
Length derives only behind a scale-pinning given and lands in the same space, scaled. Full numbers and
the reasoning in doc 07 T21.

Two things fell out that were not the question. **Doc 07 T18's second bullet is reversed**: no rule
concludes `l2const` or `r2const`, so √2 and √3 answers are *not* free — all 5 squared constants in 117
closures were assumptions, and Pythagoras (r57) never fires under Yuclid even with both legs of a 3-4-5
triangle pinned. And a **SAL adapter defect**: `_value_of` probed attribute names, so `l2const`/`r2const`
came back with the value stranded in `args` and `value=None` — a fact id (`l2const:a:b:9/1`) that
`fact_from_id` rejects outright, breaking the premise-vs-derived id agreement `_fact_from_construction`
documents. Fixed with a kind-keyed table asserted exhaustive over `VALUED_KINDS`, and every one of the
five kinds pinned by a behavioural test (writing the table by inspection got `rconst` wrong first try:
its Fraction is in `value`, while `ratio` holds the segments).

**M5 — Auxiliary-construction detection. DONE 2026-08-04. Outcome: not built; the metric is
definitionally zero, the shortcut filter it shared a stage with is unbuildable, and the replacement
feature ships unscored (doc 07 T22).** The AC allowed for a zero rate as a finding about the sampler.
The rate is zero, but not for the reason the AC anticipated — it is zero *by construction*, so it is a
finding about the definition first and about the sampler second.

Measured at seed 42:

| | |
|---|---|
| `subdag.points() - needed_points()` non-empty | **0 / 163** puzzles, every band |
| Containment (`subdag.points()` ⊆ its own leaves) | holds 61 / 61 |
| Tautology naming an otherwise-unmentioned point | 0 |
| `langley_with_auxiliary` fixture — genuine auxiliary line | reports **EMPTY** |
| Published solution naming an undrawn point | 0 (no latent shipping defect) |

The fixture is the decisive one. Its auxiliary point `d` is in the proof and essential to it, and the
detector does not see it, because `d` is named by the premise `aconst:a:c:a:d=1/9`. Any constructed
point becomes a stated given the moment the proof uses it — so the metric is blind to exactly what it is
named for, and no sampler change could ever make it fire. Doc 07 T10's "detecting them is nearly free"
and L1's 2026-08-04 amendment are both withdrawn.

**Shipped instead — `unused_points`, recorded and deliberately unscored.** Drawn points the derivation
does not need. It varies where its predecessor could not (0–5, mean 1.58, only 34% at zero), because
`prune_figure` closes construction dependencies transitively. It gets **no weight**, and that was
decided by measurement rather than caution: ρ = **+0.777** against figure size, and −0.048 / −0.110 /
−0.140 / −0.147 / −0.096 against depth, width, distinct_rules, branch_join and the score. Mean unused is
1.80 in easy and 2.11 in hard but 0.00 in expert. Weighting it positively would score big rambling
figures as hard — doc 07 T19's mistake, repeated. It is reported per band under `sampler_diagnostics`
as evidence about Stage 1, which is what it actually measures. A test asserts it stays out of
`SCORING.weights`, so weighting it later forces a re-measure.

**Also settled here, because M5 owned the stage it lived in: doc 05 §5.2 filter 9 cannot be built.**
Four independent blockers, the strongest of them measured in M4a — a saturating closure over the stated
givens yields 181 `aconst` facts of which **0 are novel**, so a bounded forward re-solve returns "no
shortcut" for every angle puzzle regardless of difficulty. `shortcut_margin` goes with it, doc 07 O9
closes, and doc 04's risk table now carries "goal solvable in two steps" as **unmitigated**.

**M6 — Generation rebuild: configuration seeding and the rescoped degeneracy check. IN PROGRESS
2026-08-05.** Promoted ahead of the gates below, because the M5 resequence said generation is the
binding constraint and two measurements then showed the fix is far cheaper than P5 assumed.

*Adopted, with the measurement that justified each:*

1. **Rescope the degeneracy check** (doc 07 T23). It rejected a whole figure for any one flat triple
   among C(n,3) — combinatorial in point count, so hardest on the richest figures. Ground truth: it
   refused 52% of JGEX and **85% of IMO** configurations, which are correct by definition, and 14 of the
   20 seeded constructions that yielded a goal. Whole-figure checks stay at Stage 3; the per-triple test
   becomes data, acted on at Stage 5 where the goal is known.
2. **Seed Stage 1 from the human configuration library** (doc 07 T24). 635 competition problems in the
   reference clones, in our own JGEX syntax, realizing at ~100%. Decorated with Stage 2 givens: **33%
   of skeletons yield a goal against clause growth's 5.4%, 25 distinct answers against 9, 11.1% modal
   share against 36.0%,** depths spread 3–9 instead of piled at 4.
3. **Difficulty ground truth** (doc 05 §5.1c): 404 olympiad vs 231 textbook skeletons — an external
   hard/routine label. It cannot rank a puzzle; it can refute a scorer, which is the first automatable
   claim about difficulty this project has had.
4. **Promote the LLM oracle to a first-class difficulty signal** (doc 07 T25). Deferred to M7 with the
   renderer, since both need the same cached-call infrastructure.
5. **Keep filter 8 and the renderer; drop the learned value model** from near-term P5 — the library
   supplies the configuration richness the value model was meant to search for.

**AC:** end-to-end yield, answer entropy and band coverage at seed 42, committed, against the M5
baseline; determinism unchanged; a build without the reference clones still produces puzzles.

**M6b — Answer-entropy cap and the configuration table.** The two selection-time gates, unchanged in
intent by the resequence and now tuned against a corpus worth tuning against.
- *Filter 8*, bank-level, between `interest.select(...)` and the layout loop so the surplus dropped is
  the least interesting; `BuildReport.dropped_by_entropy` beside `dropped_by_interest`; config
  `max_answer_share`, `min_band_size_for_share`.
- *Configuration table* (`scoring/configurations.py`), matched over the **stated givens** rather than
  construction names — a name whitelist matched 98 of 98 first-bank puzzles and the catalogue has no
  `rhombus` primitive at all, so the named failures are emergent. Patterns must be **generated from a
  real engine solve, never hand-written**: `aconst` is a directed line-to-line angle mod π and `cong`
  canonicalization is thin enough that BUG-4 exists.
**AC:** both fire on the seed-42 corpus with a committed rate; every pattern has a negative fixture; the
discard reason names the pattern so attrition reads as a priority queue.

**M7 — LLM step rendering.** Retire the whitelist gate; Gemini 3.6 Flash free tier; content-keyed cache
committed with the bank; entity-level fidelity check; golden fixtures over every templated rule; tiers
assigned for all 93 rules (doc 03 §3.5a, doc 05 §5.1, doc 07 T17). **Promoted in the resequence for a
reason worth stating: it is the only remaining item that raises yield rather than cutting it.**
**AC:** all 93 rules shippable; the seed-42 corpus rebuilds byte-identical from cache with zero network
calls; fidelity check tested from both sides; sampled prose review clean; puzzles previously discarded
for over-budget AR chains now ship — reported as a yield delta, since that is the point.

**M7 — Quantity waves: ratio and length. BLOCKED by M4a's measurement (doc 07 T21); moved out of P3.**
Registering the types is the cheap part and the spike showed it does not buy what this milestone was for
— the reachable answer set is {2, ½} because one rule of 93 concludes a ratio constant and AR chases
ratios multiplicatively. The acceptance criterion "≥ 1 irrational answer per band via the squared
predicates" is **unsatisfiable as written**: nothing derives `l2const` or `r2const` (doc 07 T18, reversed).

Unblocked by either of two things, neither of them this milestone's to build:
- a rule concluding ratio constants from similar triangles, which is where non-dyadic ratios would come
  from — an engine-side change, and doc 07 P2 forbids the GPL route to one;
- the area layer's own decomposition arithmetic (doc 03 §3.7), which does not route through DDAR and so
  is not subject to this limit at all.

Revisit when one lands. The QTR itself needs no change — that much the spike did confirm.

## P4 — Bank industrialisation (the deferred P2 tail)

Isomorphism dedupe; anti-leak layout (doc 06 §6.3); parallel seed-sharded generation with band-targeted
profiles; target-driven bank builder; GitHub Actions CI with a smoke bank. Content unchanged from the
original P2 plan — only the position moved, because these multiply a corpus rather than improve one.
**AC:** `make bank` ⇒ ≥ 2,000 validated puzzles with per-band floors; mutation tests all caught;
20-figure layout spot check clean; e2e happy path green; first-puzzle-interactive < 2 s on a mid-range
phone; owner solves 10 puzzles on a phone without UX blockers.

## v1.0 — Public release

Dogfooding pass (owner solves ≥ 100 across bands), difficulty weight calibration from those spot checks,
PWA niceties, deploy to static host.
**AC:** doc 01 success criteria measured and met or explicitly re-scoped in doc 07.

## P5 — Generation rebuild: configuration seeding and backward search

The response to doc 07 L4 — the sampler, not the translator or the scorer, is what caps puzzle quality.

- **Configuration archetypes** (doc 04 Stage 1 item 2): a reviewed library of figure archetypes
  instantiated and then decorated, replacing pure clause growth. Expected to fix the degeneracy rate as
  a side effect.
- **Backward generation** (doc 07 T20): search from a target configuration, traceback to propose,
  forward-chain to prove — the TongGeometry and AlphaGeometry data-pipeline shape. Ideas only; that
  code is GPL (doc 07 P2).
- ~~**Interestingness proposer**: a learned value model guiding the search, trained against real
  competition problems (IMO-AG-30, JGEX-AG-231, MO-TG-225).~~ **Dropped from the near term 2026-08-05
  (doc 07 T24).** The datasets it was to be *trained on* turned out to be directly usable as the
  configuration library itself, which supplies the richness the value model was meant to search for at
  none of the cost. Revisit only if seeded output plateaus and the plateau is measured — a learned
  proposer is justified by a ceiling we have hit, not by one we anticipate. T20's line still holds
  whenever it returns: the difficulty score stays a downstream judge the proposer cannot see.
- **Auxiliary-construction hiding**: generate *with* the aux element (Newclid agent heuristics, then an
  LLM proposer through the same API, engine-verified), hide it, design the rediscovery hint UX.
  ~~*Detection* already landed in P3 M5; this is the hard half.~~ **Corrected by M5: there is no
  detection half.** A point the proof uses is always named by a given, so nothing is detectable until
  something is hidden — hiding *creates* the signal rather than exposing one (doc 07 T22, L1). This
  bullet is therefore the whole of the auxiliary work, not the second half of it.

  **AMENDED 2026-08-05 by the T26 measurements — the hiding mechanism is built and works, and the
  problem moved.** `ncdgen`'s setup/aux split, run over GeoForge output, is non-empty and
  ablation-confirmed on real puzzles (best case: two withheld points, depth 19, a 46° answer). So the
  mechanism is no longer the open question. **The rate is:** ≈1.8% of extracted goals, and four levers
  — bigger figures, heuristic enrichment, adding-a-point-and-measuring-the-delta, and decoration
  sparsity — were each measured and none moved it. Cause: our figures are metrically saturated (76.6%
  of true prove-facts and 97.7% of angle goals are already derivable), so an auxiliary point has
  nothing to unlock. Full table in doc 07 T26; do not re-propose those four.

**AC:** expert band populated at target volume from figures containing genuine auxiliary points;
degeneracy attrition materially below the measured 86%; hidden-construction hint UX validated by
dogfooding.

### P5 open directions (2026-08-05) — ordered by evidence, not by appeal

Everything cheap has been tried. What is left, in the order the measurements justify:

1. ~~**Change the source: seed from `imo_102_requires_aux.txt`.**~~ **MEASURED AND REFUTED
   2026-08-05: 0/117 goals, against 3/170 (1.8%) for the rest of the library.** Those 101 problems
   need a construction for *their own* prove-goal; discard that goal and ask an angle-value question
   instead and the aux requirement does not transfer. Keep them out of seeding.

   What survives from this line: aux-yielding really is a property of particular configurations —
   every confirmed case traces to `imo_sl_2008_g3` or `imo_sl_2011_g5`, at proof depth 18–19. A
   **ranked table of per-configuration aux yield** over the whole 635 is still worth building, but
   as a bias for Stage 1b, not as a new dataset.
2. **Coordinate-coincidence aux proposal** (doc 07 T27, GenesisGeo). The one proposal method not yet
   tried: candidates are points where lines and circles spanned by existing points *happen* to meet,
   carrying several incidences at once, rather than mechanical midpoints and feet. Whether it survives
   the saturation problem is unknown — the delta experiment says any point unlocks nothing in a fat
   closure — so test it on sparse figures, not on decorated ones.
3. **Mine GenesisGeo's released dataset** (21.8M problems, >3M with auxiliary constructions,
   Apache-2.0). Not yet examined. This is the only route that does not require us to *manufacture* the
   property.
4. **Accept ~2% and industrialise it.** ~80 aux puzzles/hour single-threaded is ~25 CPU-hours for a
   2,000-puzzle bank, which is a normal offline build. If the rate cannot be raised, the honest move is
   to filter for aux and pay the compute rather than keep hunting for a lever.

**The strategic alternative, which does not depend on any of the above:** the quantity layer (P6). It
is the only change that alters what a GeoForge puzzle can *ask*, and it is independent of the aux
problem. See P6.

## P6 — Areas — **design done 2026-08-05 (`docs/10-area-layer.md`); PROMOTED**

~~Design doc first (required by doc 03 §3.7), and it must **choose between two architectures** before
any code.~~ **Written, and the choice is made:** (a) the verified decomposition layer is the build;
(b) the Chou–Gao–Zhang area method stays a candidate to be judged against A2's measured results rather
than ahead of them, because it is a second engine to own.

**Promoted ahead of the remaining P5 auxiliary-construction work**, on evidence rather than appeal.
P3 and P5 have spent four milestones on proof *structure* and the ceiling is measured: aux is real but
capped at ~1.8% of goals with five levers tried and none moving it (doc 07 T26), and `aconst` is
**0-derived** so every angle puzzle is a chase from stated angles. **No rung of doc 01's ladder changes
what a puzzle can ask.** The area layer is the only planned work that does, and it is independent of
the aux problem.

Feasibility is spiked, not assumed: the engine certifies `aconst` and two `lconst` on one triangle, the
layer computes √3, and shoelace confirms it (doc 10 §10.4). Build order, kill conditions and the
directed-angle hazard that shapes the primitive set are all in doc 10.

**AC:** unchanged and still binding — shaded-area puzzles pass all existing gates including cross-engine
re-certification of every underlying *engine* fact; decomposition steps pass the prose-fidelity check.
Added by doc 10: ≥1 irrational answer per band, modal answer share below angle's 36.0%, and an
independent second route re-checking every emitted area — the cross-engine validator cannot see layer
arithmetic (doc 10 §10.8), which is the one genuinely new blind spot this work introduces.

## P7 — Formal tier & platform seed (ongoing)

- LeanGeo export + machine-checked certificates for featured puzzles ("formally verified" badge).
- Second-domain pilot (algebra, SymPy-verified generation) reusing the bank/difficulty/product spine —
  the test of the universal-platform thesis at minimal cost.
- Watch list: Seed-Geometry code release (drop-in SAL backend candidate); LeanGeo growth; new AG-lineage
  releases.

## Sequencing rationale

Readability risk is retired first because it's the only pivot-specific unknown that could invalidate the
architecture (P0 gate). Correctness gates precede volume (P1 before P2) because every later feature
multiplies the cost of a soundness bug. Layout precedes frontend polish because the frontend contract is
"render finished JSON". The registry (doc 04 §QTR) exists from P1, so no quantity wave requires touching
core pipeline code.

**Amended 2026-08-04.** Two of the original rationales were wrong, and both were wrong in the same way —
they assumed a property instead of measuring it.

- *"Readability risk is retired first"* retired the wrong risk. P0 measured whether traces **could** be
  translated and got a reassuring 82%. It never asked what requiring translation would **cost**, and the
  answer was the difficulty ceiling of the entire product (doc 07 L3): a puzzle ships only if built from
  the theorems we can pronounce, so the pipeline selected for elementary proofs and the discard log that
  was supposed to drive coverage stayed empty because nothing hard ever got far enough to fail.
- *"Quantity waves follow engine support"* sequenced by cost when it should have sequenced by necessity
  — and then the correction made the same mistake in the other direction. Angle-only really is not a
  viable product, because on a to-scale figure every angle answer is eyeball-readable (doc 07 T5). But
  "ratio and length were cheap all along, `r2const` and `l2const` were sitting in Newclid the whole
  time" reasoned from a *predicate's existence* to a *capability*, without asking what derives it. M4a
  asked: one rule of 93 concludes a ratio constant, nothing concludes a squared one, and the reachable
  ratio answers are {2, ½} — a corpus more guessable than the angle one it was meant to fix (doc 07
  T21). Both revisions of this bullet were written from the engine's vocabulary rather than from its
  output; the entry below is what should have been applied to both.

The replacement principle, which is what P3 is ordered by: **build the measurement before the mechanism.**
The shortcut filter and answer-entropy cap come first not because they add value on their own — they
subtract, and will shrink the bank sharply — but because without them there is no way to tell whether
anything built afterwards worked. The same logic defers dedupe, anti-leak and parallelism to P4: each
multiplies a corpus, and multiplying an invalid corpus produces a larger invalid corpus and a confident
report saying so.
