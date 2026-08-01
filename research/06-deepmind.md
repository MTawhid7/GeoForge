# 06 — Google DeepMind Mathematical Reasoning: Deep Dive

## 6.1 AlphaGeometry (Nature, Jan 2024)

- **Architecture:** neuro-symbolic loop. A symbolic engine (DD: deductive database of geometric rules +
  AR: Gaussian elimination over angle/ratio/distance relations) exhausts derivable facts; when the goal
  isn't reached, a 151M-parameter transformer — trained *only* on synthetic data — proposes an auxiliary
  construction; the engine re-runs; repeat.
- **Training data:** ~100M synthetic theorems from random premise sampling + closure + traceback (~9M with
  auxiliary points). No human demonstrations. This synthetic pipeline is the design ancestor of `docs/04`.
- **Results:** 25/30 IMO-AG-30 (prior art ~10; DDAR alone 14).
- **Open source:** [google-deepmind/alphageometry](https://github.com/google-deepmind/alphageometry),
  Apache-2.0 (weights CC-BY-4.0), 4.9k★ — includes DD+AR, the LM, and the data-generation code.
  Effectively in maintenance-only mode.
- **Reproducibility:** moderate — the JAX/meliad stack and undocumented problem language are the friction
  points (community forks and Newclid exist largely because of this).

## 6.2 AlphaGeometry 2 (arXiv 2502.03544, Feb 2025; JMLR Jan 2026)

- **Upgrades:** expanded language (locus/movement, non-constructive statements, linear equations over
  angles/ratios/distances → coverage of IMO 2000–2024 geometry rises from 66% to 88%); DDAR rewritten for
  speed (C++ core); **SKEST** — dozens of differently-configured tree searches sharing a knowledge base of
  proven facts; proposal LM upgraded to a Gemini-based model; better numeric diagram checking.
- **Results:** 42/50 IMO-AG-50 (above average gold-medalist geometry performance). Part of the IMO 2024
  silver system (solved that year's geometry problem in 19 s).
- **Open source:** [google-deepmind/alphageometry2](https://github.com/google-deepmind/alphageometry2),
  Apache-2.0, Jan 2026 — **the DDAR symbolic engine with examples**, runnable on formalized problems with
  point coordinates. LM weights and SKEST are *not* released.
- **GeoForge significance:** this release is the single biggest reason the from-scratch plan is obsolete —
  a gold-medal-grade deduction+AR engine, permissively licensed, from the team that defined the field.

## 6.3 AlphaProof (IMO 2024; Nature, Nov 2025 — "Olympiad-level formal mathematical reasoning with RL")

- **Architecture:** AlphaZero-style RL agent proving in **Lean**; curriculum of ~1M auto-formalized
  competition problems (Gemini formalizer); MCTS over tactic states; **test-time RL** — generating and
  solving thousands of variants of a hard target problem before attempting it.
- **Results:** IMO 2024: solved P1, P2, P6 (incl. the hardest problem, solved by only 5 humans); with AG2,
  28/42 = silver, one point below gold. P6 took ~3 days — compute far beyond contest conditions.
- **Openness:** **not open source.** Pseudocode in the paper; results repo
  ([alphaproof-nexus-results](https://github.com/google-deepmind/alphaproof-nexus-results)) and community
  reimplementations ([nanoproof](https://github.com/Kripner/nanoproof), MIT) exist.
- **GeoForge relevance:** architectural education only for v1; a template for the eventual multi-domain
  platform (its variant-generation curriculum is a generation idea in disguise).

## 6.4 Gemini Deep Think (IMO 2025 official gold)

35/42 — five of six problems solved **in natural language within contest time limits, graded by official
IMO coordinators**. No Lean, no external tools: parallel "deep think" reasoning traces. Also the engine
behind DeepMind's 2025 IMO-ProofBench work. Available (in capped form) via the Gemini API — the obvious
candidate when GeoForge needs an LLM proposer/rephraser, alongside Claude.

## 6.5 Adjacent DeepMind work

- **AlphaTensor / AlphaDev / FunSearch / AlphaEvolve:** discovery-of-algorithms lineage; AlphaEvolve
  (2025) evolves code with LLM mutations + automated evaluation. Not geometry-relevant, but AlphaEvolve's
  evaluate-loop pattern maps onto "evolve construction-sampler heuristics against interestingness scores"
  — a far-future idea for GeoForge's sampler tuning.
- **IMO-ProofBench / grading research:** rubric-based proof grading benchmarks — relevant later if GeoForge
  ever grades *user-entered* proofs rather than numeric answers.

## 6.6 Assessment

| Project | Usable artifact today | Limitation |
|---|---|---|
| AG1 | Full pipeline code (Apache-2.0), incl. data generation | Aging research code |
| AG2 | DDAR engine (Apache-2.0) | No LM/search released |
| AlphaProof | Paper + pseudocode | Closed; compute-extreme |
| Gemini Deep Think | API access | Closed weights; cost; not a verifier |

DeepMind's strategy is consistent: publish the symbolic/verifiable substrate, keep the neural frontier.
For GeoForge that is exactly the right half to receive for free.
