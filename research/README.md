# GeoForge Research: State-of-the-Art AI for Geometry Problem Generation & Solving

**Date:** 2026-08-01 · **Status:** research complete, decision pending
**Question:** should GeoForge build its geometry engine from scratch (per `docs/01`–`09`), or assemble it from mature research systems?

**Short answer:** the from-scratch plan in `docs/` is now the wrong trade. Since that spec was written, the
field shipped exactly the components it planned to hand-build: AlphaGeometry 2's symbolic engine is
Apache-2.0 open source (Jan 2026), Newclid 3.0 wraps an AG-class solver in a maintained Python API with a
fast C++ core, and TongGeometry demonstrated end-to-end *generation* of olympiad-grade problems good enough
to appear in real competitions. What remains genuinely unavailable off the shelf is the **product layer**:
quantity-goal selection, difficulty calibration, well-posedness gating, anti-leak diagram layout, and the
puzzle bank — i.e., most of what `docs/04`–`06` already specify. Full verdict in
[01-executive-summary.md](01-executive-summary.md).

## Document map

| File | Contents |
|---|---|
| [01-executive-summary.md](01-executive-summary.md) | Verdict, recommended stack, build-vs-buy table |
| [02-solver-landscape.md](02-solver-landscape.md) | Geometry solvers/provers compared in depth |
| [03-generation-landscape.md](03-generation-landscape.md) | Problem-generation systems (the core of GeoForge's need) |
| [04-neural-reasoning.md](04-neural-reasoning.md) | LLMs, RL provers, GNNs, MCTS, neuro-symbolic approaches |
| [05-formal-systems.md](05-formal-systems.md) | Lean/mathlib, LeanGeo, GeoCoq, Isabelle, SMT, CAS |
| [06-deepmind.md](06-deepmind.md) | AlphaGeometry 1/2, AlphaProof, Gemini Deep Think — deep dive |
| [07-open-source-ecosystem.md](07-open-source-ecosystem.md) | Verified repo metadata (stars, activity, licenses) + license analysis |
| [08-research-papers.md](08-research-papers.md) | Paper-by-paper summaries with relevance ratings |
| [09-architecture-recommendation.md](09-architecture-recommendation.md) | Recommended hybrid architecture + diagrams |
| [10-roadmap-and-risks.md](10-roadmap-and-risks.md) | Phased development roadmap and risk register |

## How this research was conducted

Web research performed 2026-08-01 (the field moved substantially in 2025–2026; anything older than the
AlphaGeometry 2 release should be treated as historical). GitHub metadata (stars, last push, license) was
pulled live from the GitHub API on the same date and is recorded in
[07-open-source-ecosystem.md](07-open-source-ecosystem.md). Claims sourced from press coverage rather than
papers (notably the reported IMO 2026 42/42 results) are explicitly marked as such.

## Relationship to the existing `docs/` spec

The pivot invalidates `docs/03-core-engine.md` (the hand-written rule engine) and parts of
`docs/04-generation-pipeline.md` (deduction internals). It **preserves** the pipeline philosophy — brutal
attrition, independent validation, numeric-verifies-never-derives, difficulty from proof structure — which
this research confirms is exactly how the strongest systems (AlphaGeometry's synthetic pipeline,
TongGeometry, Seed-Geometry) work at scale. The correctness gates and product layers specced in docs 04–06
survive the pivot nearly intact; they sit *on top of* an imported engine instead of a hand-built one.
