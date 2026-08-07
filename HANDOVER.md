# Handover — the area layer, built and shipped

**Written 2026-08-06.** Branch `feat/area-layer`, **committed, fully verified, pushed.**
Read this with `ONBOARDING.md` (current state, verified commands) and `docs/10-area-layer.md`
(the area layer's full record, §10.10a–i). This file is the session-to-session context those
two do not carry.

---

## 1. The state you are inheriting

Unlike the previous handover, **there is nothing to finish verifying.** The branch is clean.

| | |
|---|---|
| `git status` | clean, nothing uncommitted |
| Branch | `feat/area-layer`, 15 commits ahead of `main`, pushed to `origin` |
| `ruff check` / `ruff format` | clean |
| `mypy --strict` | clean, 43 source files |
| Full `pytest -q` | **green, exit 0** (run on an idle machine at `33623a0`) |
| Determinism, `PYTHONHASHSEED` 0 vs 99991 | identical |
| Angle bands vs pre-area baseline | **byte-identical** — none of this moved an angle puzzle |
| Web suite (`tsc`, eslint, vitest, playwright) | **not run** — no frontend change was made |
| `make bank` on area puzzles | **never run** — see §5 |

**One environment gotcha that cost 30 minutes:** never run two `pytest` suites at once. They
contend for the engine subprocesses and both appear to hang. `ONBOARDING.md` §6a says this;
believe it. `pkill -f pytest` if you suspect it.

---

## 2. What was built

`area` is a fully registered quantity type, end to end. Eight commits:

```
33623a0  feat(templates): pin the triangle by a side, not by an angle
cefe759  feat(generator): a Claim replaces VertexAngle, and the first area puzzles
b4d8bbb  feat(schema): parse_exact carries surds, as its own docstring promised
c41289d  feat(translation): area steps clear the readability gate
4a26f11  feat(generator): register `area` in the quantity-type registry
93b232e  feat(area): the layer emits its decomposition as a proof DAG
72743df  refactor(generator): a verifier field on QuantityType
70c242e  refactor(generator): widen goal_extractor to a FigureView
```

Measured, 40 template draws at seed 42:

| | angle (shipped) | area (now) |
|---|---|---|
| answers | rational multiples of π | **96% irrational** |
| distinct answers | 9 | 21 |
| modal answer share | 36.0% | **13.4%** |
| well-posed | — | **82/82 (100%)** |
| auxiliary construction required by design | 0% | **58%** |

A real one:

```
ANSWER 3√3/4   GIVEN  BC = √37; AB = 3; AC = 4; M is the midpoint of AB; N is the midpoint of BC
  BC = √37, AB = 3 and AC = 4, so Heron's formula gives [ABC] = 3√3.
  [ABC] = 3√3 and M is the midpoint of AB, and a median divides a triangle into two of
    equal area, so [BCM] = 3√3/2.
  [BCM] = 3√3/2 and N is the midpoint of BC, and a median divides a triangle into two of
    equal area, so [CMN] = 3√3/4.
```

**The architectural result worth carrying forward:** enabling a quantity *no engine can
evaluate* cost four widened `§QTR` signatures and **zero branches in any pipeline stage**.
That is what `docs/04 §QTR` was written to promise, and it held. The four:

| field | why it had to widen |
|---|---|
| `goal_extractor` → `FigureView` | an area is computed from certified *facts*, not measured off the diagram |
| `verifier` (new) | there is no engine call to make |
| `format_answer` → takes a `Fact` | an area's value is a surd and cannot be a `Fraction` |
| `claim_of` (new) | Stages 8/9 took a `VertexAngle`, assuming every goal is an angle |

---

## 3. The three bugs this surfaced, and why they matter

Every real defect was a **silent gap**, not a wrong answer — each unreachable while `angle` was
the only registered quantity. This is the argument for registering a second instance of any
abstraction.

1. **`schema._EXACT_TERM` matched `-?\d+…`** while `_split_terms` emits every term after the
   first with an explicit `+`. **No multi-term exact value was ever parseable**, since v1.
   Invisible because `angle` cannot produce a sum.
2. **`l2const` had no phrase.** A given with no phrasing makes its whole puzzle unshippable.
   Invisible because no template stated one until A5.
3. **`area.proof_dag` emitted no configuration facts**, so Stage 8's `same_configuration`
   accepted *every* resample including mirrored ones.

---

## 4. The lesson that changed the design twice

**Measurement located the bug; reasoning did not.** Twice:

- 70 of 94 area goals were rejected as `step_underdetermined`. It looked like a hard mod-π wall.
  A per-template table showed a perfect split — every template stating an angle lost, every
  template pinning by length passed 100% — and the fix was a template change, not a gate change.
- The area layer's own §10.5 predicted the mod-π hazard would bite *sector area*. It bit the
  **sentence naming the angle** instead, on a primitive the doc had marked safe. The value was
  invariant exactly as designed; the prose was not.

Corollary that is now a test: **a gate passing at 11% is worse than one passing at 0%.**
`sas_centroid` passed 3/27 *by luck* — Stage 8 resamples a fixed number of times and the
ambiguity was structural. Retired, with `test_no_template_states_an_angle` asserting it.

---

## 5. Where to pick up — in priority order

The target genre is the Aggvent / Catriona Shearer calendar: ~31 puzzles, nearly all "find the
shaded area". Catalogued against what GeoForge can express (see §6 for the caveat):

| region type needed | count | status |
|---|---|---|
| polygon dissection (squares, rectangles, parallelograms) | ~14 | **not built — no research needed** |
| circle / semicircle / sector / lune | ~12 | designed (§10.5), vocabulary gap |
| regular hexagon / octagon | ~3 | no JGEX primitive |
| triangles only | ~2 | **works today** |

**Today GeoForge can express roughly 0–2 of 31.** The machinery is right; the region
vocabulary is the gap. Recommended order:

1. **Polygon regions.** Fan-decompose a polygon into triangles and reuse the five existing
   routes. Unlocks ~14 of 31, needs no new engine capability, and `AREA.max_region_vertices = 6`
   is already in config and unused. Highest leverage remaining.
2. **Invariance as a scored signal.** Stage 8 already resamples and checks the answer does not
   move — which *is* the genre's punchline ("the answer is the same wherever you put the
   point"). `docs/05` §5.3 records that this information is computed and discarded. Nearly free.
3. **Sectors and segments.** ~12 more. Handle the mod-π resolution up front this time; §10.5
   specifies it and A5 is the cautionary tale for ignoring it.
4. **A6 — wire `cevian_ratio_candidates` into the batch runner.** Small. The cevian rule needs a
   ratio the engine *derives* but never *declares*, so no centroid puzzle currently reaches the
   pipeline — and `sss_centroid` is the best construction in the library to have to discover.
5. **Hide the region, not just a point.** `docs/07` T29 hides `M`; the question still names its
   region. This is the `docs/10` §10.10d ceiling and it is untouched.
6. **`make bank` on an area band.** Never run. Expect real work: the cross-engine validator
   re-derives *engine* facts and is structurally blind to layer arithmetic (§10.8), so the
   shoelace check is the only thing standing there.

---

## 6. Two things I would not trust without re-checking

- **The 31-puzzle catalogue in §5 is my read of low-resolution thumbnails**, ±2 per row.
  Classify the calendar properly before committing to that ordering.
- **`area_cevian_split` has never fired end to end.** It is unit-tested and `sss_centroid` draws
  and realizes fine, but item 4 above is why no puzzle has exercised it in the pipeline. Do not
  assume the route works in situ until a batch run shows one.

---

## 7. Honest assessment of progress

Split, because a single number would mislead:

| | done |
|---|---|
| Pipeline infrastructure (sampler → SAL → extract → traceback → translate → wellposed → emit → bank, schema, frontend, cross-engine validation) | ~85% |
| Quantity machinery (registry proven generic; exact irrational values end to end) | ~80% |
| Region vocabulary (triangle only, of triangle/polygon/sector/segment/annulus) | **~20%** |
| Difficulty generation (aux-by-design works at 58%; *insight* generation does not exist) | **~15%** |
| Against the Aggvent calendar | **~5%** |

**~35% overall, and the remainder is not evenly distributed** — most of the plumbing is behind
us, most of the hardness is ahead.

**The open problem, stated plainly.** Aggvent puzzles are not hard because of the *shape*. They
are hard because of a hidden relationship — two regions secretly equal, or an answer that does
not depend on a free point. We have no mechanism that generates that. Current difficulty is
"recognise that a median halves the area": one named lemma. **Shape vocabulary is engineering;
insight is unsolved**, and item 2 in §5 is the only concrete lead we have toward it.
