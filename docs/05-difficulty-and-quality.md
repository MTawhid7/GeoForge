# 05 — Difficulty and Quality

Generated puzzles are worthless if trivial or ugly. This module scores every candidate and rejects most.
All constants live in `config/` (shared with doc 04 Stage 5 — one source) and are retuned against
spot-check data; the *feature structure* below is the stable contract, the weights are not.

## 5.1 Difficulty score

Input: the minimal translated solution sub-DAG. All features are quantity-generic (they read DAG
structure and rule/template metadata, never quantity kinds); weights may be calibrated per quantity type
once more than one is enabled.

Features:
- `depth` — longest premise→goal chain (primary).
- `width` — total rule applications. **Machine steps of the sub-DAG** (settled Phase 2 M3): difficulty
  must read proof structure, not a presentation decision, and idiom collapsing turns three machine
  steps into one sentence. `published_steps` is recorded alongside so calibration can test the other
  reading without a code change.
- `distinct_rules` — conceptual variety (five uses of triangle-angle-sum is easy even at depth 5).
- `tier_max`, `tier_mix` — rule families used (circle theorems feel harder than supplementary angles);
  tiers are assigned in our translation whitelist, not by the engine. The whitelist is not the whole
  table: `combine` and `restate` are named by premise count on the algebraic path and have no engine
  rule id, so they carry tiers in `AR_TEMPLATES`. `combine` appears in **every** puzzle the pipeline
  currently makes, so a tier table that missed it would score most of every solution as tier 0.
- `branch_join` — DAG joins of independent sub-deductions (strongly felt as "hard"). Counts steps
  resting on two or more *derived* facts; a step resting on two givens is one idea, not a join.
- `nice_penalty` — subtractive. **Two of three components ship** (Phase 2 M3): *answer telegraphed by
  a given* and *round values everywhere*. *Symmetric freebies* does not: deciding a figure is
  symmetric and that its answer follows from the symmetry needs the graph canonicalization M4 builds
  for dedupe, and a weaker guess would put an unjustifiable number into a published difficulty.

Score = weighted sum normalized 0–10 (initial weights in `config/`, including `nice_penalty`'s).
Each feature is normalized over a **useful range**, not its arithmetic range: the shippable corpus
occupies a narrow slice of every feature (depth is 3–7, never 0–10), and dividing by the arithmetic
range would compress every real puzzle into the bottom of the scale and make the cuts below
unreachable. Each range's floor is the corresponding hard filter's floor — clearing a bar you were
required to clear earns nothing.
Bands: easy [0,3) · medium [3,5.5) · hard [5.5,7.5) · expert [7.5,10].

**Calibration protocol:** every bank build → stratified 50-puzzle spot check, owner records perceived
band; weight changes must cite a spot-check batch. Replace with solve-time calibration when users exist.
Runnable as `python -m geoforge.scoring.report --n N --seed S`, which prints the stratified sample
*and* the batch distribution — a spot check answers "is this puzzle in the right band" and cannot
answer "is this cut ever reached", which is the question an empty band raises. The report names bands
nothing reached, how far the best puzzle fell short of each missed cut, and any feature that took a
single value across the batch (a constant feature is a fixed offset and no discrimination).

## 5.2 Hard rejection filters (any hit ⇒ discard)

1. `depth < 3` or `distinct_rules < 2` — trivial. **Applied twice, over two different graphs
   (settled Phase 2).** A cheap copy runs at doc 04 Stage 5 over the whole solve, to reject a goal
   before traceback is paid for; the authoritative copy runs here over the minimal sub-DAG, which is
   what §5.1 scores. The two are *not* ordered: Stage 6 re-derives the goal from the surviving
   premises after minimization, so the sub-DAG is a fresh derivation rather than a subgraph of the
   solve, and a proof with fewer givens to lean on often takes a longer, more varied route
   (measured at seed 42: of 42 goals, 32 agree, 2 fall, 8 rise — one from 5 rules to 8). The early
   copy is therefore a proxy that can in principle reject a goal this filter would have kept, which
   is precisely why this one is re-asserted rather than inherited.
2. Goal one rule away from a given — "read it off the picture". **Implemented as "the published
   solution contains no geometric step at all"** (Phase 2 M3), which is the form this corpus produces:
   measured over 1,200 constructions at seed 42, all 4 such puzzles are a single `combine` sentence at
   depth 3 — the answer follows from the stated givens by arithmetic with no geometry in between.
3. One rule > 60% of applications — monotonous. **Counted over published *geometric* steps, with a
   three-step minimum** (Phase 2 M3). The doc's wording admits three readings and they differ by two
   orders of magnitude; all three were measured over the same 118 puzzles before the threshold was
   fixed:
   - over machine steps of the sub-DAG the observed maximum share is 0.50, so the filter **never
     fires**, at any threshold the doc could have meant;
   - over published steps counting the algebraic idiom it rejects 11 (9.3%) — but `combine` appears
     in 118 of 118 puzzles, so that number measures how often the engine did arithmetic;
   - over published geometric steps it rejects 8 (6.8%) at 0.6, 2 at 0.7 and 0 at 0.75.

   The minimum denominator is not a nicety: 66 of 118 solutions have exactly one geometric step, and
   calling those "100% one rule" would delete more than half the corpus for a ratio with no
   denominator.
4. Figure complexity out of range: < 4 or > 12 visible points; > 2 circles (v1 readability). Measured
   over the *pruned* figure, which is the one the player sees; points run 3–8, so only the lower
   bound binds and it takes 1 of 118.
5. Any given unused by the minimal solution — must be impossible after Stage-6 minimization; a hit is a
   bug report, not a silent discard.
6. Answer or given outside its quantity type's `answer_policy` exactness class (doc 04 §QTR — e.g.,
   non-integer degrees for `angle`, a surd deeper than the closed exact-value grammar for `length`).
7. Isomorphism-hash duplicate within the batch.

## 5.3 Interestingness (soft score; keep top X% per band)

- **Elegance ratio (adopted from TongGeometry):** proof difficulty ÷ construction complexity. A hard
  proof from a simple figure is the signature of a good puzzle; a complicated figure with a shallow proof
  is noise. This is the primary soft signal.
- Positive: goal far (figure-graph distance) from the givens; solution crosses rule families (circle fact
  → isosceles fact) — and, once multiple quantity types are enabled, crosses *quantity* families (an
  angle chase that unlocks a length, a ratio argument that resolves an area): these conversions are
  where generated puzzles feel most like curated ones; a "surprising" equality of far-apart elements; a
  much longer alternate derivation exists in the full DAG (the short path is an *insight*).
- Negative: visual clutter (many collinear points); symmetric figure with symmetric answer; goal at a
  construction's obvious special point.

Keep-rate: **per band, not a flat 40%** (settled Phase 2 M3, deviating from this doc as it stood).
The flat rate assumes every band is oversupplied. Measured at seed 42 the upper bands are
*filter*-limited rather than interest-limited — hard holds 17 of 105 and expert is empty — so
discarding 60% of them would shrink the bands doc 07 T10 already flags as thin. Easy is where the
surplus is and where the rate bites: easy 50% · medium 80% · hard 90% · expert 100%. Selection never
empties a band; a band below its rate keeps at least one puzzle, because deleting a band to enforce a
ratio is the opposite of what the rate is for. Still the main volume/quality knob, still governed by
the ≤ 5% trivial/ugly floor (doc 01).

Two of the positive terms are **measured constant on current output** and therefore contribute
nothing to the ranking, which is all interest is used for. `goal_given_distance` is 0 for every
puzzle — with 4–8 points the premises name nearly all of them, so the argument has nowhere to travel
— and the longer-alternate-derivation signal fires on 2 of 105. Both are kept because both
discriminate on larger figures; the zero is recorded so their presence is not read as evidence they
are doing something.

## 5.4 Gem promotion (manual, optional)

Batch report surfaces top-10 by interestingness per band; the owner may set `"featured": true` (feeds the
daily-puzzle slot). No other human curation exists.

## 5.5 Anti-goals

- Never tune difficulty via clutter or confusing labels — difficulty comes from proof structure only.
- No scorer→sampler feedback loops in v1 (band targeting in Stage 1 is the only coupling). Value-guided
  sampling à la TongGeometry is a deliberate later experiment (doc 09 P3), to be adopted by editing this
  doc, not by drift.
