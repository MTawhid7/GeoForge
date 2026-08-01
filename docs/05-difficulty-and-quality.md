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
- `width` — total rule applications.
- `distinct_rules` — conceptual variety (five uses of triangle-angle-sum is easy even at depth 5).
- `tier_max`, `tier_mix` — rule families used (circle theorems feel harder than supplementary angles);
  tiers are assigned in our translation whitelist, not by the engine.
- `branch_join` — DAG joins of independent sub-deductions (strongly felt as "hard").
- `nice_penalty` — subtractive: answer telegraphed by a given, 90°/60° everywhere, symmetric freebies.

Score = weighted sum normalized 0–10 (initial weights in `config/`, including `nice_penalty`'s).
Bands: easy [0,3) · medium [3,5.5) · hard [5.5,7.5) · expert [7.5,10].

**Calibration protocol:** every bank build → stratified 50-puzzle spot check, owner records perceived
band; weight changes must cite a spot-check batch. Replace with solve-time calibration when users exist.

## 5.2 Hard rejection filters (any hit ⇒ discard)

1. `depth < 3` or `distinct_rules < 2` — trivial.
2. Goal one rule away from a given at the same vertex — "read it off the picture".
3. One rule > 60% of applications — monotonous.
4. Figure complexity out of range: < 4 or > 12 visible points; > 2 circles (v1 readability).
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

Keep-rate default: top 40% per band per batch — the main volume/quality knob, governed by the ≤ 5%
trivial/ugly floor (doc 01).

## 5.4 Gem promotion (manual, optional)

Batch report surfaces top-10 by interestingness per band; the owner may set `"featured": true` (feeds the
daily-puzzle slot). No other human curation exists.

## 5.5 Anti-goals

- Never tune difficulty via clutter or confusing labels — difficulty comes from proof structure only.
- No scorer→sampler feedback loops in v1 (band targeting in Stage 1 is the only coupling). Value-guided
  sampling à la TongGeometry is a deliberate later experiment (doc 09 P3), to be adopted by editing this
  doc, not by drift.
