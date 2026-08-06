# 10 — The area layer

**Status: design, not built. Written 2026-08-05.** Doc 09 P6 requires a design doc before any build;
this is it. Everything marked MEASURED has a seed and a number behind it (docs/08 §8.1.8); everything
marked UNVERIFIED is a known hole, not an oversight.

Governs: exact computation of **area, and the dimensional quantities that share its machinery** — arc
length, perimeter, sector and segment area, curvature. Does **not** govern the engine, which is
untouched by all of this.

---

## 10.1 Why area, and why now

Angle is the only registered quantity type, and it is a weak product for a reason that is structural
rather than fixable by tuning:

- **MEASURED** (40 seeded figures, seed 42): `aconst` appears **102 times declared and 0 times
  derived**. The closure never produces a novel angle constant. Every angle puzzle is therefore a
  chase from stated angles.
- Every angle answer is a rational multiple of π, because `ConstantAngle.angle` is a `Fraction`
  (docs/07 T18). 7π/8 is free; √3/2 is not expressible, ever.
- Angle answers are eyeball-readable on a to-scale figure (docs/07 T5). 71 of the first bank's 98
  answers were 45°.

The two obvious escapes are already measured dead. **Ratio and length as *engine-derived* quantities
are worse than angle**: one rule of 93 concludes a ratio constant (`r51`, midpoint, always ½), AR
chases ratios multiplicatively, and the reachable answers are powers of 2 — 3 distinct values at 52.9%
modal share against angle's 9 at 36.0% (docs/07 T21). `simtri` and `eqratio` have **zero supply** in
generated figures (MEASURED, 0.00 per figure), so ratio-by-similarity has no inputs at all.

Area is not an escape from the same trap; it is a different mechanism. It is **layer-computed**, not
engine-derived, so it is bounded by what the engine can *certify* rather than by what it can *evaluate*
— and the certification supply is rich.

## 10.2 What the engine actually supplies

MEASURED, 40 seeded figures at seed 42, `max_seed_points = 16`. "Derived" means numerically true in the
diagram and provable from the declared set.

| fact kind | declared | derived | per figure |
|---|---|---|---|
| `coll` | 158 | 131 | 7.22 |
| `cong` | 130 | 74 | 5.10 |
| `perp` | 57 | **107** | 4.10 |
| `cyclic` | 9 | **151** | 4.00 |
| `aconst` | 102 | **0** | 2.55 |
| `para` | 18 | 75 | 2.33 |
| `circle` (centre) | 30 | 0 | 0.75 |
| `midp` | 18 | 2 | 0.50 |
| **`simtri`, `eqratio`** | **0** | **0** | **0.00** |

Read this as the layer's parts bin. `perp`, `cong` and `cyclic` are abundant and mostly *derived* —
the engine is doing real work finding them. `simtri`/`eqratio` are absent and no design may depend on
them.

## 10.3 The contract

Non-negotiable, and inherited from docs/07 T6 and docs/02 invariant 4:

1. **The engine certifies geometry. The layer does arithmetic.** SymPy may combine
   already-certified quantities. It may never establish that two lines are perpendicular, that four
   points are concyclic, or that a region is the one the question names.
2. **Numerics verify, never derive.** Every computed area is checked against the reference diagram by
   an independent numeric route (shoelace over the realized coordinates). A mismatch is a build
   failure, not a warning. The check confirms; it never supplies the value.
3. **Every step is a solution step.** A decomposition the player cannot follow is not a solution. The
   layer emits its decomposition as ordinary `solution[]` steps through the same readability path as
   engine steps.
4. **The layer is thin — this is the whole design risk.** If the puzzle becomes "apply the law of
   cosines to a labelled triangle", we have traded a sight-readable answer for tedious computation,
   which docs/01 names as an anti-goal. The difficulty must stay in the geometric derivation the
   engine certifies (spot the concyclicity, find the perpendicular); the layer converts the *final*
   certified structure into a value and does nothing clever.

## 10.4 Feasibility, spiked

**SPIKED 2026-08-05, seed 42.** Three constructions realized, their declared facts read back, the
area computed symbolically and checked by shoelace over the reference coordinates:

| construction | engine declares | layer computes | shoelace |
|---|---|---|---|
| `a = free a; b = lconst b a 4; c = on_tline c a a b, lconst c a 3` | `lconst(a,b)=4`, `lconst(a,c)=3`, `perp(a,b,a,c)` | ½·3·4 = **6** | 6.000000 |
| `a = free a; b = lconst b a 2; c = lconst c a 2, lconst c b 2` | three `lconst` | Heron = **√3** | 1.732051 |
| `a = free a; b = lconst b a 2; c = s_angle b a c 60o, lconst c a 2` | `aconst(a,b,a,c)=1/3` **and** both `lconst` | ½ab·sin C = **√3** | 1.732051 |

The third case is the load-bearing one: the engine certifies an angle *and* two lengths on the same
triangle, which is exactly the input the area and law-of-cosines formulas need.

Values reachable by the layer and unreachable by any engine in the lineage:
`√3`, `2π/3`, `2π/3 − √3` (circular segment), `5π` (annulus), `√3·π²`.

## 10.5 The directed-angle hazard — found by the spike, and it shapes the design

In case 3 the construction says `s_angle b a c 60o` and the engine declares `aconst = 1/3`, but the
realized apex angle is **120°** (`|bc| = 2√3` ⇒ `cos C = −½`). Both readings are correct: engine
angles are **directed, line-to-line, mod π** (ONBOARDING gotcha 5, docs/07 T1), so the directed value
60° and the undirected apex 120° are the same fact.

The consequence splits the primitives cleanly:

| primitive | form | mod-π safe? |
|---|---|---|
| triangle area from two sides and included angle | ½·a·b·sin C | **YES** — `sin θ = sin(π − θ)`, so both readings give the same area |
| Heron from three sides | — | **YES** — no angle involved |
| right-triangle area, Pythagoras | ½·a·b, √(a²+b²) | **YES** — `perp` is its own mod-π reading |
| **sector area** | ½·r²·θ | **NO** — 60° gives 2π/3, 120° gives 4π/3 |
| **arc length** | r·θ | **NO** |
| **circular segment** | ½r²(θ − sin θ) | **NO** |

**Rule: any primitive whose value is not invariant under θ → π − θ must resolve the angle against the
figure's configuration facts (docs/07 T2) before computing, and must refuse rather than guess when the
configuration does not pin it.** This is the exact class of bug that hid a validator miscalibration
and a reflection bug behind 90° (ONBOARDING gotcha 6). No sector or arc fixture may use a right angle
or an isosceles figure.

## 10.6 Scale pinning

Area is the first **dimensional** quantity, so docs/07 T7 applies: it requires a stated unit, where
angle forbids one. `lconst` is already in the catalogue's numeric-parameter whitelist
(`solvers/catalog.py`) and `sampler._render_numeric_param` renders it as a small integer, so the
construction language expresses this today — but **Stage 2 currently appends only `s_angle` givens**
(`sampler.decorate`), so no seeded figure carries a length. That is the first code change the layer
needs, and it is in the sampler, not in the layer.

Consequences to design for, not discover:
- A pinned length is a premise Stage 6 must keep, so minimization must not drop the scale.
- Two independent pinned lengths over-determine a figure and will often be inconsistent; pin **one**
  and derive the rest.
- `GENERATION.max_givens`' sweep (docs/07 T26) measured that extra givens add easy goals rather than
  hard ones. Adding a length given is not exempt from that and must be measured the same way.

## 10.7 Region algebra

The target region is part of the *question*, so it must be represented explicitly and rendered, never
inferred from the answer.

```
Region := Triangle(p, q, r)
        | Sector(centre, from, to, radius)      # needs a resolved, undirected angle
        | Polygon(p1..pn)                       # fan-decomposed into triangles
        | Difference(Region, Region)            # segment = Sector - Triangle
        | Union(Region, Region)                 # disjointness is a proof obligation
```

Each leaf's area comes from a primitive in §10.5's table. `Union` requires certified disjointness;
absent that, refuse. `Difference` requires certified containment. These obligations are geometry and
therefore the **engine's** to discharge, not the layer's — which is the contract in §10.3 applied to
the region algebra itself.

## 10.8 Validation, well-posedness, and the gap

- **Numeric check**: shoelace over reference coordinates, exact-vs-float within `config` tolerance.
- **Well-posedness**: Stage 8 resamples the construction; the layer's value must be **invariant**
  across resamples, and dimensionally so — the ratio of area to (pinned length)² is what must hold
  fixed, not the area itself.
- **Cross-engine validation — the gap, stated plainly.** `bank/validate.py` re-derives *engine* facts
  on a second engine. It does not and cannot re-derive a layer computation, so a layer arithmetic bug
  is invisible to the mechanism that catches every other class of error (docs/07 T14 already limits
  what that validator certifies). The layer needs its own independent second route — recomputing the
  region by a different decomposition and comparing exactly is the cheapest candidate. **UNVERIFIED**:
  whether a second decomposition is always available.
- **`Fact` accepts a surd today.** `Fact(kind=CONSTANT_LENGTH, value=sympy.sqrt(2))` is accepted by
  `solvers/types.py`, which does not enforce the `Fraction` constraint the engine imposes (docs/03
  §3.7a). The layer will eventually need that permissiveness; until then it is an unguarded gap, and
  the fix is to validate against the quantity type's exactness class at construction time.

## 10.9 Answer policy and UX

docs/07 T8 already settled the shape and it is unchanged: **decimal input within a per-puzzle
tolerance, with the exact surd revealed on solve.** Structured exact-form entry (`a + b√c` fields) was
rejected as hostile on mobile and as gatekeeping on notation rather than on geometry. `√3` is entered
as `1.73`; the solve screen shows `√3`.

This is also where area repays the most: **`2π/3 − √3` cannot be read off a to-scale figure.** The
guessability failure that invalidated the first bank (docs/07 T5) does not have an analogue here, so
filter 8's answer-entropy cap should bind far less — but that is a prediction, and it is to be
measured, not assumed.

## 10.10 Build order

Each step is independently verifiable and each has a kill condition.

| step | deliverable | kill condition |
|---|---|---|
| ~~A1~~ | **DONE 2026-08-05 — see §10.10a. Its sampling half is superseded by §10.10b.** | — |
| ~~A2~~ | **DONE 2026-08-05 — module built and tested; see §10.10b.** Its kill condition *fired* and the fix is A1b | ~~the engine does not certify enough lengths per figure to close a triangle~~ **THIS HAPPENED** |
| ~~A1b~~ | **DONE 2026-08-05 — see §10.10d.** Extended to seven templates and the cevian rule in §10.10e | ~~templated figures fail Stage 8 well-posedness or collapse to one answer~~ **neither happened** |
| ~~A3~~ | **DONE 2026-08-06 — see §10.10f.** Registered in the QTR; reaches Stage 6. Discarded at Stage 7 for want of a translation table, which is A4 | ~~answers cluster the way ratio's did~~ **6.0% modal share against angle's 36.0%** |
| A4 | Translation templates for the five area routes and the answer path, then `Sector`, `Difference`, and the configuration-fact angle resolution of §10.5 | configuration facts do not pin the undirected angle often enough to be worth it |
| A5 | Arc length, perimeter, curvature — all reuse A4's machinery | — |

**Acceptance for the layer as a whole:** ≥1 irrational answer per band; modal answer share below
angle's 36.0%; every emitted area independently re-checked; determinism unchanged; and a bank built
without the layer still builds.

## 10.10a A1 as built (2026-08-05)

The figures an area question can be asked about, plus the scale it needs. Landed as an `area`
*sampling profile* — `Band` is `str` and `profile_for` falls back to easy for anything unknown, so
the four difficulty bands are untouched.

**What went in.** Two new `ConstructionDef` flags, `bounds_region` and `states_length_value`, both
named explicitly rather than derived from predicate heads — a trapezoid declares `para` and a square
declares `cong`, exactly like a dozen primitives that bound nothing, and deriving the circle flag from
predicates is what produced the first bank (docs/09 P3 M4). Two new `BandProfile` weights
(`region_weight`, `length_weight`), both defaulting to 1.0. `require_length_given` forces one
length-stating step into a grown construction, and `max_length_givens` appends one `lconst` to a
seeded skeleton.

**Why the forced step, and not just the weight.** MEASURED: at `length_weight = 10.0`, only **78 of
200** area-profile constructions pinned a scale. That is the same failure `require_angle_given`
already records — a weighted draw that misses never comes back to it. An area over an unpinned figure
has no determined answer at all, so this is a correctness requirement, not a yield tweak.

**Measured, seed 42:**

| | before | after |
|---|---|---|
| constructions containing a region | 10–20 draws per 300 (weight 1.0) | **198/200** |
| constructions pinning a scale | 0 | **200/200** |
| both (the minimum for an askable area question) | 0 | **198/200** |
| area-profile constructions that realize | — | **120/120, zero failures** |

Declared fact supply on realized area figures, per figure: `cong` 4.14, `perp` 1.77, `para` 1.48,
`aconst` 1.23, `lconst` 0.78, `l2const` 0.61. Every input the §10.5 triangle primitives need is
present — ½ab·sin C wants `aconst` plus two lengths, Heron wants three, ½·base·height wants `perp`.

**The four difficulty bands are provably unchanged**: sha256 over 200 constructions each is
byte-identical before and after (`easy f642c9b1…`, `medium 9162e3c2…`, `hard ede47bca…`,
`expert 191ba3df…`). `max(circle, angle, region, length)` reduces to the old `max(circle, angle)`
when the two new weights are 1.0.

**A trade-off this exposed, to be settled at A4, not now.** Area-profile figures are polygon-rich and
**circle-poor**: `cyclic` runs 0.09/figure here against 4.00/figure on seeded skeletons, because
`circle_weight` is 8 rather than expert's 20 and the regions crowd in. That is right for A2, which
only needs triangles — but **sectors, arcs and segments need circles with named centres**, so A4 will
need either its own profile or seeded skeletons rather than grown ones. Do not raise
`circle_weight` on the `area` profile to fix this without re-measuring the region rate: at 20 the two
circle primitives took 555 of ~1000 sampled steps.

## 10.10b A2 as built, and the finding that redefines A1 (2026-08-05)

`generator/area.py` is built, tested (23 tests) and type-clean: three primitives, exact SymPy,
shoelace verification that **raises** on disagreement, and the mod-π invariance of ½ab·sin C
asserted by a parametrised test rather than assumed.

**Then it produced zero areas on 150 real area-profile figures.** A2's own kill condition, fired
on the first honest measurement. The diagnosis matters more than the module:

1. **The pin dangles.** `lconst f d 4` introduces a *fresh* point `f` that participates in nothing
   else. MEASURED: 27 of 40 figures carry exactly one declared length fact, and only **6 of 40**
   have two pinned segments sharing an endpoint — the minimum a triangle needs.
2. **Scale does not propagate.** In a sample figure, exactly **one** segment in the whole diagram
   had a known length: the pin itself. `lconst` holds a `Fraction`, so from one pinned length the
   engine reaches only rationally-related lengths — via `cong` (equal) or `midp` (half). This is
   docs/07 T21's "powers of 2" wall, reappearing for lengths instead of ratios.
3. **The deepest reason, and the one that changes the design: a generically-grown region has no
   determined area at all.** `on_tline c a a b` places `c` on a perpendicular but leaves `|ac|`
   free, so triangle `abc`'s area is not a function of the givens. There is nothing for any layer
   to compute, and Stage 8 well-posedness would reject it regardless.

**So area cannot come from weighted random growth.** It needs constructions whose region is pinned
by design. MEASURED over four templates, 25 instantiations each, values drawn at random:

| source | areas computed | irrational | distinct values | modal share |
|---|---|---|---|---|
| random clause growth (the A1 profile) | **0 / 150** | — | — | — |
| pinned templates | **95 / 100** | 61 | **38** | **10.5%** |

Against angle's 9 distinct values at 36.0% modal share, that is a decisive improvement on exactly
the guessability metric that invalidated the first bank (docs/07 T5) — and the values are the ones
no engine can represent: `5√3/2`, `25√2/4`, `6√3`, `9√2`, `3√3/2`.

The four templates, with what each buys:

| template | JGEX shape | yields |
|---|---|---|
| SAS | `a = free a; b = lconst b a P; c = s_angle b a c THETAo, lconst c a Q` | 25/25, 16 irrational — the workhorse |
| equilateral | `a = free a; b = lconst b a P; c = lconst c a P, lconst c b P` | 25/25, **all irrational** — (√3/4)P² |
| isosceles | `a = free a; b = lconst b a P; c = lconst c a P, lconst c b Q` | 20/25, all irrational |
| right legs | `a = free a; b = lconst b a P; c = on_tline c a a b, lconst c a Q` | 25/25, **0 irrational** — ½PQ is rational, so this is easy-band filler |

**A1's flags and weights are still right and stay** — `bounds_region` and `states_length_value` are
what a template selector reads, and the four difficulty bands remain byte-identical. What is
superseded is the assumption that *weighting* a random walk would produce askable area figures.
It produced figures containing regions, which is what §10.10a measured and claimed, and none of
those regions had a determined area — the gap between those two statements is the lesson.

**This is docs/07 L4 again** ("the difficulty ceiling is the generator"), in a new quantity type:
random clause growth cannot produce the deliberate arrangements a good puzzle needs. The response
here is the same one docs/09 P5 reaches for — a reviewed library of archetypes — at much smaller
scale, because an area template is four clauses rather than a competition configuration.

## 10.10c Decomposition: what makes a decorated template a puzzle (2026-08-05)

§10.10b asked whether a template with structure grown on top still has a determined area. It does
not, by the direct primitives — **0 of 20** on every decorated case:

| case | direct primitives | with decomposition |
|---|---|---|
| base (the pinned triangle itself) | 20/20 | 20/20 |
| + midpoint of a side | **0/20** | **20/20** |
| + two midpoints | 2/20 | 20/20 |
| equilateral + midpoint | **0/20** | 20/20 |
| right triangle + midpoint | **0/20** | 20/20 |

**Why the direct route fails, and why it is not fixable by trying harder.** For the sub-triangle
`abm` with `m` the midpoint of `bc`: `|bc|` is irrational (law of cosines on the pinned SAS), so
`|bm| = |bc|/2` is unreachable and the median `|am|` more so. `lconst` holds a `Fraction` and
cannot express any of them. Asking the engine for those lengths asks its predicates for values
they cannot hold — the same wall as docs/07 T21.

**None of it is needed.** If `m` is the midpoint of `bc`, then `abm` and `abc` share the apex `a`
and the second has twice the base, so `[abm] = ½[abc]` **exactly** — an area-*ratio* argument over
certified structure, using no length at all. Verified against the diagram on 6 of 6 instantiations
before a line of it was written, then on 20 of 20 after.

This is the Chou–Gao–Zhang area-method idea that docs/03 §3.7 names as a candidate *engine*, used
here as a decomposition rule instead. `AREA.max_decomposition_depth` bounds the recursion — a
requirement, not tidiness, since mutually-recursive midpoint facts would otherwise spin, and the
bound doubles as a difficulty knob because each level is one ratio step in the solution.

**Answer quality across all five cases: 100 areas, 45 distinct values, 6.0% modal share** —
against angle's 9 values at 36.0%. Sample: `2√3`, `√3/2`, `9√3/2`, `5√3/2`, `3/2`, `5`.

Note the `right+mid` row yields **0 irrational** — ½·p·q halved is still rational. It is honest
easy-band filler, not a defect, but a band built only from right triangles would reproduce
angle's guessability problem in a new unit.

## 10.10d A1b as built (2026-08-05)

`generator/templates.py` — a **reviewed** library of six area archetypes and `draw_area`, which
replaces weighted random growth as the source of area figures. Reviewed is load-bearing here for
the same reason it is for the translation table and the configuration library: a template nobody
has checked is a figure nobody can vouch for, so each entry records what it yields.

| template | region | steps | irrational |
|---|---|---|---|
| `sas` | the pinned triangle | 1 | yes |
| `equilateral` | the pinned triangle | 1 | yes |
| `right_legs` | the pinned triangle | 1 | **no** — ½pq over integers |
| `sas_median` | sub-triangle at a midpoint | 2 | yes |
| `equilateral_median` | sub-triangle at a midpoint | 2 | yes |
| `sas_two_medians` | sub-triangle at two midpoints | 3 | yes |

**MEASURED, 300 draws at seed 42:**

| | |
|---|---|
| realized | **300/300**, zero failures |
| area computed | **300/300**, zero verification errors |
| irrational | 201 (**67.0%**) |
| distinct values | **65** |
| modal share | **6.0%** (angle: 36.0%) |

`TEMPLATE_ANGLES` excludes 90° deliberately: a right angle makes the SAS area rational *and* is
its own supplement, which is how two separate defects hid themselves before (ONBOARDING gotcha 6).
Multiples of 30 and 45 stay in, because an area of `5√3/2` is not sight-readable just because the
angle behind it was 60°.

**Well-posedness — the gate §10.10c left open — passes.** A template claims to *pin* its region,
so the area must be the same number in every figure the construction realizes to; a value that
moved with the seed was never determined by the givens. Asserted per template across four seeds,
and `area_of` verifies against each diagram along the way, so the test also re-checks the exact
value four times over. All six hold.

**Still open, and now the honest ceiling.** These are two- and three-step puzzles with irrational
answers and 6.0% modal share — a real improvement on angle, and genuinely not sight-readable. They
are **not olympiad problems**. The region is stated plainly and the solver's work is "recognise the
median, halve the area". Making them hard needs the region *hidden* — asked about a sub-figure the
solver must first identify — which is the same hide/rediscover mechanism docs/07 T26 records as
capped at ~1.8% for auxiliary points. Nothing here shows that transfers to regions; it is the next
thing to measure, not to assume.

## 10.10e The cevian rule, and the seven-template library (2026-08-06)

§10.10d's ceiling was that the construction to discover was always "the midpoint of BC". One rule
changes it to "the intersection of two medians".

**The rule.** Triangles `ABP` and `ABX` share the base `AB`, so their areas are in the ratio of the
apexes' distances from `AB`. If `P`, `X`, `Y` are collinear with `Y` on line `AB`, that ratio is
`PY/XY` — again with no length involved, which is what makes it usable at all, since every length in
these figures is irrational.

**Why the arithmetic has to be ours, measured rather than assumed.** The engine certifies
`rconst X P P Y` (`|XP|/|PY| = k`) but **cannot** certify `rconst P Y X Y = 1/(k+1)`: AR chases
ratios *multiplicatively*, and getting from `XP/PY` to `PY/XY` needs `XY = XP + PY`, an **addition**
it does not do. MEASURED on a centroid figure — `rconst c g g m 2/1` proves, `rconst g m c m 1/3`
does not. That single addition is exactly the arithmetic-on-certified-quantities docs/07 T6 permits,
and it is what unlocks the centroid: `[ABC] = 6√3` → `[ABG] = 2√3` via `area_cevian_split`.

**The configuration assumption, stated rather than hidden.** `PY/XY = 1/(k+1)` assumes `P` lies
*between* `X` and `Y`; outside that segment the relation differs, and betweenness is a configuration
fact (docs/07 T2) that is not always certified. The rule is sound because `verify` checks the result
against the reference diagram and raises on a mismatch — templates are reviewed so their
configuration is known-good, and a figure from anywhere else fails loudly rather than shipping a
wrong answer.

**MEASURED, 210 draws over the seven-template library, seed 42:**

| | |
|---|---|
| areas computed | **210/210**, zero verification failures |
| irrational | 144 (**69%**) |
| auxiliary construction required *by design* (docs/07 T29) | 121 (**58%**) |
| routes | `median_split` 90, `heron` 33, `cevian_split` 31, `sas` 29, `right_triangle` 27 |

Example of the genre this reaches: show `A B C M N`; state "G is the intersection of lines CM and
AN"; ask for `[ABG] = 3√2`.

`sas_centroid` is the seventh template, and `cevian_ratio_candidates()` proposes the ratios the
engine *derives* but never *declares*. Proposing is all it does; the engine decides
(docs/02 invariant 4).

**An integration gap this surfaced, recorded because the tests now exercise it rather than route
around it.** The layer needs **derived** facts, not just `figure.declared` — the cevian ratio is
never declared by any construction. Three `sas_centroid` tests failed for exactly that reason and
were fixed by enriching through the same path the pipeline must, not by weakening the assertion.

## 10.10f A3 as built (2026-08-06)

`area` is registered in the QTR and reaches Stage 6. The work was almost entirely in **removing the
registry's assumption that every quantity is an engine predicate**, which is the assumption docs/04
§QTR exists to prevent and which had gone unnoticed while `angle` was the only registration.

**Three §QTR signatures were widened, in this order, each because the next one blocked:**

| field | was | is | why |
|---|---|---|---|
| `goal_extractor` | `Callable[[Coords], ...]` | `Callable[[FigureView], ...]` | an area is computed from *certified facts*; a coordinates-only extractor would have to re-derive geometry from numbers, which docs/02 invariant 4 forbids |
| — | (none) | `verifier: Verifier` | there is no engine call to make — no engine in the lineage has an area predicate |
| `format_answer` | `Callable[[Fraction], str]` | `Callable[[Fact], str]` | an area's value is a surd and cannot be a `Fraction` at all, which is the entire reason the layer exists |

**The fact vocabulary.** `FactKind.AREA` and a second value field `Fact.exact: str | None`, holding a
SymPy expression string. A second field rather than widening `value`, because the two mean different
things and the difference is the whole point: `value` is what an *engine predicate* can hold, and
every engine in the lineage holds a rational (docs/07 T18, T21) — which is exactly why no angle
puzzle can ever answer `√3/2`. `LAYER_KINDS` names the kinds no engine can express, and
`PremiseSpec.__post_init__` **refuses** one at the seam; a backend handed an area would otherwise
fail deeper down as an `UnsupportedFactKind` or, worse, a silent `dropped_assumptions` entry.

**The derivation.** Everything after Stage 5 is written against a proof DAG, and an area has no
*engine* proof. Rather than teach traceback, translation, pruning and scoring about areas, the layer
emits its own: `AreaResult` gained `region` and `parents` so a decomposition is a tree rather than a
flattened value, and `area.proof_dag()` renders that tree as `ProofStep`s whose `rule_id` is the
route name. Those five names — `area_right_triangle`, `area_heron`, `area_sas`, `area_median_split`,
`area_cevian_split` — are public API under CLAUDE.md's step-`rule` rule from this commit.

**Two consequences that had to be handled rather than deferred:**

1. **Each route now reports precisely the facts it consumed.** The previous `_facts_used` pooled
   "every fact wholly about this triangle", which is over-collection: those become the puzzle's
   *stated givens*, and docs/05 filter 5 treats a stated-but-unused given as a build-failing bug
   rather than as attrition.
2. **`derive` skips premise minimization for a layer goal.** `minimize_premises` asks the engine
   "does the goal still follow without premise X?", and there is no engine to ask. Nothing is lost:
   because of (1), every surviving premise is dereferenced by some step, so a greedy pass has
   nothing to drop. `test_a_layer_derivation_is_already_minimal` pins that, so the day a route
   starts over-collecting, this stops being true *out loud*.

`verify` now checks **every node** of the decomposition, not just the answer. A wrong intermediate
that a later step happens to cancel would otherwise ship a correct number attached to a solution
that does not hold — and the solution is what the player reads.

**MEASURED, 60 template draws at seed 42, area goals through Stage 6:**

| | |
|---|---|
| proposals | 200 |
| accepted as goals | 136 (the other 64 are `surplus`, the per-construction cap) |
| `not_verified` / `engine_error` / area verification failures | **0 / 0 / 0** |
| reached a minimized derivation | **136/136** |
| derivation depth | 1: 40, 2: 48, 3: 48 |

Every premise set came back exactly the facts the routes dereference. Sample:

```
[a b n] = 25*sqrt(2)/16   depth 3   area_sas -> area_median_split -> area_median_split
  premises: aconst a b a c = 3/4; lconst a b = 5; lconst a c = 5; midp m b c; midp n b m
[a b c] = sqrt(3)         depth 1   area_heron
  premises: lconst a b = 2; lconst a c = 2; lconst b c = 2
```

**The four difficulty bands are provably unchanged by the registration**: the seed-42, n=200
attrition report is identical field-for-field with `area` registered and with it absent. Grown
angle-profile figures certify too few lengths for the layer to find anything, so `propose_areas`
returns empty and nothing downstream sees a new candidate.

**Where A3 stops, precisely.** An area goal is proposed, verified, traced and minimized. It is then
discarded at Stage 7, because `translate` has no template for the five route ids and `angle_of`
cannot read an area as an answer. That is counted attrition with a named reason, not a crash. A4
closes it, and the remaining work is the translation table plus generalizing the answer path — not
another §QTR widening.

## 10.11 Deliberately not in scope

- **The Chou–Gao–Zhang area method** as a second SAL backend (docs/03 §3.7). It proves area statements
  natively and yields short readable proofs, but it is a different engine, not an extension — adopting
  it is a docs/07 entry and an SAL backend, and it should be judged against A2's measured results
  rather than ahead of them.
- Conics, 3D, and anything needing a predicate no engine has (docs/07 T9).
- Using the layer to *derive* geometry. If a question needs a fact the engine cannot certify, the
  question is out of scope — that is docs/07 P3 applied to ourselves.
