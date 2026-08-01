# 01 — Executive Summary

## The landscape shifted under the original plan

The `docs/` spec (write a ~25-rule forward-chaining angle-chase engine from scratch) was a reasonable 2024
decision. Three developments since make "assemble, don't build" the better strategy in 2026:

1. **The AG-class engine is now free.** Google DeepMind open-sourced the **AlphaGeometry 2 symbolic engine
   (DDAR)** under Apache-2.0 alongside the JMLR publication (Jan 2026) — the same engine that, with its LM,
   solves 42/50 of all IMO geometry problems 2000–2024. **Newclid 3.0** (PyPI `newclid`, with the C++
   **Yuclid** core) wraps an AG-derived solver in a maintained, documented Python API accepting JGEX and
   GeoGebra input. Yuclid is the geometry solver inside Harmonic's Aristotle, which produced formally
   verified gold-medal IMO 2025 performance. Rebuilding this class of engine by hand — including the
   algebraic-reasoning (AR) module the old spec deferred as "AR-lite" — would take months to reach a level
   these systems exceed today.

2. **Generation is a solved research problem (at olympiad grade, not just workmanlike grade).**
   **TongGeometry** (BIGAI, *Nature Machine Intelligence*) generates and solves olympiad geometry via guided
   tree search; it built a repository of **6.7 billion** theorems requiring auxiliary constructions, and
   three of its generated problems were selected for real olympiads (a Chinese national team qualifying exam
   and a top US competition). ByteDance's **Seed-Geometry** generated **230 million** unique problems to
   train its prover. The "sample constructions → deduce closure → pick deep goals → traceback" pipeline in
   `docs/04` is exactly the published AlphaGeometry synthetic-data pipeline — and that pipeline's reference
   implementation is in the open-source AG1 repo.

3. **The frontier keeps compounding.** Official IMO results: 2024 silver (AlphaProof + AG2, 28/42), 2025
   gold (Gemini Deep Think, 35/42, officially graded; Harmonic's Aristotle got 5/6 formally verified in
   Lean), and in July 2026 press reports first officially graded **42/42** scores (Huawei "Celia" and
   Xiaohongshu "dots-note 3.0" — press-reported, papers pending). Betting against this ecosystem by
   hand-building a small rule engine means permanently trailing it.

## Verdict on the core question

**Combining mature systems is significantly better than manual implementation — for the engine. It is not
available at all for the product.** No existing system produces GeoForge's actual deliverable: banked,
difficulty-graded, well-posed *quantity-finding* puzzles with human-readable step solutions and clean
diagrams for a consumer app. TongGeometry's outputs are proof problems for olympiad committees; AG/Newclid
are solvers, not puzzle products; educational generators (SDE-GPG, VeriGeo, GeoProblem Factory) target
school curricula at far lower difficulty ceilings. The moat is the product layer, and the old `docs/`
already specify most of it.

## Recommended stack (details in 09)

| Layer | Recommendation | Why |
|---|---|---|
| Symbolic geometry engine | **Newclid 3.0 + Yuclid** (primary), **AG2 DDAR** (independent cross-validator) | Maintained Python API + Apache-2.0 second engine for correlated-bug-free validation |
| Problem generation | **Custom orchestrator** implementing `docs/04`'s pipeline over the imported engine; borrow AG1's premise sampler design; TongGeometry ideas (not code — GPL) for value-guided search later | Nothing off-the-shelf emits quantity-finding puzzles with difficulty control |
| Auxiliary constructions (later) | LLM proposer (Gemini / Claude) + Newclid's built-in heuristics, engine-verified | Standard AG-style neuro-symbolic loop; LLM never trusted |
| Difficulty & interestingness | **Custom** (proof-DAG scoring from `docs/05` survives intact) | No public system grades difficulty for end users |
| Well-posedness / degeneracy | **Custom** numeric gates (from `docs/04`) | Unique to the quantity-finding product; no equivalent exists |
| Formal verification (optional tier) | **Lean 4 + LeanGeo** for flagship/featured puzzles only | Machine-checked guarantee where it's worth the cost |
| Diagram generation | **Custom SVG layout** (from `docs/06`); Penrose as reference, GeoGebra for authoring/debugging | Anti-leak metric-consistent layout is product-specific |
| Frontend | Unchanged from `docs/06` | Renders JSON; engine swap is invisible to it |
| Future domains (algebra, NT, …) | Lean/mathlib + open RL provers (Kimina, DeepSeek-Prover-V2, Goedel-Prover-V2) + SymPy | The only credible "universal math platform" substrate |

## Build vs. buy, per component

| Component | Old plan | New plan | Rationale |
|---|---|---|---|
| Deduction rules + AR | Build (~25 rules, "AR-lite") | **Buy** (Newclid/DDAR: full rule set + Gaussian-elimination AR, C++ speed) | External feedback already flagged AR-lite as the spec's weakest engine decision; DDAR resolves it |
| Construction DSL | Build | **Adapt** (JGEX/AG language is the ecosystem lingua franca) | Compatibility with AG2, Newclid, TongGeometry benchmarks for free |
| Proof traceback | Build | **Buy + shape** (Newclid emits traced proofs; custom translation to player-facing steps) | Readability post-processing stays custom |
| Goal selection, minimization | Build | **Build** (thin layer over engine output) | Product-specific |
| Well-posedness, degeneracy gates | Build | **Build** | Product-specific; keep `docs/04` design |
| Difficulty scoring | Build | **Build** | Product-specific; keep `docs/05` design |
| Layout / anti-leak | Build | **Build** | Product-specific; keep `docs/06` design |
| Bank + validator + frontend | Build | **Build** | Product-specific |
| Formal proof checking | Not planned | **Buy** (Lean/LeanGeo, optional) | New capability, near-zero build cost |

## Top risks (register in 10)

1. **Newclid's license is undeclared** (no license detected on GitHub or PyPI as of 2026-08-01). Must be
   resolved with the maintainers before integration; AG2 DDAR (Apache-2.0) is the fallback primary.
   *(Resolved 2026-08-01 after cloning: the monorepo carries per-subpackage LICENSE files — `newclid`,
   `yuclid`, and `ncdgen` are all Apache-2.0. Blocker cleared; see docs/07 P2.)*
2. **Proof readability gap**: DDAR/AR proof steps (especially algebraic ones) are not directly
   player-friendly; a translation layer is required and its difficulty is the main technical unknown —
   hence the Phase-0 spike in [10-roadmap-and-risks.md](10-roadmap-and-risks.md).
3. **GPL boundaries**: TongGeometry and FormalGeo are GPL-3.0; use as separate processes or ideas-only.
4. **Learning-goal loss**: `docs/01` names learning-by-building as a project goal. The pivot trades
   engine-building for systems-integration learning; this is a values decision the owner should make
   explicitly, not a technical one.
