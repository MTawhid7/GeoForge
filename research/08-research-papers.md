# 08 — Key Research Papers (2024–2026)

Ranked by relevance to GeoForge. ★★★ = read before writing code; ★★ = read during design of the relevant
subsystem; ★ = background.

## ★★★ Directly load-bearing

**1. "Solving olympiad geometry without human demonstrations" (Trinh et al., Nature 2024 — AlphaGeometry)**
- *Contribution:* neuro-symbolic solver + the synthetic generation pipeline (premise sampling → closure →
  traceback → aux-point extraction) that produced 100M training theorems.
- *Relevance:* the reference implementation of GeoForge's entire generation philosophy. Code: Apache-2.0.
- *Limitations:* proof-goal (not quantity-goal) orientation; research-grade code.

**2. "Gold-medalist performance in solving olympiad geometry with AlphaGeometry2" (arXiv 2502.03544; JMLR 2026)**
- *Contribution:* expanded language (88% IMO coverage), fast DDAR, SKEST parallel search, 42/50 IMO-AG-50.
- *Relevance:* the open-sourced DDAR engine is our designated independent validator; the language extension
  chapter defines what a modern geometry DSL must express. Code (symbolic engine): Apache-2.0.
- *Limitations:* LM + search closed; needs point coordinates supplied with problems.

**3. "Newclid: A User-Friendly Replacement for AlphaGeometry" (arXiv 2411.11938; v3 docs at newclid.github.io)**
- *Contribution:* DDARN refactor — traceable readable proofs, GeoGebra/JGEX input, agentic aux-point API,
  no-LLM operation; v3 adds C++ Yuclid (used inside Harmonic's Aristotle).
- *Relevance:* candidate primary engine. *Limitation:* license undeclared; small team.

**4. "Proposing and solving olympiad geometry with guided tree search" (Zhang et al., Nature Machine
Intelligence 2026 — TongGeometry)**
- *Contribution:* value-guided MCTS that *proposes* and solves; 6.7B aux-construction theorems; generated
  problems adopted by real olympiads; full IMO-geometry-since-2000 coverage on one GPU.
- *Relevance:* proof that generation-to-human-quality works; its "proof difficulty ≫ construction
  complexity" aesthetic metric should upgrade `docs/05`'s interestingness score. Code: GPL-3.0.
- *Limitations:* compute-heavy at full scale; proof-style outputs; GPL.

**5. "Seed-Prover / Seed-Geometry" (ByteDance, arXiv 2507.23726)**
- *Contribution:* lemma-style Lean prover (78.1% of formalized IMO problems) + dedicated geometry engine:
  corpus-statistics-weighted DSL search, 230M generated problems, 43/50 IMO-AG-50, IMO-2025 geometry in 2 s.
- *Relevance:* corpus-weighted grammar sampling is directly adoptable; benchmark ceiling context.
- *Limitations:* geometry engine not released.

## ★★ Subsystem design inputs

**6. "Towards Generating Controllable and Solvable Geometry Problems by Leveraging Symbolic Deduction
Engines" (SDE-GPG, ACL 2025, arXiv 2506.02565)** — knowledge-point-controlled generation with an explicit
difficulty checking function; the closest published analogue to GeoForge's controllable educational
pipeline. School-level ceiling; no code found.

**7. "VeriGeo: Controllable Geometry Question Generation with Numerical and Analytical Verification"
(arXiv 2606.14176, 2026)** — independently converges on GeoForge's dual (numeric + analytic) validation of
generated questions; compare its verification battery against `docs/04` Stages 3–7 for gaps.

**8. "LeanGeo: Formalizing Competitional Geometry Problems in Lean" (arXiv 2508.14644)** — 260-theorem
Lean 4 competition-geometry library + LeanGeo-Bench; the enabling artifact for an optional formal
verification tier.

**9. "FormalGeo: An Extensible Formalized Framework for Olympiad Geometric Problem Solving" (arXiv
2310.18021) + FGeo-HyperGNet (IJCAI 2025) + FGeo-Eval (Symmetry, 2025)** — CDL formal language, 88
predicates/196 theorems, FormalGeo7K/30K datasets; FGeo-Eval's difficulty coefficient and
problem-completion-rate metrics are prior art for `docs/05` calibration. GPL-3.0.

**10. "Wu's Method can Boost Symbolic AI to Rival Silver Medalists" (Sinha et al., 2024)** — Wu's method
alone: 15/30 IMO-AG-30; combined with DDAR exceeds AG1's symbolic baseline. Argues for algebraic methods
as cheap *complementary validators* — exactly the bank-validator third-opinion role proposed here.

**11. "Olympiad-level formal mathematical reasoning with reinforcement learning" (AlphaProof, Nature,
Nov 2025)** — AlphaZero-in-Lean, ~1M autoformalized curriculum, test-time RL on problem variants; IMO 2024
silver. Blueprint for the multi-domain future, not v1.

**12. "Aristotle: IMO-level Automated Theorem Proving" (Harmonic, arXiv 2510.01346)** — Lean proof search
+ informal-lemma formalization + Yuclid geometry solver; formally verified 5/6 at IMO 2025. Validates the
hybrid informal-proposer/formal-verifier pattern and Yuclid's strength.

## ★ Background & surveys

**13. "A Survey of Deep Learning for Geometry Problem Solving" (arXiv 2507.11936)** and **14. "Towards
Geometry Problem Solving in the Large Model Era: A Survey" (arXiv 2506.02690)** — taxonomies of tasks,
datasets (Geometry3K, GeoQA/+, UniGeo, PGPS9K, GeoEval…), methods, and open challenges; both identify
diagram understanding and verifiable reasoning as the field's bottlenecks. Use as dataset/benchmark
directories.

**15. "Penrose: from mathematical notation to beautiful diagrams" (SIGGRAPH 2020)** — constraint-based
diagram specification + optimization-based layout; the intellectual reference for `bank/layout.py` even if
GeoForge keeps its own SVG layouter.

**16. Inter-GPS (ACL 2021) / GeoDRL lineage** — interpretable symbolic solving + neural theorem
prediction on exam datasets; historical context for the FGeo family.

**17. GeoGebra Discovery literature (Kovács, Recio et al., 2021–2024)** — `Discover`/`Prove`/`Compare`
with Gröbner verification; the strongest authoring-time conjecture tools; also a published comparison
correlating algebraic vs. deductive difficulty measures (relevant to difficulty-score validation).
