# Phase 0 Gate Report

**Date:** 2026-08-01 · **Verdict: PROCEED to Phase 1**, with four design amendments below.
All numbers come from runs recorded in `out/`; nothing here is estimated.

## Environment (verified)

`uv 0.12.1` · Python **3.12.13** in a project-local `.venv` · `newclid==3.0.1` (+ `pyyaml`,
see BUG-0) · `py-yuclid==3.0.0` installed from a **prebuilt wheel — no cmake/Boost needed**.
System Python is untouched (`import newclid` there still fails, as intended).

---

## Headline results

| Spike | Question | Result |
|---|---|---|
| S1 | Do the engines solve our problem class? | Yuclid **11/23**, pure-Python **8/23** on a deliberately hard, circle-heavy set. Failures are informative, not fatal (below) |
| S1b | Can we extract numeric quantity goals **without** `acompute`? | **Yes — the central result.** 4/6 verified; the 2 "failures" are *correct* rejections of underdetermined angles |
| S2 | Can proof traces become player-readable steps? **(THE GATE)** | **86%** of steps translate; **82%** of puzzles fully translate at AR-budget 5 (46% at the budget our docs assumed) |
| S3 | Does a deterministic sample→saturate→enumerate loop work? | **6/6** saturated on Yuclid; two runs at the same seed are **byte-identical** |
| — | Cross-validator vendored? | Yes, AG2 DDAR runs; **its angle convention is inverted vs Newclid** |

---

## 1. Three upstream bugs found in newclid 3.0.1

All three are in the **pure-Python** path. Upstream CI builds the Yuclid C++ backend, which
replaces both the AR deductor and the rule matcher — so this path is effectively untested
upstream. Present in both the PyPI wheel and the git clone (`ac65507`).

| id | Defect | Impact |
|---|---|---|
| **BUG-0** | Published wheel metadata omits `pyyaml`, which `newclid/rule.py` imports | `import newclid` fails on a clean install |
| **BUG-1** | `ar_predicates.enumerate_lconsts` iterates `expected_lconsts.copy()` (a `dict[Symbol, float]`) and unpacks each item as a pair → `TypeError` on every call | Kills any problem whose AR ratio table holds a length constant (most distance-touching problems). **One-line fix** (`.items()`) — patched in `newclid_patches.py`; unlocked 2 problems immediately |
| **BUG-2** | `MappingMatcher` treats numeric constants in rule variables as point names → `KeyError: '1/2'` / `ValueError: too many values to unpack` | Pure-Python matcher cannot apply any rule containing a constant (midpoint-ratio, right-angle rules…). Not patched — this is a design-level defect, and it is the reason pure-Python is not viable as the primary backend |

**Consequence:** the pure-Python backend is *not* production-viable for us. That inverts the
Phase-0 assumption that we would avoid Yuclid.

## 2. Yuclid is the primary backend (Decision 3b resolved)

| | pure-Python | Yuclid |
|---|---|---|
| Solved (23 problems) | 8 | **11** |
| `circum_right_angle` run time | 0.548 s | **0.024 s** (23×) |
| `pentagon_star_circum` run time | 2.852 s | **0.111 s** (26×) |
| Trivial problems | faster | ~13–15 ms subprocess floor |
| `acompute`/`lcompute` goals | supported (but buggy) | **rejected** |
| Rule-matcher bugs | BUG-2 | none observed |

Yuclid wins on both speed (23–26× where it matters) and correctness. Its one limitation —
no `acompute` — is neutralised by S1b.

**Performance question answered:** no Rust/Go/C++ work is justified. The hot path is already
C++ (Yuclid); our orchestration is negligible; 95% of wall time is inside the engine.

## 3. S1b — goal extraction without `acompute` (the enabling result)

We replicate what `acompute` does internally: measure the quantity on the reference diagram,
snap it to a rational via `get_quotient`, then ask the engine to **symbolically verify** the
explicit `aconst`. Soundness stays symbolic; numerics only propose.

| case | measured | verified (Yuclid) |
|---|---|---|
| equilateral triangle angle | 120.0000° = 2/3·π | ✅ |
| central angle | 30.0000° = 1/6·π | ✅ |
| Thales semicircle | 90.0000° = 1/2·π | ✅ |
| inscribed, same arc | 50.0000° = 5/18·π | ✅ |
| tangent–chord (free point) | 161.0174° = 17/19·π | ❌ *correct rejection* |
| circumcentre bridge (free point) | 65.4457° = 4/11·π | ❌ *correct rejection* |

The two rejections are the desired behaviour: both angles are genuinely **not determined** by
the premises (a free point on a circle), and their measured values are ugly rationals — so the
"nice value" filter and the well-posedness gate both fire for free. Behaviourally: **6/6 correct.**

Note `acompute` itself *failed* on the equilateral case in S1 while the explicit `aconst`
form succeeded — further reason to avoid the predicate entirely.

## 4. S2 — the readability gate

Corpus: 11 solved problems, 95 proof steps, **only 13 distinct engine rules fired** (the
translation whitelist is small and tractable — the top 3 rules cover 42 of 58 rule steps).

Sensitivity to the AR-chain budget (`docs/03 §3.5` assumed 3):

| max AR premises | 2 | 3 | 4 | **5** | 7 | 14 |
|---|---|---|---|---|---|---|
| puzzles fully translatable | 27% | 46% | 55% | **82%** | 91% | 100% |
| steps translatable | 78% | 86% | 90% | **96%** | 99% | 100% |

**Gate passes at budget 5 (82% ≥ 80%).** Two further findings make this stronger than the
raw numbers suggest:

**(a) Translation is compression, and the patterns are systematic.** A 10-step machine proof
of Thales maps to a 4-step human solution. The recurring idiom — an AR ratio restatement, then
`SAS Similarity (Reverse)` of a triangle **with itself**, then `Properties of similar
triangles` — is always just "isosceles ⇒ base angles equal". It appears 15 times in 95 steps.
The translator must therefore collapse *idiom patterns* → one readable step, not map 1:1.

Worked example (`thales_semicircle`, machine → human):
```
000-002  CO=AO → ratio → ▲ACO≅▲CAO → ∠(AC,AO)=∠(CO,AC)   ⇒  "OA = OC, so triangle OAC is
003-005  O midpoint → AB:AO=2 → AB:BO=2 → BO=CO               isosceles: ∠OAC = ∠OCA."
006      BO=CO → ∠(BC,BO)=∠(CO,BC)                        ⇒  "Likewise ∠OBC = ∠OCB."
007-008  midpoint → collinear → BO ∥ AO                    ⇒  (structural, invisible)
009      AR(3) → ∠(AC,BC) = 1pi/2                          ⇒  "The angles of ABC sum to 180°,
                                                               so ∠ACB = 90°."
```

**(b) Directed-angle conversion is universal, not occasional.** **48 of 48** angle facts are
directed line-to-line angles `∠(XY,ZW)`, never human vertex angles `∠ABC`. Every published
solution line needs conversion, disambiguated by configuration predicates. This confirms the
planning-stage risk and promotes it from "a translator responsibility" to *the* translator's
central job.

## 5. S3 — generation loop

Goal-free build → saturate → read `proof_state.graph.hyper_graph`. On Yuclid: **6/6**
constructions saturated, 43–75 facts each; two runs at seed 42 produced **byte-identical**
JSON. On pure-Python: 0/6 (BUG-2).

Caveat that changes Stage-5 design: saturation surfaced only **3 explicit `aconst` facts
across 6 constructions**. The closure rarely *derives* numeric constants spontaneously. So
goal extraction must be the **S1b numeric-propose/symbolic-verify sweep** over candidate point
tuples, with closure-scanning as a secondary source — not the reverse.

## 6. Cross-validator

AG2 DDAR vendored to `vendor/ag2_ddar/` (Apache-2.0, verbatim, provenance recorded) and smoke
tested: `acompute` returns `Fraction(2,3)` for an equilateral configuration.

⚠ **Its directed-angle orientation is inverted relative to Newclid.** A cross-validator that
assumed matching conventions would report a soundness failure on *every* puzzle. Calibration
belongs in the adapter. Full cross-validation of S1 problems is **deferred to Phase 1** (it
needs the coordinate exporter); this is honest scope, not a silent skip.

---

## Verdict and required amendments

**PROCEED.** Readability is achievable, goal extraction works, the loop is deterministic.
Four amendments to the docs:

1. **Yuclid is the primary backend**, pure-Python a debug-only fallback (`docs/03 §3.2`) —
   with the S1b pattern replacing `acompute` (`docs/04` Stage 5).
2. **`max_ar_chain` = 5, not 3** (`docs/03 §3.5`), justified by the sensitivity curve.
3. **Translator collapses idiom patterns** and **converts directed line-angles to vertex
   angles for every published step** (`docs/03 §3.5`).
4. **Dependency policy holds but with eyes open**: newclid stays a pinned dependency, plus a
   small `newclid_patches` module we own. Upstream's pure-Python path is under-tested, so the
   patch module is permanent infrastructure, not a stopgap (`docs/07` P1).

## Reproduce

```bash
cd spikes/p0
uv run python s1_solve.py --compare-yuclid   # solve rates + timing split
uv run python s1b_aconst_probe.py            # goal-extraction mechanism
uv run python s2_traces.py --backend yuclid --max-ar-chain 5   # the gate
uv run python s3_generate.py --seed 42 --n 6 --backend yuclid --out out/a.json
```
