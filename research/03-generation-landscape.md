# 03 — Geometry Problem Generation Landscape

This is GeoForge's core need, and the area where the research picture changed most since `docs/` was
written. Two distinct traditions exist — **synthetic-data pipelines** (generate millions of problems to
train provers) and **educational generators** (generate curriculum problems with knowledge-point control).
GeoForge's product sits between them and borrows from both.

## 3.1 Synthetic-data pipelines (high difficulty, high volume, validated by construction)

### AlphaGeometry's synthetic pipeline (open source, Apache-2.0)
The reference design — and structurally identical to `docs/04`:
1. Sample a random construction from a DSL of premise clauses.
2. Run symbolic closure (DD+AR) to derive all consequences, recording the proof DAG.
3. Pick derived facts as goals; **traceback** extracts minimal premises and proof.
4. Crucially: premises used by the proof but *not* in the goal's dependency closure become **auxiliary
   constructions** — this is how AG mined 100M theorems incl. ~9M with auxiliary points, the training
   signal for its LM.
Every generated problem is valid *by construction* (the proof is the derivation). This validates the
`docs/04` attrition-pipeline philosophy — and its reference implementation ships in the AG1 repo.

### TongGeometry (BIGAI + PKU; *Nature Machine Intelligence*, s42256-025-01164-x)
State of the art in *quality-targeted* generation:
- **Method:** guided tree search grows constructions step-by-step; learned value functions steer both
  *proposing* (which construction extensions are promising) and *solving*; MCTS-style traversal.
- **Scale:** 10,000 rented CPU cores × 30 days → **6.7B theorems requiring auxiliary constructions**
  (4.1B with geometric symmetry).
- **Aesthetics as a metric:** a proposition is deemed olympiad-worthy when *proof difficulty far exceeds
  construction complexity* — a formalization of "elegance" directly analogous to `docs/05`'s
  interestingness heuristics (short-insight-path vs. long-alternate-path).
- **External validation:** three generated problems were **selected by real olympiad committees** (a China
  national-team qualifying exam and a top US olympiad) — the strongest human-quality evidence any generator
  has produced.
- **Solving:** all IMO geometry since 2000, ≤38 min on one consumer GPU.
- **Caveats:** GPL-3.0 code ([bigai-ai/tong-geometry](https://github.com/bigai-ai/tong-geometry), 45★);
  outputs are *prove-this* propositions, not numeric quantity puzzles; compute for full-scale runs is
  beyond a hobby budget (though GeoForge's difficulty band needs far shallower search).

### Seed-Geometry (ByteDance)
Generated **230M unique problems** by extensive search over a compact DSL, using frequency statistics from
20+ years of olympiad problems to weight the construction grammar — a data-driven version of `docs/04`'s
"weighted grammar, tune empirically". Engine not released; the *grammar-weighting-from-corpus* idea is
directly reusable.

## 3.2 Educational generators (difficulty/knowledge-point control, lower ceiling)

| System | Venue | Approach | Relevance |
|---|---|---|---|
| **SDE-GPG** (arXiv 2506.02565) | ACL 2025 | Knowledge points → formal definitions → symbolic deduction → filter → text+diagram; explicit difficulty checking function | Closest published analogue of GeoForge's controllable pipeline; school-level ceiling |
| **VeriGeo** (arXiv 2606.14176) | 2026 | Controllable generation with **numerical + analytical verification** of every emitted problem | Independently converges on GeoForge's dual-validation design; worth a close read |
| **GeoProblem Factory** (AAAI 2026 demo) | AAAI | Visual front-end over a solvable/controllable generation pipeline | UX reference for an authoring tool |
| **GeoUni / GeoFM** (arXiv 2510.27448 etc.) | 2025 | Generate aligned diagram+text training data via formal language for MLLM training | Diagram-text consistency techniques |
| **AMC-style AIED work** (e.g., difficulty-controlled QG) | AIED | LLM generation with difficulty conditioning | Weak validity guarantees; not correctness-path material |

**Key observation:** educational generators control *knowledge points*; synthetic pipelines control
*validity and depth*; none controls *player-perceived difficulty for a consumer puzzle app*. GeoForge's
proof-DAG difficulty scoring (`docs/05`) remains novel and custom.

## 3.3 Do these systems generate random / validated / novel / human-level problems?

| | Random | Validated | Novel | Human-level |
|---|---|---|---|---|
| AG synthetic pipeline | Yes (uniform sampling) | **By construction** | Mostly workmanlike | No (median is dull) |
| TongGeometry | Guided (value function) | By construction + search | **Yes** | **Yes — competition-selected** |
| Seed-Geometry | Corpus-weighted | By construction | Partly | Training-grade |
| SDE-GPG / VeriGeo | Constraint-directed | Checked post-hoc | Limited | School-level |
| LLM-direct generation | — | **No (unreliable)** | Superficially | No |

The consistent lesson across all serious systems: **LLMs never generate the problem; a symbolic system
does, and validity comes from the derivation itself.** GeoForge's `docs/01` non-goal ("no LLM in the
correctness path") is unanimously confirmed by the field.

## 3.4 What GeoForge's generator still must add on top of any engine

1. **Quantity-goal conversion** — turning derived numeric facts (angle = 40°) into find-the-value puzzles;
   AG-family goals are predicates, FormalGeo-style goals are numeric. A thin adapter over the engine's
   derived-fact store.
2. **Well-posedness gating** (premises uniquely determine the value) — no external system does this;
   `docs/04` Stage 7 (with the configuration-fact fix from prior review) stays.
3. **Difficulty banding for humans** — `docs/05` scoring over the traced proof DAG stays.
4. **Premise minimization + figure pruning + anti-leak layout** — product-specific; stays.
5. **Interestingness / dedup at bank scale** — stays (TongGeometry's aesthetic metric is a good upgrade to
   `docs/05 §5.3`: score = proof depth ÷ construction complexity).
