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

## P3 — Difficulty rebuild (**next**)

The phase this roadmap was resequenced to create. Ordered so each milestone produces the measurement
that justifies the next.

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

**M4a — Ratio and length spike (next).** Add goal extractors for `ratio` and `length` over the closures
Stage 4 already computes, and report verification rate, yield per construction, and answer distribution
per type. Rationale: the closure is the expensive part and we harvest one quantity type from it, so this
may *raise* yield rather than cost it — and every gate built after this should be tuned against the real
quantity mix, not against an angle-only corpus. Decide the mix from the spike, not from argument.

**M5 — Auxiliary-construction detection.** Surface `requires_auxiliary` from the traceback we already
build (doc 04 Stage 6), score it (doc 05 §5.1a), report it per band.
**AC:** the rate is measured on the current corpus. If it is ~0, that is a finding about the sampler
(doc 07 L4) and feeds P5 — not a failure of the milestone.

**M6 — LLM step rendering.** Retire the whitelist gate; Gemini 3.6 Flash free tier; content-keyed cache
committed with the bank; entity-level fidelity check; golden fixtures over every templated rule; tiers
assigned for all 93 rules (doc 03 §3.5a, doc 05 §5.1, doc 07 T17).
**AC:** all 93 rules shippable; the seed-42 corpus rebuilds byte-identical from cache with zero network
calls; fidelity check tested from both sides; sampled prose review clean; puzzles previously discarded
for over-budget AR chains now ship.

**M7 — Quantity waves: ratio and length.** Register both (doc 04 §QTR); goal extractors over
`rconst`/`r2const` and `lconst`/`l2const`; scale-pinning givens; fraction and decimal answer input
(doc 06 §6.2); tolerance-collision check.
**AC:** mixed banks across all bands; ≥ 1 irrational answer per band via the squared predicates
(doc 07 T18); angle banks rebuild byte-identical (regression); tolerance-collision check clean.

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
- **Interestingness proposer**: a learned value model guiding the search, trained against real
  competition problems (IMO-AG-30, JGEX-AG-231, MO-TG-225). The difficulty score stays a downstream
  judge the proposer cannot see — doc 07 T20's line.
- **Auxiliary-construction hiding**: generate *with* the aux element (Newclid agent heuristics, then an
  LLM proposer through the same API, engine-verified), hide it, design the rediscovery hint UX.
  *Detection* already landed in P3 M5; this is the hard half.

**AC:** expert band populated at target volume from figures containing genuine auxiliary points;
degeneracy attrition materially below the measured 86%; hidden-construction hint UX validated by
dogfooding.

## P6 — Areas

Design doc first (required by doc 03 §3.7), and it must **choose between two architectures** before any
code: (a) the verified decomposition layer — target region split into triangles whose sides/angles are
engine-certified, exact symbolic area arithmetic (SymPy) as decomposition steps; or (b) adopting the
Chou–Gao–Zhang **area method** as a second SAL backend, which proves area/ratio/length statements
natively and produces short readable proofs, at the cost of a second engine to own. Either way:
`regions` figure schema + shading UX (doc 06).
**AC:** shaded-area puzzles pass all existing gates including cross-engine re-certification of every
underlying fact; decomposition steps pass the prose-fidelity check.

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
- *"Quantity waves follow engine support"* sequenced by cost when it should have sequenced by necessity.
  Ratio and length were cheap all along — `r2const` and `l2const` were sitting in Newclid the whole time
  (doc 07 T18) — and angle-only turned out not to be a viable product at all, because on a to-scale
  figure every angle answer is eyeball-readable (doc 07 T5).

The replacement principle, which is what P3 is ordered by: **build the measurement before the mechanism.**
The shortcut filter and answer-entropy cap come first not because they add value on their own — they
subtract, and will shrink the bank sharply — but because without them there is no way to tell whether
anything built afterwards worked. The same logic defers dedupe, anti-leak and parallelism to P4: each
multiplies a corpus, and multiplying an invalid corpus produces a larger invalid corpus and a confident
report saying so.
