# 01 — Project Overview

## Vision

GeoForge generates an unlimited supply of valid, well-posed, non-trivial Euclidean geometry puzzles —
**find an unknown quantity: an angle, a length, a ratio, a shaded area…** — with machine-verified,
human-readable step-by-step solutions, presented in a clean Euclidea-like web app. The pipeline, schema,
and gates are designed **quantity-generic** from day one; quantity types are *enabled* in phases (angles
first) as engine support and answer-input UX mature (doc 09). Curated collections (books, sudokuwiki-style sites, puzzle YouTube channels) are
excellent but finite; GeoForge removes that ceiling.

**Strategy (2026 pivot):** we assemble the reasoning core from mature open-source systems — the
AlphaGeometry lineage, specifically **Newclid/Yuclid** as the engine and **AlphaGeometry 2 DDAR** as an
independent validator — and build only what no existing system provides: the puzzle-forming, quality,
and delivery layers. Rationale and evidence: `research/` (kept as the permanent research record).

## Why this is worth building in the age of frontier LLMs

Frontier models (Claude Fable, GPT-5.6-class, Gemini Deep Think) solve olympiad geometry at gold-medal
level. We do not compete with them, and puzzle *solvability by machines* is irrelevant to the product —
the chess-app precedent: Stockfish surpassed humans decades ago; puzzle/training apps thrive. Our
defensible claims are things LLMs cannot provide:

1. **Validity by construction.** Every puzzle is emitted from a symbolic derivation that *is* its
   solution; correctness is structural, not probabilistic. An LLM generating 10,000 puzzles produces an
   unknowable fraction of subtly broken ones — and detecting them requires exactly the machinery we run.
2. **Trustworthy difficulty.** Bands derived from measurable proof structure, reproducibly. An LLM's
   difficulty label is an opinion.
3. **Zero-marginal-cost delivery.** A pre-validated static bank costs nothing per user, works offline,
   and puts no hallucination risk in any session.
4. **A compounding content asset.** The validated, graded, interestingness-ranked bank (plus, later, real
   solve-time data) is a moat that model progress feeds rather than erodes: better models make better
   auxiliary-construction proposers for our verified pipeline.

## Primary goals

1. **Correctness above all.** Every published puzzle provably solvable from exactly the information shown
   (stated premises + the figure's configuration — see doc 07 T2), with a unique numeric answer and a
   valid displayed derivation. One broken puzzle destroys trust permanently.
2. **Unlimited content.** Fully automatic batch generation; human effort only for optional gem promotion.
3. **Human-readable solutions.** Chains of named elementary theorems ("∠BAC = ∠BDC because both subtend
   arc BC"), never algebraic certificates. This is the pivot's hardest requirement — see doc 03 §3.5.
4. **Meaningful difficulty grading** derived from proof structure.

## Secondary goals

Daily-puzzle and endless-practice modes; one-step-at-a-time hint system; difficulty progression.

## Scope — v1

- **Puzzle type:** quantity-finding. Given a figure with marked quantities/relations, find one unknown
  quantity. All machinery (schema, goal selection, gates, difficulty, frontend) is written against the
  **quantity-type registry** (doc 04 §QTR), never against "angle" specifically.
- **Enabled quantity types at launch:** `angle` (angle chasing). `length` and `ratio` follow in the first
  post-release phase — the engines' algebraic reasoning derives them natively (doc 03 §3.8); `area`
  follows later behind a custom verified derivation layer. Enabling a type is config + templates + UX,
  not an architecture change.
- **Figure universe: line-and-circle Euclidean geometry** — points, segments/lines, polygon families
  (triangles, quadrilaterals, trapezoids, …, as construction-step families), circles and arcs. Circles
  are in the v1 sampler from day one (they carry most non-trivial difficulty). Conics
  (parabolas/ellipses/hyperbolas) are a recorded non-goal for the synthetic engine (doc 07 T9).
- **Engine:** imported (Newclid 3 / Yuclid; AG2 DDAR as validator) behind a thin Solver Abstraction
  Layer (doc 03). We do not write deduction rules.
- **Platform:** static web app consuming a pre-generated, pre-validated JSON puzzle bank. No accounts,
  no backend.
- **Generation:** offline batch, run by the developer; output committed/deployed as data.

## Scope — later (doc 09)

Length/ratio quantity types (first post-release phase); auxiliary-construction puzzles
(generate-with/hide, LLM-proposed and engine-verified); area puzzles behind the custom area layer;
optional Lean/LeanGeo formal-verification tier for featured puzzles; further domains (algebra first,
SymPy-verified) reusing the bank/difficulty/product spine — the spine, not any engine, is the platform.

## Explicit non-goals

- **Not a solver competing with LLMs or research provers.** We consume provers; we don't advance them.
- **No LLM in the correctness path.** LLMs may propose auxiliary constructions (engine-verified) and
  rephrase solution prose (template output remains source of truth). Validity, answers, proofs, and
  difficulty labels come only from the symbolic pipeline. Unanimously confirmed by every serious system
  surveyed (research/03 §3.3).
- **Not a construction game** (Euclidea's compass-and-straightedge gameplay is out of scope).
- **No real-time generation in v1.** Precomputed banks only.

## Success criteria

- **Correctness:** 0 invalid puzzles in the published bank; every bank build passes the independent
  cross-engine validation gate (doc 04 §V).
- **Volume:** ≥ 500 accepted puzzles/hour on the owner's hardware, **measured per difficulty band** —
  an aggregate target hides expert-band starvation.
- **Quality floor:** ≤ 5% "trivial or ugly" in stratified spot checks of 50 puzzles per bank build.
- **Difficulty sanity:** band ordering monotone in perceived difficulty on spot checks; solve-time
  calibration once users exist. Measured per quantity type once more than one is enabled.
- **Readability gate (pivot-specific):** ≥ 90% of accepted puzzles have solutions consisting entirely of
  whitelisted readable step types (doc 03 §3.5); the remainder are discarded, never shipped ugly.

## Difficulty ambition (honest ladder)

Difficulty is a phased capability, not a v1 promise. Unguided random generation naturally yields
easy-to-medium material; everything above that comes from selection pressure and mechanisms:

| Rung | Mechanism | Phase | Honest claim |
|---|---|---|---|
| Easy–medium | Random sampling + filters | P1 | Solid practice material |
| Hard | Depth/tier targeting, branch-join selection, elegance-ratio ranking, cross-quantity goals | P1–P3 | Challenges strong amateurs; real effort for competition-trained solvers ("Euclidea-hard") |
| Expert / olympiad-entry | **Auxiliary-construction hiding** (generate-with, hide, rediscover) | P4 | The known difficulty multiplier — the mechanism behind TongGeometry's competition-selected problems |
| Olympiad-grade | Value-guided construction search at scale | P4+ aspiration | Requires TongGeometry-class compute; architected for (sampler feedback slot), not promised |

Two commitments hold at every rung: difficulty comes from proof structure, never presentation obstacles
(doc 05 §5.5), and bands mean what they say — a thin, honest expert band beats an inflated one.

## Target user

Puzzle enthusiasts comfortable with school-to-competition geometry — the Euclidea / sudokuwiki /
competition-warmup audience. Interface language-light; usable by non-native English speakers.
