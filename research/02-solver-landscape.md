# 02 — Geometry Solver Landscape

Systems that *solve/prove* plane-geometry statements, compared on the axes that matter for GeoForge:
proof readability (solutions are the product), speed (generation runs millions of attempts), input
language, openness, and maintenance. Benchmark shorthand: **IMO-AG-30** = 30 IMO geometry problems
(2000–2022) from the AlphaGeometry paper; **IMO-AG-50** = extended set (2000–2024) from AG2.

## 2.1 The AlphaGeometry family (synthetic-rule + algebraic reasoning)

### AlphaGeometry 1 — DDAR + LM (Google DeepMind, Nature 2024)
- **Architecture:** symbolic *Deductive Database* (DD: forward chaining over ~hundreds of geometric rules)
  + *Algebraic Reasoning* (AR: Gaussian elimination over angle/ratio/distance atoms), with a 151M-param
  transformer proposing auxiliary constructions when the symbolic closure stalls.
- **Performance:** 25/30 on IMO-AG-30 (DDAR alone: 14).
- **Openness:** [google-deepmind/alphageometry](https://github.com/google-deepmind/alphageometry) —
  Apache-2.0, 4.9k★, includes the **synthetic problem-generation pipeline** (random premise sampling →
  closure → traceback) that `docs/04` independently reinvented. Weights CC-BY-4.0.
- **Weaknesses:** research code (JAX/meliad stack is awkward to run), Python DD is slow, undocumented
  problem language, effectively unmaintained (issues only).

### AlphaGeometry 2 — DDAR2 + Gemini-based LM (arXiv 2502.03544, JMLR Jan 2026)
- **Architecture:** extended language (locus/movement statements, non-constructive problems, ratios),
  faster C++-backed DDAR, novel **SKEST** shared-knowledge parallel tree search, Gemini-based proposal LM.
- **Performance:** 42/50 on IMO-AG-50 (84% — above average human gold medalist on geometry).
- **Openness:** [google-deepmind/alphageometry2](https://github.com/google-deepmind/alphageometry2) —
  Apache-2.0, **symbolic DDAR engine only** (runs on formalized problems + point coordinates); the LM and
  search are not released.
- **Role for GeoForge:** ideal **independent second engine** for bank validation (uncorrelated codebase,
  permissive license), and a hard-mode solver for aux-construction-free closure.

### Newclid 3.0 + Yuclid (arXiv 2411.11938; PyPI `newclid` 3.0.1)
- **Architecture:** community successor to AG's symbolic side. DDARN (refactored DDAR) → v3 adds
  **Yuclid**, a high-performance C++ solver using deductive databases + algebraic reasoning with numeric
  diagram preprocessing. Agentic API: pluggable "agents" (including LLM or human heuristics) propose
  auxiliary points. Accepts JGEX text and **GeoGebra (.ggb)** files; produces traced, human-followable
  proofs; no LLM required for most problems.
- **Pedigree:** Yuclid is the geometry component inside Harmonic's **Aristotle** (formally verified IMO
  2025 gold performance, 5/6 problems).
- **Openness/maintenance:** [Newclid/Newclid](https://github.com/Newclid/Newclid), 95★, active
  (pushed Feb 2026), good docs ([newclid.github.io](https://newclid.github.io/Newclid/)).
  ⚠ **No license declared on GitHub or PyPI as of 2026-08-01 — must be clarified before adoption.**
- **Role for GeoForge:** recommended **primary engine** (pending license), because it is the only AG-class
  system with a supported API, readable tracebacks, and active maintenance.

### Seed-Geometry (ByteDance, arXiv 2507.23726)
- **Architecture:** forward-chaining engine + C++ backend + LLM proposal, inside Seed-Prover. Generated
  **230M unique problems** for training via extensive search over its DSL.
- **Performance:** 43/50 on IMO-AG-50 (edges out AG2); solved IMO 2025's geometry problem in ~2 s.
- **Openness:** [ByteDance-Seed/Seed-Prover](https://github.com/ByteDance-Seed/Seed-Prover) (Apache-2.0,
  438★) publishes proofs/results and Lean artifacts; the geometry engine itself does not appear to be
  released as reusable code. Track for future release; not currently integrable.

### TongGeometry (BIGAI, Nature Machine Intelligence)
- Solver *and* generator via value-guided tree search; solves all IMO geometry 2000+ within 38 min on a
  single consumer GPU. Covered in depth in [03-generation-landscape.md](03-generation-landscape.md).
- [bigai-ai/tong-geometry](https://github.com/bigai-ai/tong-geometry): **GPL-3.0**, 45★, pushed Feb 2026.

## 2.2 Classical algebraic provers

| System | Method | Verdict for GeoForge |
|---|---|---|
| **Wu's method** | Characteristic sets over polynomial translations | Decides truth, certificates unreadable. Notably: a 2024 study showed Wu's method alone solves 15/30 IMO-AG-30 and complements DDAR. Candidate *validator*, never the solution source |
| **Gröbner bases** (Giac, Singular) | Ideal membership | Same profile as Wu; powers GeoGebra Discovery's `Prove` |
| **Area method** (GCLC/JGEX) | Coordinate-free area/ratio elimination | Semi-readable proofs, elegant but alien to angle-chasing audiences |
| **SMT (Z3, cvc5)** | Nonlinear real arithmetic (∃-decision) | Usable for consistency/impossibility checks on coordinate encodings; proofs unreadable; timeouts on nontrivial synthetic geometry |

## 2.3 Dynamic-geometry provers (education lineage)

- **GeoGebra Discovery** ([kovzol/geogebra-discovery](https://github.com/kovzol/geogebra-discovery),
  active July 2026): `Prove`, `ProveDetails`, `Discover`, `Compare`, `LocusEquation` on GeoGebra
  constructions, verified symbolically via Gröbner bases (Giac). Excellent **authoring/debugging cockpit**
  and conjecture-discovery aid; GPL; not an embeddable library for our pipeline.
- **GCLC** (Janičić; [official site](http://poincare.matf.bg.ac.rs/~janicic/gclc/)): three provers (area
  method, Wu, Gröbner) + figure description language; open source; venerable but niche.
- **JGEX** (Java Geometry Expert): deductive database + full-angle method; historically important — its
  problem format is the lingua franca AG and Newclid still speak — but essentially unmaintained.
- **OK Geometry**: observation/conjecture tool for teachers; not a prover engine.

## 2.4 Formal-foundations provers (covered fully in 05)

GeoCoq (Rocq/Coq, Tarski axiomatics), LeanGeo (Lean 4 + 260-theorem competition library + LeanGeo-Bench),
LeanEuclid/E (diagrammatic reasoning à la Euclid). These give *machine-checked certainty*, not solving
power or speed; they belong in an optional verification tier, not the generation hot loop.

## 2.5 FormalGeo / FGeo family (CDL ecosystem)

[FormalGeo](https://github.com/FormalGeo/FormalGeo) (GPL-3.0, active July 2026): 88 predicates + 196
theorems, CDL formal language, FormalGeo7K/30K datasets; satellite systems FGeo-SSS (search),
FGeo-TP (theorem predictor), FGeo-DRL (RL), FGeo-HyperGNet (hypergraph net; IJCAI 2025 — 88.4% solving on
FormalGeo7K), FGeo-Eval (difficulty/completion metrics). Targets *SAT-to-olympiad exam problems* (often
numeric quantity-finding — closer to GeoForge's goal type than AG's proof goals). Weaknesses: GPL, mostly
research-quality code, Chinese-education problem style, lower ceiling than AG-class engines.

## 2.6 Comparative summary

| System | Solves IMO-AG-50 | Readable proofs | Numeric goals (find-the-angle) | API quality | License | Maintained | GeoForge fit |
|---|---|---|---|---|---|---|---|
| Newclid 3.0/Yuclid | ~AG-class (Aristotle pedigree) | **Yes (traced)** | Via derived value facts | **Good (Python, docs)** | ⚠ undeclared | **Yes** | **Primary** |
| AG2 DDAR | 42/50 (with LM) | Partial (DD steps yes, AR terse) | Yes (aconst/rconst facts) | Research-grade | Apache-2.0 | Low | **Validator** |
| Seed-Geometry | 43/50 | Unknown | Yes | Not released | Apache-2.0 (repo) | Yes | Watch |
| TongGeometry | IMO 2000+ geometry | Yes | Proof-style goals | Research-grade | GPL-3.0 | Some | Ideas / gen. reference |
| FormalGeo/FGeo | Exam-level | Yes (CDL steps) | **Yes (native)** | Research-grade | GPL-3.0 | Yes | Ideas; difficulty metrics |
| GeoGebra Discovery | Conjecture-level | No (certificates) | No | GUI-centric | GPL | Yes | Authoring/debug |
| Wu/Gröbner/SMT | Partial | No | No | Library-level | Various | Yes | Independent validator |
| Lean/LeanGeo | With LLM provers | Formal (expert-readable) | Possible | Lean toolchain | Apache-2.0 | **Yes** | Optional formal tier |
