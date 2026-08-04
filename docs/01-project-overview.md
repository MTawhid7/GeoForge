# 01 — Project Overview

## Vision

GeoForge generates an unlimited supply of valid, well-posed, **genuinely hard** Euclidean geometry
puzzles — **find an unknown quantity: an angle, a length, a ratio, a shaded area…** — with
machine-verified step-by-step solutions, presented in a clean Euclidea-like web app. The pipeline,
schema, and gates are designed **quantity-generic** from day one; quantity types are *enabled* in phases
as engine support and answer-input UX mature (doc 09). Curated collections (books, sudokuwiki-style
sites, puzzle YouTube channels) are excellent but finite; GeoForge removes that ceiling.

**Difficulty revision (2026-08-04).** The first playable bank was measured and rejected: 71 of 98
answers were 45°, another 15 were 90°, no figure contained a circle, and puzzles banded *expert* were
solved by inspection. The causes were structural, not cosmetic — see doc 07 T5, T17, T19, and L4 — and
the response reshapes several parts of this document. The one-line version: **hard means a competition
solver has to work, and every claim to the contrary in this repo is now measured rather than assumed.**

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
2. **Genuine difficulty** (promoted 2026-08-04, was goal 4). A puzzle must resist the reader — not
   because the figure is cluttered or the wording is coy, but because finding the first move is hard.
   Operationally this means three properties, each enforced rather than hoped for: **no shortcut** (the
   goal is not reachable in a couple of steps by any route, doc 07 T19), **no sight-read** (the answer
   is not guessable from the figure or from the bank's answer distribution, doc 07 T5), and **real
   theorem content** (the proof composes non-elementary results rather than repeating one).
3. **Unlimited content.** Fully automatic batch generation; human effort only for optional gem promotion.
4. **Readable solutions** (demoted from a gate to a rendering concern, doc 07 T17). Solutions read as
   chains of named theorems, not algebraic certificates — but a puzzle is no longer *discarded* for
   using a theorem our template table cannot phrase. Prose is rendered by an LLM from the engine's
   structured step, under the four conditions in T17, which is what lets all 93 of Newclid's rules ship.
5. **Meaningful difficulty grading**, calibrated against human perception rather than derived from proof
   length alone (doc 05 §5.1, doc 07 T19).

## Secondary goals

Daily-puzzle and endless-practice modes; one-step-at-a-time hint system; difficulty progression.

## Scope — v1

- **Puzzle type:** quantity-finding. Given a figure with marked quantities/relations, find one unknown
  quantity. All machinery (schema, goal selection, gates, difficulty, frontend) is written against the
  **quantity-type registry** (doc 04 §QTR), never against "angle" specifically.
- **Enabled quantity types at launch:** `angle` only (revised twice — see below). The concern that
  motivated adding `ratio` and `length` stands: on a to-scale figure every angle answer is
  eyeball-readable, and integer degrees give a small answer space a player learns to guess (doc 07 T5).
  The remedy did not survive measurement. **M4a measured the ratio corpus and it is more guessable than
  the angle corpus, not less** — 3 distinct answers at 52.9% modal share, because one rule of 93
  concludes a ratio constant and AR chases ratios multiplicatively; length lands in the same space
  scaled by a pinned unit; and `r2const`/`l2const` derive never, so the irrational answers this bullet
  promised are not reachable at all (doc 07 T18 reversed, T21). Guessability is therefore handled where
  the measurement says it lives — the sight-readable rejection and filter 8's per-band share cap — and
  `ratio`/`length` wait on a rule extension. `area` still follows later behind a custom verified
  derivation layer (doc 03 §3.7). Enabling a type remains registry + config + UX, which the spike
  confirmed; the blocker is what the engine derives, not what the architecture allows.
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

~~Length/ratio quantity types~~ — **pulled forward into scope above** (doc 07 T7). Still later:
auxiliary-construction *hiding* (generate-with/hide, LLM-proposed and engine-verified — detection lands
earlier, doc 07 T10); configuration-seeded and backward generation with a learned interestingness
proposer (doc 07 T20); area puzzles behind the custom area layer; optional Lean/LeanGeo
formal-verification tier for featured puzzles; further domains (algebra first, SymPy-verified) reusing
the bank/difficulty/product spine — the spine, not any engine, is the platform.

## Explicit non-goals

- **Not a solver competing with LLMs or research provers.** We consume provers; we don't advance them.
  Note the corollary, sharpened 2026-08-04: *solving* olympiad geometry is close to a solved problem for
  frontier models, and it is not what we are selling. **Proposing an interesting problem is the hard
  part**, and it is the part this repo exists to do.
- **No LLM in the correctness path** (unchanged in force, restated precisely — doc 07 T17). Validity,
  answers, proofs, canonical facts, highlights and difficulty labels come only from the symbolic
  pipeline. An LLM may (a) render an already-proved step into English, (b) propose auxiliary
  constructions for the engine to verify, and (c) later, guide the search for interesting configurations
  — none of which is permitted to decide what is *true*. Doc 02 invariant 5 enumerates the fields LLM
  output may never enter, and it got stricter, not looser, when rendering was adopted.
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
- **Answer entropy** (added 2026-08-04): no single answer value holds more than 15% of any band, and the
  bank's answer distribution has enough entropy that guessing the modal answer beats random by less than
  a stated margin. The first bank failed this at 72% — the criterion exists because nothing was watching.
- **Shortcut resistance** (added 2026-08-04): 0 published puzzles whose goal is reachable from the stated
  givens by a short route. ~~This is a build gate~~ — **it is not, and cannot be, on this engine
  (2026-08-04, M5; doc 05 §5.2 filter 9, doc 07 T22).** There is no step budget to impose, no second
  derivation to find, and forward search never derives a constant angle at all (measured: 0 novel
  `aconst` across 117 closures). The criterion stands as a *criterion* — it is still what the product
  must achieve — but it has no automated instrument, and the two partial substitutes (the configuration
  table, the LLM oracle column) are a whitelist and a judge, not a proof. This is the largest known gap
  between what this document asks for and what the build can verify, and it is stated rather than
  quietly downgraded.
- **Prose fidelity** (replaces the pivot-era readability gate, doc 07 T17): 100% of rendered solution
  steps pass the entity-level check, and the sampled prose review on each bank build finds no
  misstatement. The old criterion — ≥ 90% of puzzles built entirely from whitelisted step types — is
  **retired**: it measured our template coverage, not the player's experience, and enforcing it capped
  difficulty (doc 07 L3).

## Difficulty ambition (honest ladder)

Difficulty is a phased capability, not a v1 promise. **Rewritten 2026-08-04** after the first bank was
measured; the old ladder's bottom two rungs turned out to be one rung, and it credited mechanisms that
were not actually doing anything.

| Rung | Mechanism | Phase | Honest claim |
|---|---|---|---|
| **Invalid** | *(what unguided sampling actually produced)* | — | 72% of answers 45°, no circles, expert puzzles solved by inspection. Recorded so the baseline is not re-discovered |
| Easy–hard, honest | Shortcut filter + answer entropy + non-round values + all 93 rules | P3 | Real practice material; a competition solver has to read the figure rather than glance at it |
| Expert | Non-angle goals (ratio/length) + **auxiliary-construction detection** — surfacing the puzzles whose minimal derivation already needs a point no given names | P3 | The mechanism behind AlphaGeometry's own training corpus. Detection is cheap; we simply never looked (doc 07 T10) |
| Olympiad-entry | Auxiliary-construction **hiding** (generate-with, hide, rediscover) + configuration-seeded figures | P5 | The known difficulty multiplier; needs figures rich enough to contain aux points (doc 07 L4) |
| Olympiad-grade | Backward/value-guided proposing at scale | P5+ | TongGeometry demonstrated it and got three problems into real competitions. We commit to the architecture, not to its compute |

Three commitments hold at every rung: difficulty comes from proof structure and never from presentation
obstacles (doc 05 §5.5); bands mean what they say, and a thin honest expert band beats an inflated one
(doc 07 T10); and **every claim on this ladder is measured before it is written down** — the row that
was wrong got there by being assumed.

## Target user

**Competition-trained solvers** — olympiad students, coaches, and adults who did that once and miss it.
Revised 2026-08-04 from "puzzle enthusiasts comfortable with school-to-competition geometry", which was
the audience the first bank was accidentally built for: an undergraduate skips most of a 9-step
generated proof in their head and answers in seconds.

The practical consequence is a calibration one. **The reference standard is not a textbook exercise; it
is a Catriona Shearer puzzle or an olympiad problem 1.** Two properties of that reference material are
worth naming because our generator does not currently produce either: the figures are *deliberate
arrangements of regular shapes* (squares sharing a vertex, hexagons edge to edge, semicircles in a
rectangle) rather than clause-by-clause growths, and the interesting questions are usually about
**areas, ratios and lengths** with a surprisingly invariant answer — not about angles. Both are recorded
as gaps in doc 07 L4 and T7 respectively.

Interface stays language-light and usable by non-native English speakers; a harder audience is not a
wordier one.
