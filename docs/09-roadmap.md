# 09 — Roadmap

Ordered so an end-to-end pipeline exists as early as possible; every phase ships something runnable and
each has acceptance criteria (AC). Phase 0 is a **decision gate**: it can still send us back to a hybrid
design if trace readability disappoints.

## P0 — Feasibility spikes (≈ 2–3 weeks) · decision gate

- ~~License check~~ **resolved**: `newclid`, `yuclid`, `ncdgen`, AG2 DDAR all verified Apache-2.0 in the
  reference clones (doc 07 P2).
- **S1 Solve spike:** run Newclid and AG2 DDAR on ~20 hand-written Euclidea-style angle-chase problems
  (JGEX). Measure solve rate, wall time, and trace quality.
- **S2 Readability spike (the gate):** hand-translate 10 engine traces into player steps; estimate
  whitelist coverage and AR-chain lengths (doc 03 §3.5). Include 2–3 length/ratio traces (similar
  triangles, Pythagoras) to price the wave-2 template family early — informational, not a gate.
- **S3 Generation spike:** adapt `ncdgen`'s loop: sample → closure → enumerate numeric-valued goals →
  traceback. Confirm quantity-goal extraction and seed determinism through the engine.
- **AC / gate:** ≥ 80% of S2 traces translate with bounded effort ⇒ proceed. Below that ⇒ adopt the
  hybrid fallback (engine finds truths; a thin custom presentation layer re-derives display paths) and
  record it in doc 07 before Phase 1.

## P1 — Generator MVP (≈ 4–6 weeks)

SAL with `newclid` backend + contract tests; typed construction layer over JGEX; sampler (adapted
`ncdgen`); Stages 1–9 of doc 04 incl. configuration facts, readability gate, well-posedness;
attrition report per stage/band.
**AC:** fixed seed ⇒ byte-identical batch; 100 validated puzzles across ≥ 2 bands; every puzzle's
solution readable per gate; zero soundness failures in a 1,000-construction run (failures found = bugs
fixed, rerun clean).

## P2 — Product bank + frontend (≈ 4–6 weeks)

Scoring/filters/elegance ratio; isomorphism dedupe; layout + anti-leak; bank builder; **cross-engine
validation via `ag2ddar` backend**; JSON Schema → TS types in CI. Frontend v1 (player, hints, replay,
home/daily/practice, localStorage stats) per doc 06.
**AC:** `make bank` ⇒ ≥ 2,000 validated puzzles; mutation tests all caught; 20-figure layout spot check
clean; e2e happy path green; first-puzzle-interactive < 2 s on a mid-range phone; owner solves 10
puzzles on a phone without UX blockers.

## v1.0 — Public release

Dogfooding pass (owner solves ≥ 100 across bands), difficulty weight calibration from those spot checks,
PWA niceties, deploy to static host.
**AC:** doc 01 success criteria measured and met or explicitly re-scoped in doc 07.

## P3 — Quantity wave 2: lengths & ratios (post-v1)

Register `length` and `ratio` in the quantity-type registry (doc 04 §QTR): goal extractors over the
engines' AR length/ratio atoms; scale-pinning givens; similarity/metric template family (similar
triangles, Pythagoras, equal chords…); fraction and decimal+tolerance answer input (doc 07 T8); nice-
value palettes; per-type difficulty calibration.
**AC:** mixed banks across all bands with ≥ 3 quantity-type-crossing puzzles per spot check surviving
filters; v1 angle banks rebuild byte-identical (regression); tolerance-collision check clean bank-wide.

## P4 — Difficulty depth

Auxiliary-construction puzzles: generate *with* the aux element (Newclid agent heuristics, then LLM
proposer via the same agent API — engine-verified), hide it, design hint UX for rediscovery. Corpus-
weighted sampler grammar. Deliberate revisit of doc 05 §5.5's no-feedback-loop rule (value-guided
sampling à la TongGeometry) — via doc 07 entry.
**AC:** expert band populated at target volume; hidden-construction hint UX validated by dogfooding.

## P5 — Quantity wave 3: areas

Design doc first (required by doc 03 §3.7): the verified decomposition layer — target region split into
triangles whose sides/angles are engine-certified; exact symbolic area arithmetic (SymPy) as readable
decomposition steps; `regions` figure schema + shading UX (doc 06).
**AC:** shaded-area puzzles pass all existing gates including cross-engine re-certification of every
underlying fact; decomposition steps pass the readability gate at the standard threshold.

## P6 — Formal tier & platform seed (ongoing)

- LeanGeo export + machine-checked certificates for featured puzzles ("formally verified" badge).
- Second-domain pilot (algebra, SymPy-verified generation) reusing the bank/difficulty/product spine —
  the test of the universal-platform thesis at minimal cost.
- Watch list: Seed-Geometry code release (drop-in SAL backend candidate); LeanGeo growth; new AG-lineage
  releases.

## Sequencing rationale

Readability risk is retired first because it's the only pivot-specific unknown that could invalidate the
architecture (P0 gate). Correctness gates precede volume (P1 before P2) because every later feature
multiplies the cost of a soundness bug. Layout precedes frontend polish because the frontend contract is
"render finished JSON". Quantity waves follow engine support (doc 03 §3.7): lengths/ratios ride the
engines' native AR (P3, cheap), areas need a custom verified layer (P5, expensive) — but the registry
(doc 04 §QTR) exists from P1, so no wave requires touching core pipeline code. Aux constructions (P4)
wait for a stable pipeline because they multiply search cost and UX complexity simultaneously.
