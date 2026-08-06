# 04 — Generation Pipeline

The generator turns random constructions into validated candidate puzzles. Expect brutal attrition
(> 90% of samples discarded is normal); throughput comes from cheap early rejection. The readability gate
(doc 03 §3.5) adds a new attrition stage the old design didn't have.

## §QTR — Quantity-type registry

The pipeline is parameterized by a registry of **quantity types**; nothing outside the registry may
special-case "angle". Each registered type declares:

| Field | Meaning | `angle` | `ratio` / `length` | `area` (later) |
|---|---|---|---|---|
| `goal_extractor` | Which derived facts qualify as goals | numeric-valued angle atoms (`aconst`), proposed then verified — the closure emits none | AR length/ratio atoms (`rconst`, `lconst`), **harvested from the closure**, which emits them directly (M4a). Not `r2const`/`l2const`: nothing derives those | custom area layer output (doc 03 §3.7) |

**`goal_extractor` signature, widened 2026-08-06.** It takes a **`FigureView`** — the reference
coordinates *and* the engine's certified facts — where it previously took coordinates alone:

```python
goal_extractor: Callable[[FigureView], tuple[Proposal, ...]]
```

The original signature encoded `angle`'s workflow as though it were every type's: measure the
diagram, propose a value, let the engine verify. That is right for any quantity the engine can
*evaluate*, and wrong for one it cannot. An area is computed from certified facts — a right angle
here, a midpoint there (doc 10 §10.5) — and a coordinates-only extractor would have to re-derive
that geometry from numbers, which invariant 4 forbids outright.

A dataclass rather than a second positional argument, so that the next field a quantity type needs
is an addition rather than another signature break. Two properties are asserted by tests rather
than assumed: `angle` ignores `facts` entirely (it reads the diagram, and a version that started
depending on facts would be a design change, not a refactor), and **every** registered type
accepts a view — the contract belongs to the registry, not to `angle`.

**`verifier` — a seventh registry field, added 2026-08-06.** How a proposal is shown to be *true*
is the type's business, not Stage 5's:

```python
verifier: Verifier = verify_with_engine     # (backend, figure, proposal, opts) -> Verification | None
```

The registry previously assumed every quantity is an engine predicate, because every registered
one was. Two routes now exist:

| route | who decides | proof DAG | used by |
|---|---|---|---|
| **engine-verified** (default) | `solve_facts` derives the goal from the premises | yes — Stage 6 minimizes it | `angle`, and anything the engine can evaluate |
| **layer-verified** | our own arithmetic on engine-certified facts, checked against the reference diagram | **no** | `area` — no engine in the lineage has an area predicate (doc 03 §3.7) |

`Verification` carries the canonical `fact`, the `evidence` it consumed (premises Stage 6 must not
minimize away), the `proof_dag` Stage 6 minimizes, and an optional engine `result`.
`VerificationError` stays separate from returning `None`, because "the engine crashed" and "the
premises do not force this value" are different facts and the attrition report counts them apart.

`proof_dag` is **required**, not optional. A verification with no derivation is a value nobody can
be shown how to reach, and shipping one would mean shipping a puzzle with no solution. A
layer-verified type supplies its own — `area` renders its decomposition tree as proof steps whose
rule ids are the route names (doc 10 §10.10f) — so every stage after Stage 5 reads one graph and
never asks which route produced it.

**`format_answer` — widened 2026-08-06, the third and last signature that assumed a rational:**

```python
format_answer: Callable[[Fact], str]        # was Callable[[Fraction], str]
```

An area's value lives in `Fact.exact` as a surd and cannot be a `Fraction` at all, which is the
entire reason the layer exists (doc 07 T18, T21). Taking the whole fact lets each type read the
field it stores its value in.

**`claim_of` — the fourth and last field the area work added (2026-08-06):**

```python
claim_of: ClaimOf        # (goal fact, reference coords) -> Claim | None
```

Stages 8 and 9, the bank layout and the bank build all took a `VertexAngle`, which bundled three
assumptions: that a goal is an angle, that its value is degrees, and that re-measuring it means
reading three points off a diagram. A `Claim` carries the published question, its `exact` and
`display` forms, its render and drift tolerances, and a `measure(coords)` closure — so Stage 8 can
re-read the answer from a resampled figure without knowing what quantity it is holding.

`angle` supplies a vertex-angle reading. `area` supplies a shoelace one, which needs **no** mod-π
resolution — so this generalization *deleted* a special case rather than adding one. A claim whose
`angle` is None asks its question in the statement text rather than drawing a goal arc.

Returning None is how a goal with no reading in this figure becomes `goal_unreadable` attrition,
which is why the field is required rather than defaulted: a type registered without one would be
discarded on every puzzle it produced, and the report would read as a hard corpus rather than as a
missing registration.
| `dimension` | Scale behavior | scale-free | ratio: scale-free; length: **scale-pinned** | scale-pinned (dimension 2) |
| `nice_values` | Given-value palette per band | rationals × π — round for easy, **non-round for the upper bands** (doc 07 T18) | small integers/surds, small fractions | — (derived) |
| `answer_policy` | Exactness class + input mode (doc 02) | integer degrees, keypad | fraction / decimal+tolerance, exact surd revealed on solve | decimal+tolerance |
| `templates` | Step template family (doc 03 §3.5); **fallback only** since the LLM path renders anything (doc 07 T17) | angle family | similarity/metric family | decomposition family |
| `marks` | Mark kinds **this type's own quantities** use | arcs | length labels, braces | shaded regions |

Enabling a type = registering these six things + its config block. The registry keeps schema, gates,
scoring, and frontend generic while rollout stays deliberate (doc 09).

**Enablement status (2026-08-04):** `angle` enabled; `ratio` and `length` promoted to the same phase as
the difficulty rebuild (doc 07 T7) — angle alone means every answer is eyeball-readable on a to-scale
figure (T5), so the second wave is now a difficulty requirement rather than a variety nicety. `area`
still needs the verified decomposition layer, or a second engine (doc 03 §3.7).

Note the registry's `templates` row no longer gates enablement. Under doc 07 T17 a new quantity type
needs its *goal extractor*, *nice values*, *answer policy* and *marks*; prose comes from the LLM path
whether or not templates exist yet.

## Pipeline stages

```
sample construction ─▶ assign numeric givens ─▶ numeric pre-checks ─▶ SAL closure (engine)
  ─▶ goal selection ─▶ traceback + premise minimization (incl. configuration facts)
  ─▶ shortcut + auxiliary-construction check ─▶ step rendering ─▶ well-posedness gate
  ─▶ emit CandidatePuzzle ─▶ (scoring/filters, doc 05) ─▶ (bank build + cross-engine validation, §V)
```

### Stage 1 — Obtain a construction (**two sources since M6 — doc 07 T24**)
`sampler.draw` produces one construction per index from one of two sources, chosen by
`GENERATION.corpus_share` on the construction's own rng so the choice stays a pure function of
`(seed, index)`.

**Stage 1a — clause growth.** 3–9 JGEX-compatible steps from a weighted grammar (weights in `config/`;
follows `ncdgen`'s sampler, re-weighted). Unbounded and cheap; produces small, symmetric,
right-angle-heavy figures, which is doc 07 L4.

**Stage 1b — configuration seeding.** Take a human-authored competition configuration from
`generator/corpora.py` — 635 problems in the reference clones, in this same JGEX syntax — and discard
its goal. Their goals are `perp`/`cyclic` statements to *prove*; ours are values to *find*, and Stage 5
picks one. The skeleton is richer than anything Stage 1a reaches: 7–17 points against 3–9, with
incentres, orthocentres, tangent circles and spiral similarities the grammar never assembles.

Seeded figures are **metric-free** and yield nothing on their own — `triangle a b c` samples generic
angles, so no angle has a nice value. Stage 2 is what makes them puzzles, which is why the two stages
must be read together. Measured over 60 JGEX skeletons: 4 goals bare, 20 decorated.

Neither source is sufficient alone. The library is finite, so a bank built only from it repeats
skeletons and its isomorphism dedupe bites; growth is unbounded but poor. `BatchReport.sampled_origins`
and `puzzle_origins` report the split and its yield on every build, so `corpus_share` is retuned against
data rather than taste.

**Measured verdict on random clause growth (2026-08-04): it is the binding constraint on puzzle quality,
and it does not work well enough.** At seed 42 over 400 constructions, 344 of 546 discards — 86% of all
attrition — are degeneracy: `degenerate_triangle` 148, `unrealizable` 98, `flat_angle` 75. What survives
is small and symmetric: 82% of banked figures have 4 or 5 points and **not one of 98 contained a
circle**, despite `circle_step_weight = 2.0` biasing the grammar toward them. Growing a figure one
random clause at a time essentially never lands on the deliberate arrangements the reference material in
doc 01 is made of — three squares sharing a vertex, two hexagons edge to edge, a square inscribed in an
equilateral triangle. Recorded as doc 07 L4.

Three upgrades, in order (doc 09 P3 then P5):

1. ~~**Pass the band through.**~~ **DONE, M4.** `band_for_index` draws a Stage-1 profile from
   `GENERATION.band_mix` on the construction's own rng stream, so it stays a pure function of
   `(seed, index)` and sharding still changes nothing. `BandProfile` carries step range, circle weight,
   angle weight and goal budget per band; `BatchReport.sampled_bands` reports how the budget was spent,
   which is the number to compare against `by_band` when asking which profile pays for itself.

   **The circle bias was measuring the wrong thing, and that is what produced the first bank.**
   `ConstructionDef.introduces_circle` keyed on the `cong` predicate — which is how JGEX spells a
   circle *and* every square, parallelogram, isosceles triangle and reflection. It flagged **37 of 87**
   primitives, so a 2× "circle bias" was a 2× bias toward symmetry generators. The flag now means what
   `emit.circles_of` draws (a `circle` or `cyclic` clause): 3 primitives, 2 of them usable. Measured at
   seed 42, circles per figure went **0 of 98 → 10 of 25**.

   A second weight joins it: `angle_weight`, over the primitives that state an angle value. Measured
   before it, **only 2 of 22 surviving puzzles stated an angle at all**, so the per-band palette below
   governed 9% of the corpus and the rest answered 45° because the figure contained a square.
2. **Configuration-seeded generation.** A hand-reviewed library of figure *archetypes* — cyclic
   quadrilateral with diagonals, two intersecting circles, square with an inscribed triangle,
   regular-polygon dissections — instantiated and then decorated by the existing random growth, rather
   than grown from nothing. This is a whitelist for the same reason the translation table was: an
   archetype nobody has reviewed is a figure nobody can vouch for. Expected to fix the degeneracy rate
   as a side effect, since archetypes are realizable by construction.
3. **Backward generation** (doc 07 T20, doc 09 P5): search from a target configuration and traceback to
   propose the problem, rather than deducing everything and keeping whatever survives.

### Stage 2 — Assign numeric givens
Choose 1–3 free parameters; assign exact values from the target quantity type's `nice_values` palette
for the band (angles: multiples of 10 → arbitrary integers; lengths: small integers/surds; ratios: small
fractions). Remaining parameters stay free — they power the well-posedness check.

**For a seeded skeleton (Stage 1b) this stage is what creates the puzzle.** `sampler.decorate` appends
`BandProfile.max_givens` `s_angle` clauses from the same per-band palette — 1 for easy up to 3 for
expert, capped at half the skeleton's point count so a small figure is never over-constrained. A
competition configuration states no angle values at all, so without this Stage 5 has nothing to propose;
with too many, the answer becomes a restatement of a given and Stage 5's `already_given` check discards
it. The count is a config knob for exactly that reason.

**The band was never passed here, and it was a contributing cause of the 45° bank (fixed M4).**
`_render_numeric_param` falls back to `nice_angle_degrees["easy"]` when no band is given, and Stage 1
never gave one — so every angle in every band came from multiples of 10. The palette now differs per
band, and the upper bands draw **non-round even integers** (multiples of 10 excluded): `aconst` stores a
`Fraction` of π, so 74° costs exactly what 90° costs (doc 07 T18), and values stay even because
bisecting an odd angle leaves a half-degree that the whole-degree `answer_policy` then rejects.
What is *not* available at any price is an irrational angle.

**Measured caveat, and the reason Stage 5 also gates on the answer:** fixing the palette was necessary
and nowhere near sufficient. Only **2 of 22** surviving puzzles stated an angle at all, so the palette
governed 9% of the corpus; the rest answered 45° because the figure contained a square, with no angle
given anywhere. Stage 1's `angle_weight` addresses the first half and Stage 5's rejection the second.
~~Irrational answers come from the other quantity types via `l2const`/`r2const` (doc 03 §3.3a).~~
**Reversed by M4a:** nothing derives `l2const` or `r2const`, so no quantity type on this engine yields
an irrational answer (doc 07 T18, T21). The residual guessability is filter 8's per-band share cap, not
a second quantity type.

**Scale pinning:** if
the target quantity type is dimensional (`length`, `area`), exactly one given must fix the figure's
scale (a stated segment length); scale-free types must have *no* length givens (they'd be redundant and
fail Stage-6 minimization anyway).

### Stage 3 — Numeric pre-checks (before the engine call) — **rescoped M6, doc 07 T23**
Instantiate once with a fixed reference seed, then ask two different questions with two different
consequences. Thresholds are unchanged and still live in `config/`, never inline.

**Rejected here (whole-figure):** the engine could not instantiate it; fewer than 3 points; any point
pair closer than ε_sep. These say the figure is broken, and a broken figure has nothing to offer.

**Reported here, acted on later (per-triple):** `degenerate_triples` returns every undeclared triple
whose area is below ε_area or whose angle is within ε_deg of 0°/180°. Declared collinearity is exempt —
`on_line`, `midpoint` and `foot` create it on purpose. Stage 5 refuses a *goal* built on such a triple;
nothing else is refused for it.

This used to be one whole-figure rejection, and that was a defect rather than a strictness choice: the
probability of rejecting climbs with C(n,3), so the check was hardest on the richest figures. It threw
away 85% of IMO configurations — figures correct by definition — and 14 of the 20 seeded constructions
that produced a goal. A flat triple in a far corner cannot corrupt a *symbolic* proof (doc 02
invariant 4); it can only mislead a *numeric* check, and the numeric check that matters is the one about
the goal. See doc 07 T23 for the residual risk this accepts.

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

**Sight-readable answers are rejected here (added M4 — doc 07 T5).** An answer of 45° or 90°
(`GENERATION.rejected_answer_degrees`) is *recognised* off a to-scale figure rather than measured, so
the puzzle has no content left however deep its proof. It is a rejection rather than a ranking penalty
because a preference only helps when the same construction also offers something better, and most offer
nothing else — measured over 250 constructions, 45° was 13 of 47 verified candidates (28%) but 11 of 24
after ranking (46%). **Ranking by proof depth was actively concentrating them**, which is doc 07 T19 in
miniature: the engine's longest mechanical chains live in exactly the symmetric figures whose angles are
round. `_preference` therefore stays `(-depth, -distinct_rules, key)` and carries no roundness term —
by the time it runs, every readable answer is already gone.

Scope was chosen by measurement, over 3,000 constructions at seed 42:

| rejected | puzzles | yield | distinct answers | modal share |
|---|---|---|---|---|
| nothing | 163 | 5.43% | 10 | 71.8% |
| **{45, 90}** | **25** | **0.83%** | **9** | **36.0%** |
| multiples of 30 and 45 | 13 | 0.43% | 7 | 30.8% |

{45, 90} does almost all the work; extending to every multiple of 30 buys 5 points of modal share and
halves the yield again. The residual concentration is doc 05 §5.2 filter 8's job — a per-band *share*
cap keeps a hard puzzle that answers 60° while refusing a bank full of them, which banning the value
cannot do. `reject_sight_readable=False` exists for tests over classic fixtures (Thales, inscribed
angle) whose whole point is a right-angle answer; never for shipping.

**"Closure-scanning is a secondary source only" is right for angles and backwards for ratios (M4a).**
The propose-then-verify sweep above exists because a saturating closure emits **no** `aconst` — measured
at seed 42, n=600: all 181 `aconst` facts across 117 closures were stated givens, none derived. That is
the same fact doc 05 §5.2 filter 9 rests on. `rconst` behaves oppositely: the closure emits it directly
(32 facts, 17 of them novel, over the same 117 figures), so a ratio goal arrives already symbolically
derived and costs no speculative engine call at all. Whichever quantity type is registered next should
pick its extraction direction from this, per type, rather than inheriting the angle sweep — the QTR's
`goal_extractor` is the right seam for that, and it needs no change to accommodate it. Doc 07 T21
records why "next" is not `ratio`: the direction is cheap, the answers are not worth harvesting yet.

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
- ~~**Auxiliary-construction detection (added 2026-08-04 — doc 07 T10).**~~ **NOT BUILT — the signal is
  identically zero by construction, not near-zero on current output (M5, doc 07 T22).** The definition
  was: a point the minimal derivation *uses* that is named by no stated given and does not appear in the
  goal, i.e. `subdag.points() - needed_points()`. It cannot be non-empty. Every point in the sub-DAG
  enters through one of its own leaves — forward chaining derives facts about existing points, so a
  rule's conclusion binds only points its premises already name — and the leaves are exactly the
  premises, the configuration facts and the trivial tautologies. `needed_points()` is the premises plus
  the configuration plus the goal, so the difference can only ever be a point named *solely* by a
  tautology.

  Measured at seed 42: 0 of 163 puzzles have a non-empty difference; containment holds for 61 of 61
  checked; no trivial fact ever names a point nothing else does. And the decisive case — the repo's
  `langley_with_auxiliary` fixture, the one construction here that genuinely needs an auxiliary line —
  reports **EMPTY**, because its auxiliary point `d` is named by the premise `aconst:a:c:a:d=1/9`. Any
  constructed point becomes a stated given the moment the proof uses it. The metric is definitionally
  blind to the thing it is named for.

  What replaces it is `unused_points` (doc 05 §5.1a): drawn points the derivation does not need. That
  one is about the *figure* rather than the proof, it varies across the corpus, and it is the honest
  version of "how much irrelevant structure must the solver search". *Hiding* a genuinely auxiliary
  point remains a later phase (doc 07 L1), and this stage no longer claims to detect one.

### Stage 6b — ~~Shortcut check~~ **NOT BUILDABLE (settled M5 — doc 05 §5.2 filter 9, doc 07 T22)**
The specification was: re-solve the goal from the **stated givens only**, over the same fixed
coordinates (`solve_facts`, doc 03 §3.3), under a small step budget; if the goal falls out within
budget, discard, because the puzzle's real solution is not the one we were about to publish. The
*intent* is right and is still the product's central difficulty question (doc 07 T19). The mechanism
cannot be built on this engine, for four independent reasons, and it is recorded here rather than
deleted so it is not re-proposed:

1. **There is no step budget to impose.** `SolveOptions` carries a seed, a backend and a wall clock —
   no step or depth cap. Caps are evaluated after the fact, so "solve under 2 steps" cannot be asked.
2. **A tier-limited solve is inert.** Newclid's `FollowDeductions` agent ignores its `rules` argument,
   so restricting the rule set does not restrict the search.
3. **Forward search cannot reach an angle goal at all.** *Measured (M4a, seed 42, n=600):* across 117
   saturating closures over the stated givens, **181 `aconst` facts appear and 0 of them are novel** —
   every one is a stated given. The closure never *derives* a constant angle, so a bounded forward
   re-solve would return "no shortcut" for every angle puzzle regardless of difficulty. A gate that
   passes everything is worse than no gate: it would read as evidence.
4. **There is no alternative route to find.** `ProofState.apply` is write-once, so each fact carries
   exactly one justification and the DAG holds no second derivation to be shorter.

The human shortcut this was meant to catch — "a rhombus diagonal bisects the angle" — is a *composite
theorem the engine's rule granularity does not have*, not a shorter path through the engine's rules.
So it must be caught by recognising the *configuration*, which is the configuration-table filter, or by
an outside judge, which is the LLM oracle column. Neither asks the engine a question it cannot answer.

Consequently `shortcut_margin` is not computable either (doc 05 §5.1a), and doc 07 O9 closes.

### Stage 7 — Step rendering
Render the sub-DAG per doc 03 §3.5 / §3.5a. Output: final `solution[]` steps.

**No longer a gate on rule vocabulary (2026-08-04 — doc 07 T17).** It read: "untranslatable ⇒ discard,
log offending rule", and measured 91% pass over 300 sampled constructions with every failure an
over-budget AR chain. That gate is retired. A step with a template uses it; a step without one is
rendered by the LLM path; an over-budget AR chain goes to the LLM path too, which handles long chains
better than a template can. The discard log survives as the priority queue for the template table, now
recording "no template, rendered by LLM" rather than a deletion.

**Two things still discard a puzzle here**, and both are about content rather than vocabulary: a step
whose rendered sentence fails the fidelity check after retry and fallback (doc 03 §3.5a item 3), and the
unspeakable-given check below. Attrition at this stage should now be small and any rise in it is a
renderer bug, not a coverage gap. Steps are emitted in **topological order ending at the goal**, not the engine's canonical fact
order, so a reader never meets a step before its premises. The translation also reports which points
its steps highlight, which Stage 6 pruning must keep.

**The gate covers the givens too (added Phase 2).** It originally inspected only steps, which left
the hypotheses unchecked: a surviving premise can be a directed angle between two lines that meet at
no named point, and that has no ∠ABC spelling — the presentation cost doc 07 T1 accepted. Such a
puzzle is unshippable however readable its proof is, because the player is shown a statement missing
one of its own hypotheses, and it *was* shipping (`gf-000042000213-1` carried `aconst:a:c:d:e=1/9`).
The check runs over the **minimized** premise list, since that is what the puzzle states, and ahead
of Stage 8, whose 64 resamples are wasted on a puzzle that cannot be phrased. Discard reason
`given_unspeakable`; measured at 1 of 36 formed puzzles at seed 42.

### Stage 8 — Well-posedness gate (critical correctness gate)
Stated premises **+ configuration facts** must uniquely determine the goal value. For scale-free
quantity types the check runs modulo similarity (resampled figures may differ in scale/pose); for
dimensional types the resampler holds the pinned unit fixed and the goal value must be invariant
absolutely.
1. Resample M = 64 instantiations: re-run the construction with fresh free parameters, **rejecting any
   sample whose configuration facts differ from the reference** (a configuration flip is a legitimate
   different figure, not evidence of ill-posedness — and not a bug).
2. Accept iff the goal's numeric value deviates < ε_wp across all accepted samples.
2b. **Also check the solution text** (added M4, refined M5). Steps are published as human vertex
   angles, and the directed fact the engine proved allows two of them — θ or 180° − θ — with the
   configuration deciding. The check is to **re-render the solution from each resampled figure and
   require identical text**. Freezing each stated angle's *value*, or its direct/supplement
   *reading*, are both wrong: a step says "∠CAO = ∠OCA", and as C runs round its circle both angles
   change and both readings flip together while the sentence stays true. Only what a sentence
   claims has to be stable, and re-rendering is exactly the test of that.
3. **Reclassified in M5.** A deviation among configuration-matching samples means the puzzle's stated
   facts do not pin its answer, so the puzzle is discarded — *this is the gate working*, and it is
   ordinary attrition (measured: ~1.7% of formed puzzles). It is **not** an upstream soundness bug,
   as this document previously assumed: that assumption required the recorded configuration facts to
   pin the figure completely, and they do not. The engine records the numerical checks its *rules*
   needed, not a full description of the configuration, so an angle-chased `aconst` can depend on the
   reference diagram in ways nothing we state captures. A reproduction case is still filed for
   analysis. Recorded as doc 07 T13.
3b. The one verdict that **does** indict the engine and fails the build: the goal fact proved
   symbolically is numerically **false in the very diagram it was proved about**. Nothing downstream
   can compensate, so the batch exits non-zero. Measured across 1,200 constructions: zero.
   Deviation across flipped configurations ⇒ normal discard of the sample, not the puzzle.
4. Known residual limit: construction-based sampling explores the construction's parameterization of the
   premise manifold, not the whole manifold. Recorded as accepted risk (doc 07 T3) with the cross-engine
   validation and optional SMT check as compensating controls.

### Stage 9 — Emit
`CandidatePuzzle`: the schema-v2 `Puzzle` (doc 02) plus the pipeline objects doc 05 scores over,
carried in memory and never serialized — the only thing that can reach the JSON is what the schema
defines.

**Emit is a gate, not a formatter (Phase 2).** Assembling the figure can *refuse* a puzzle: a mark
the givens do not back, a given with no phrasing, two engine points colliding on one display label.
Those are attrition under the `emit` stage with a named reason rather than an exception, so they are
counted like every other discard — a rising `emit:` line means an assembly bug rather than a quietly
swallowed one. Measured at seed 42: zero across 400 constructions.

Givens are rendered through the same `phrases.describe` the solution steps use, against the
**reference** coordinates, so a hypothesis and a step citing it read identically and both match the
diagram Stage 8 certified the wording over. Display coordinates are a separate parameter: the drawn
figure is a similarity transform of the reference figure (uniform scale, translation, and one y-flip
for SVG's axis), which is the only class of transform that preserves every premise (doc 06 §6.3,
doc 07 T5). Choosing a *better* instantiation to draw is doc 06 §6.3's layout, downstream of here.

## §V — Bank-build validation (doc 02 invariant 3) — implemented M6
Every accepted puzzle is re-derived from scratch by the **ag2ddar** backend (uncorrelated codebase):
premises + coordinates in, goal fact must be derivable out, answer must match exactly. Plus: schema
validation, numeric re-check at bank tolerances, optional SymPy/Gröbner spot-check on a sample (still
open), and mutation tests (corrupt an answer / drop a premise ⇒ validator must reject — a validator that
never fails is untested).

**The input is the emitted JSON, not the generator's objects.** A validator handed the generator's
in-memory state re-checks the *run*; this one re-checks the *artifact*, which is what ships, and can be
pointed at a bank file months later. That is why puzzles carry a `reference_figure.points` block: the
engine coordinates the puzzle was derived over, build-time data stripped from shipped banks alongside
`provenance` (doc 02), and distinct from the laid-out display `figure` that Phase 2 produces.

**The reference figure is the *pruned* point set.** A validator handed the scaffolding the drawn figure
no longer shows could derive the goal through a point the player never sees, and report a pass the
puzzle has not earned.

**Configuration facts are carried by the coordinates, not asserted.** DDAR has no `sameclock` or
`sameside` and does not need them: it receives the reference diagram, so the configuration is pinned by
construction. What this does *not* re-check is the well-posedness argument — whether some *other*
diagram satisfying the same premises gives a different answer. That is Stage 8's job on the generation
side; cross-validation certifies the answer over the reference diagram. Recorded as doc 07 T14. Facts
carried this way are listed in the validation record rather than silently skipped, and a configuration
fact appearing among the *stated givens* is a hard failure, not a pass.

Five ship-blocking verdicts, all of which fail the build: `not_derivable` (second engine cannot reach
the goal), `answer_mismatch` (published answer disagrees with the goal fact), `numeric_mismatch` (goal
false in its own reference diagram), `unsupported` (a premise the validator cannot state — an unchecked
puzzle and a valid one are different things), `malformed`, `engine_error`.

**Measured (M6, 1,200 constructions at seed 42):** 129/129 puzzles re-derived by DDAR, zero
disagreements, 2.1 s total (16 ms per puzzle). Mutation tests: 129/129 corrupted answers rejected,
129/129 lying published answers rejected, and **441/441** single-premise deletions made the goal
underivable — an independent confirmation of Stage 6 minimality, since a second engine agrees no
given is redundant.

## Tolerance policy (single source of truth)
Exact layer: derived values are exact rationals; equality is exact. Numeric layer: absolute tolerance on
normalized quantities (radians, unit-scale coords) from `config/`; degeneracy uses Stage-3 ε's. Never
compare floats for equality; never let a numeric check pass a fact no symbolic derivation produced.

## Determinism and parallelism
Pipeline is a pure function of `(config, engine_version, master_seed)`; seed-sharded across processes.
Every discard logs `(stage, reason, seed)`; the attrition report per stage **and per band** is the primary
regression signal — drift between builds means a sampler/engine/translator change did something.

**Sharding requires per-index seeding, not a per-batch stream (settled Phase 2).** Construction *i*
must be a function of `(master_seed, i)` alone — both its clause sampling and its engine seed. Until
Phase 2 this held for the engine seed but not for the sampler, which drew from one `Generator`
advanced across the loop, making construction *i* depend on every draw before it. Such a batch is
perfectly reproducible in a single process and produces a **different corpus** the moment the range
is split across workers, so the defect is invisible to every same-process determinism test. The
sampler is now seeded `default_rng([master_seed, i])` per construction, and shard-independence is
pinned by `tests/generator/test_batch.py::TestShardability`. Cost: the fixed-seed corpus changed once,
at the fix.

## Failure-mode checklist
| Failure | Guard |
|---|---|
| Degenerate figure | Stage 3 |
| Engine soundness bug | Stage 4 numeric guard + §V cross-engine + mutation tests |
| Solution prose misstates its step | Stage 7 fidelity check (doc 03 §3.5a) + golden fixtures + sampled review |
| **Goal solvable in two steps — the published proof is not the real one** | **UNMITIGATED.** Stage 6b cannot be built on this engine (above; doc 07 T22). Falls to the configuration table and the LLM oracle column, neither of which is a proof |
| **Answer guessable from the bank's answer distribution** | **Selection-time entropy cap (doc 05 §5.2 filter 8) + band-aware Stage 2 palette** |
| **Answer guessable off the figure by eye** | Non-angle quantity types (doc 07 T5); to-scale figures are not negotiable (doc 06 §6.3) |
| Configuration-dependent ambiguity | Stage 6 configuration facts + Stage 8 matching-configuration sampling |
| Redundant givens | Stage 6 minimization |
| Under-determined goal | Stage 8 |
| Scale-unpinned dimensional goal (answer depends on drawing size) | Stage 2 scale pinning + Stage 5 leaf check + Stage 8 |
| Figure leaks undeclared info | Stage 6 pruning + doc 06 anti-leak layout |
| Duplicates | bank dedupe (canonical hash over type-refined labeled premise/goal hypergraph — algorithm specified in `bank/dedupe.py`) |
| Correlated generator/validator bugs | different engines for generation vs validation |
