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
| A1 | `sampler.decorate` appends one `lconst` given; measure the effect on yield and answer entropy at seed 42 | scale pinning collapses yield the way `corpus_share` did |
| A2 | `quantities/area.py`: `Triangle` only, three primitives (½ab sin C, Heron, ½·base·height), exact SymPy, shoelace check | the engine does not certify enough lengths per figure to close a triangle |
| A3 | Register `area` in the QTR (`goal_extractor`, `dimension`, `nice_values`, `answer_policy`, `templates`, `marks`) and ship one band | answers cluster the way ratio's did — measure modal share before believing otherwise |
| A4 | `Sector`, `Difference`, and the configuration-fact angle resolution of §10.5 | configuration facts do not pin the undirected angle often enough to be worth it |
| A5 | Arc length, perimeter, curvature — all reuse A4's machinery | — |

**Acceptance for the layer as a whole:** ≥1 irrational answer per band; modal answer share below
angle's 36.0%; every emitted area independently re-checked; determinism unchanged; and a bank built
without the layer still builds.

## 10.11 Deliberately not in scope

- **The Chou–Gao–Zhang area method** as a second SAL backend (docs/03 §3.7). It proves area statements
  natively and yields short readable proofs, but it is a different engine, not an extension — adopting
  it is a docs/07 entry and an SAL backend, and it should be judged against A2's measured results
  rather than ahead of them.
- Conics, 3D, and anything needing a predicate no engine has (docs/07 T9).
- Using the layer to *derive* geometry. If a question needs a fact the engine cannot certify, the
  question is out of scope — that is docs/07 P3 applied to ourselves.
