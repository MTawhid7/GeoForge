# 05 — Difficulty and Quality

Generated puzzles are worthless if trivial or ugly. This module scores every candidate and rejects most.
All constants live in `config/` (shared with doc 04 Stage 5 — one source) and are retuned against
spot-check data; the *feature structure* below is the stable contract, the weights are not.

## 5.0 What difficulty means here (added 2026-08-04 — doc 07 T19)

**Read this before §5.1.** The model below scores the *published proof*. That is a measurement of the
solution we ship, and it was mistaken for a measurement of the puzzle. Playtesting the first bank showed
the two coming apart badly, and in the worst possible direction:

- an *expert*-banded puzzle with a 9-step machine proof through two similar-triangle chains was answered
  by inspection — the figure is a square, the answer is half a right angle;
- a *hard* puzzle was 90° ÷ 2 by symmetry, a route the published proof never mentions;
- 71 of 98 answers were 45°, so the modal guess beat the app.

The structural reason is worse than imprecision. DDAR finds long mechanical chains **precisely in the
symmetric configurations a human sight-reads**, so proof length and human difficulty are anti-correlated
exactly where the expert band lives. Adding weights cannot fix a signal that points the wrong way.

So difficulty is now decided by three things in strict priority order:

1. **Hard gates that establish the puzzle is a puzzle at all** — §5.2 filters 8 and 9. A puzzle with a
   two-step shortcut is not "easy", it is *mis-stated*: we would be publishing a proof that is not the
   shortest thing a solver will find and calling that the difficulty. These are filters, never features,
   because no amount of proof depth compensates.
2. **Human-search features** — how hard the *first move* is to find (§5.1a). New, and the part the old
   model had nothing to say about.
3. **Proof-structure features** — §5.1's original list, retained but demoted. They are a real signal
   *among puzzles that already pass 1 and 2*; they were never a signal on their own.

The calibration protocol governs all three, and no weight may be changed without citing a spot-check
batch — that requirement predates this revision and is the reason the revision was possible.

## 5.1 Difficulty score

Input: the minimal translated solution sub-DAG. All features are quantity-generic (they read DAG
structure and rule/template metadata, never quantity kinds); weights may be calibrated per quantity type
once more than one is enabled.

Proof-structure features (**demoted to a component, see §5.0**):
- `depth` — longest premise→goal chain (primary).
- `width` — total rule applications. **Machine steps of the sub-DAG** (settled Phase 2 M3): difficulty
  must read proof structure, not a presentation decision, and idiom collapsing turns three machine
  steps into one sentence. `published_steps` is recorded alongside so calibration can test the other
  reading without a code change.
- `distinct_rules` — conceptual variety (five uses of triangle-angle-sum is easy even at depth 5).
- `tier_max`, `tier_mix` — rule families used (circle theorems feel harder than supplementary angles);
  tiers are assigned in our template table, not by the engine. The table is not the whole story:
  `combine` and `restate` are named by premise count on the algebraic path and have no engine
  rule id, so they carry tiers in `AR_TEMPLATES`. `combine` appears in **every** puzzle the pipeline
  currently makes, so a tier table that missed it would score most of every solution as tier 0.
  **Amended 2026-08-04 (doc 07 T17):** with the whitelist retired as a gate, rules can now ship that
  have no template and therefore no hand-assigned tier. Every rule in `newclid.all_rules` gets a tier —
  the 19 templated ones keep theirs, the remaining 74 are assigned by family (circle theorems 4;
  similarity/congruence 3; elementary triangle/angle 2; restatement and bookkeeping 1) in one reviewed
  table. An unrated rule is a **build error**, not a silently-zero tier: the whole point of the feature
  is that harder theorems score higher, and defaulting to 0 would score the hardest new rules lowest.
- `branch_join` — DAG joins of independent sub-deductions (strongly felt as "hard"). Counts steps
  resting on two or more *derived* facts; a step resting on two givens is one idea, not a join.
- `nice_penalty` — subtractive. **Two of three components ship** (Phase 2 M3): *answer telegraphed by
  a given* and *round values everywhere*. *Symmetric freebies* does not: deciding a figure is
  symmetric and that its answer follows from the symmetry needs the graph canonicalization M4 builds
  for dedupe, and a weaker guess would put an unjustifiable number into a published difficulty.

Score = weighted sum of **the features above and those in §5.1a**, normalized 0–10 (initial weights in
`config/`, including `nice_penalty`'s). Per §5.0 the §5.1a group is expected to carry the majority of the
weight once calibrated; the split into two lists is about provenance, not about two separate scores.
Each feature is normalized over a **useful range**, not its arithmetic range: the shippable corpus
occupies a narrow slice of every feature (depth is 3–7, never 0–10), and dividing by the arithmetic
range would compress every real puzzle into the bottom of the scale and make the cuts below
unreachable. Each range's floor is the corresponding hard filter's floor — clearing a bar you were
required to clear earns nothing.
Bands: easy [0,3) · medium [3,5.5) · hard [5.5,7.5) · expert [7.5,10].

## 5.1a Human-search features (added 2026-08-04 — doc 07 T19)

What the proof-structure features could not see: **how hard it is to find the first move**. These carry
the majority of the score's weight once measured, and their initial weights are guesses like everyone
else's — the calibration protocol below is what settles them.

- ~~`shortcut_margin`~~ — **not computable (M5).** It was to be the gap between the published proof's
  depth and the shortest derivation any route achieves, "computed from the same bounded re-solve filter
  9 runs, so it costs nothing extra". Filter 9 cannot be run at all (§5.2 filter 9, doc 04 Stage 6b), and
  there is no second derivation to be shorter: `ProofState.apply` is write-once, so each fact carries
  exactly one justification. There is no depth gap to compute because there is only ever one depth.
- ~~`requires_auxiliary`~~ — **identically zero, not near-zero (M5, doc 07 T22).** Defined as
  `subdag.points() - needed_points()`, it cannot be non-empty: forward chaining binds a rule's
  conclusion only to points its premises already name, so every sub-DAG point enters through a leaf, and
  the leaves are the premises, the configuration facts and the tautologies — all but the last of which
  `needed_points()` already contains. Measured 0/163 at seed 42, with containment holding 61/61 and no
  tautology ever naming an otherwise-unmentioned point. The decisive case is the `langley_with_auxiliary`
  fixture, the one genuinely auxiliary-requiring construction in the repo: it reports **empty**, because
  the auxiliary point is named by a premise. Any constructed point is a stated given the moment the proof
  uses it, so this metric is blind to exactly what it is named for. The literature's difficulty
  multiplier is real (doc 07 T10); it does not survive translation into a pipeline that *draws the whole
  construction for the player*, and nothing detects it here until the hide mechanism exists (doc 07 L1).
- `unused_points` — **the replacement, and the one §5.1a feature that ships in M5.** Drawn points the
  minimal derivation does not need: `len(set(pruned.points) - derivation.needed_points())`. This is the
  honest version of the question the two entries above were reaching for — not "must the solver invent a
  point" (they never must) but "how much of what they are shown is irrelevant". It is free, it comes from
  data Stage 6 already produces, and unlike its predecessors it **varies**: measured over the seed-42
  corpus it spans 0–5 with a mean of 1.7, and only 34% of puzzles have none. The variance exists because
  `prune_figure` closes construction dependencies transitively — a point needed to *build* a kept point
  survives into the figure even when no premise names it. Weight is a GUESS pending §5.1b, and its sign
  was checked against the corpus before it was assigned rather than argued from the story.
- `first_move_branching` — how many facts are derivable in one step from the stated givens. A figure
  offering three openings is a search; a figure offering one is a nudge. Read off the closure the
  shortcut check already builds.
- `goal_symmetry_distance` — whether the goal is fixed by a symmetry of the *stated premises*. The
  square-diagonal case ("90 ÷ 2, obviously") is exactly this, and it is what let a 9-step proof be
  sight-read. Requires the graph canonicalization that dedupe builds, which is why it is specified here
  and lands with that milestone rather than before it.
- `answer_surprise` — subtractive, and the honest name for the 45° problem. How predictable the answer
  is given the bank's own answer distribution for the band. Filter 8 caps the pathological case; this
  scores the rest of the range.

## 5.1b Calibration protocol

Every bank build → stratified 50-puzzle spot check, owner records perceived
band; weight changes must cite a spot-check batch. Replace with solve-time calibration when users exist.
Runnable as `python -m geoforge.scoring.report --n N --seed S`, which prints the stratified sample
*and* the batch distribution — a spot check answers "is this puzzle in the right band" and cannot
answer "is this cut ever reached", which is the question an empty band raises. The report names bands
nothing reached, how far the best puzzle fell short of each missed cut, and any feature that took a
single value across the batch (a constant feature is a fixed offset and no discrimination).

**Two columns added 2026-08-04.** `perceived_band` is joined by **`solved_by_inspection`** (yes/no —
the single question that would have caught the first bank, and the one no automated feature answered)
and **`prose_ok`** (the sampled human read that backstops the LLM renderer's entity-level check, doc 03
§3.5a item 3, doc 07 O8). The spot check is now the acceptance instrument for three separate subsystems,
so it is run on every bank build and its output is committed alongside the bank.

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
8. **Answer-entropy cap (added 2026-08-04 — doc 07 T5).** No single answer value may hold more than
   `FILTERS.max_answer_share` of a band. This is a **bank-level** filter, not a per-puzzle one: it runs
   at selection time and rejects the surplus, keeping the highest-interest puzzles at that value. It is
   a hard filter and not an interest term because the failure it prevents is not "boring", it is
   "guessable" — measured on the first bank, 71 of 98 answers were 45° and 15 more were 90°, so guessing
   the mode beat the app 72% of the time and no amount of proof quality redeems that.
   Two supporting mechanisms live upstream, because a cap alone would just discard most of the corpus:
   Stage 2 must draw from the *band's* value palette rather than always the easy one (doc 04 Stage 2),
   and non-angle quantity types widen the answer space structurally (doc 07 T18).
9. ~~**Shortcut (added 2026-08-04 — doc 07 T19).**~~ **CANNOT BE BUILT ON THIS ENGINE (settled M5).**
   The specification — re-solve the goal from the stated givens under a step budget of
   `FILTERS.shortcut_budget`, discard if it lands — asks the engine a question it has no way to answer.
   Four independent blockers, kept on the page so the filter is not re-proposed in six months:
   - **no budget to impose.** `SolveOptions` has a seed, a backend and a wall clock; there is no step or
     depth cap, and caps are evaluated after the fact;
   - **a tier-limited solve is inert.** Newclid's `FollowDeductions` agent ignores its `rules` argument;
   - **forward search never reaches an angle goal.** *Measured (M4a, seed 42, n=600):* across 117
     saturating closures over the stated givens, 181 `aconst` facts appear and **0 are novel**. The
     closure does not derive constant angles, so a bounded re-solve returns "no shortcut" for every
     angle puzzle whatever its difficulty. Per this section's own rule that a filter must be shown to
     fire, a filter that provably *never* fires is worse than absent — it would read as evidence;
   - **no alternative route exists to be found.** `ProofState.apply` is write-once: one justification per
     fact, so the DAG holds no second derivation.

   The failure it targeted is real and now **unmitigated**: the human shortcut ("a rhombus diagonal
   bisects the angle") is a composite theorem the engine's rule granularity lacks, not a shorter path
   through its rules. It has to be caught by recognising the *configuration* (the configuration table)
   or by an outside judge (the LLM oracle column, doc 07 T21's sibling reasoning) — neither of which is
   a proof, and both of which trail the corpus. This is the largest known hole in the difficulty story
   and it is named as such rather than papered over.
10. **Figure poverty (added 2026-08-04).** A rolling build metric rather than a fixed threshold at
   first: figures with no circle, fewer than 5 points, and fewer than 3 distinct given kinds are the
   shape the first bank was made of. The immediate action is measurement and reporting per band, not a
   cut — setting a threshold before knowing the distribution is how filter 3 nearly deleted a third of
   the easy band. Promote to a hard filter once the distribution is known.

## 5.3 Interestingness (soft score; keep top X% per band)

- **Elegance ratio (adopted from TongGeometry):** proof difficulty ÷ construction complexity. A hard
  proof from a simple figure is the signature of a good puzzle; a complicated figure with a shallow proof
  is noise. This is the primary soft signal.
  **Caveat recorded 2026-08-04:** the numerator is the §5.1 proof-structure score, so for as long as
  that score is the thing §5.0 says it is, elegance inherits its blind spot — the square-diagonal puzzle
  scores as *elegant* (long proof, tiny figure) when it is the opposite. Elegance is only meaningful
  downstream of filters 8 and 9, which is where the pipeline now runs it.
- **Invariance** (added 2026-08-04): whether the answer is stable while a free parameter of the
  construction varies. This is the punchline of most of the reference material in doc 01 — "the shaded
  area is the same wherever you put the point" — and Stage 8's resampling already computes exactly this
  and currently discards the information. Nearly free, and the closest thing we have to a machine-
  readable definition of "surprising".
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

- Never tune difficulty via clutter or confusing labels — difficulty comes from the search, never from
  presentation obstacles. (Wording widened 2026-08-04 from "from proof structure only", which §5.0
  showed was too narrow: proof structure is one input among three, and treating it as the definition is
  what produced sight-readable expert puzzles.)
- **Never lower a band cut to populate a band.** Unchanged, and reinforced: an empty expert band is a
  measurement, and doc 07 T10 forbids inflating bands to fake the upper rungs.
- ~~No scorer→sampler feedback loops in v1~~ — **superseded 2026-08-04 by doc 07 T20**, which draws the
  line in a different place. The rule was aimed at a real hazard (a scorer optimizing against itself
  drifts away from human perception) but it also forbade backward generation, which is not a scorer loop
  at all and is the main thing standing between us and interesting figures. The replacement line: an
  **interestingness proposer may guide the search; the difficulty score may not.** Difficulty stays a
  measurement made after the fact, on a corpus its own weights had no hand in producing — which is what
  keeps the calibration protocol meaningful.
