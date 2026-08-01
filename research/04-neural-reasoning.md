# 04 — Neural Networks & LLMs for Mathematical Reasoning

Assessed specifically for what GeoForge can *use*, not the field for its own sake. Bottom line: neural
systems have exactly two safe roles here — **proposing** (auxiliary constructions, search guidance) and
**prose** (rephrasing verified solutions). Every credible system keeps a symbolic verifier in the loop.

## 4.1 Frontier LLMs on olympiad math (2024 → mid-2026)

| Milestone | System | Result | Verified how |
|---|---|---|---|
| IMO 2024 | AlphaProof + AlphaGeometry 2 (DeepMind) | Silver, 28/42 | Lean formal proofs |
| IMO 2025 | **Gemini Deep Think** (DeepMind) | **Gold, 35/42, officially graded** | Natural language, IMO coordinators |
| IMO 2025 | OpenAI experimental model | Gold-level claim | Self-graded — disputed (no IMO judges involved) |
| IMO 2025 | **Aristotle** (Harmonic, arXiv 2510.01346) | Gold-level, 5/6 | **Lean-verified**; geometry via Yuclid |
| IMO 2025 | Seed-Prover (ByteDance) | 5/6 post-contest; 78.1% of past formalized IMO | Lean-verified |
| IMO 2026 (July, Shanghai) | Huawei "Celia"; Xiaohongshu "dots-note 3.0" | **First officially graded 42/42** (press reports; papers pending) | Reported official grading |

Implications for GeoForge: (a) general LLMs can now *solve* most puzzles GeoForge would generate — the
product's value is curation, difficulty calibration, and interaction, not being unsolvable by machines;
(b) LLM-as-solver is still not LLM-as-validator: hallucinated proofs remain routine outside
formally-checked pipelines.

## 4.2 Open RL-trained formal provers (the AlphaProof lineage, but downloadable)

- **Kimina-Prover** (Numina + Kimi): RL "formal reasoning pattern" prover in Lean 4, 72B; ~80%+ miniF2F.
- **DeepSeek-Prover-V2** ([repo](https://github.com/deepseek-ai/DeepSeek-Prover-V2), 1.3k★): subgoal
  decomposition + RL; open weights (custom license).
- **Goedel-Prover-V2** ([repo](https://github.com/Goedel-LM/Goedel-Prover-V2)): scaffolded data synthesis +
  verifier-guided self-correction; strong open-source miniF2F results.
- **BFS-Prover, Aristotle-API, nanoproof** ([Kripner/nanoproof](https://github.com/Kripner/nanoproof),
  MIT): minimal open AlphaProof/HTPS reimplementation — useful for learning the architecture.

Relevance: not needed for v1 geometry (symbolic engines dominate there), but they are the credible
substrate for the **universal-platform vision** (algebra, number theory, combinatorics in Lean).

## 4.3 Neuro-symbolic geometry specifically

- **Proposal-LM + symbolic closure** (AG1/AG2, Newclid's agent API, Seed-Geometry): the proven pattern.
  The LM only suggests auxiliary points; the symbolic engine does all deriving. GeoForge should adopt this
  *unchanged* when it reaches aux-construction puzzles (v2 in the old roadmap).
- **Value-guided tree search** (TongGeometry): replaces the LM with learned value functions over search
  states — cheaper at inference, needs large self-generated training data.
- **HyperGNet / GeoDRL / Inter-GPS lineage**: GNN/RL theorem-predictors over formal geometry systems
  (FormalGeo, Inter-GPS). Achieve high solve rates on exam-level datasets (HyperGNet 88.4% on FormalGeo7K,
  IJCAI 2025). Architecture lesson: encode the fact/proof state as a hypergraph, predict next theorem —
  a plausible future "hint difficulty" model for GeoForge, not a v1 need.
- **Multimodal (diagram-input) models**: per the 2025 surveys (arXiv 2507.11936, 2506.02690), diagram
  *understanding* remains the weakest link in geometry AI. GeoForge generates diagrams from symbolic truth,
  so it sidesteps this entirely — an architectural advantage worth preserving (never OCR/vision in the
  loop).

## 4.4 Search algorithms worth borrowing

| Technique | Source | GeoForge use |
|---|---|---|
| Traceback over deduction DAG | AG1 (open source) | Already specced (`docs/04`); reuse implementation |
| SKEST (shared-knowledge parallel tree search) | AG2 | Only if aux-construction search becomes a bottleneck |
| MCTS with learned value fn | TongGeometry | Later: steer sampler toward high-interestingness regions (the `docs/05 §5.5` anti-goal on feedback loops should be revisited *then*, deliberately) |
| Corpus-weighted construction grammar | Seed-Geometry | Cheap immediate win for sampler weights |
| Test-time RL on problem variants | AlphaProof | Out of scope/budget |

## 4.5 Where LLMs fit in GeoForge (explicit contract)

**Allowed:** auxiliary-construction proposals (engine-verified), solution-prose rephrasing (template output
remains the source of truth), flavor text/hints wording, autoformalization drafts for future domains
(human+machine checked), code assistance.
**Forbidden (unchanged from `docs/01`):** answers, validity, proofs, difficulty labels, anything in the
bank that isn't derivable from the symbolic pipeline. Every serious system surveyed enforces the same
boundary; nothing in 2026 justifies relaxing it.
