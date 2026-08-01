# 10 — Development Roadmap & Risk Analysis

## 10.1 Phased roadmap (replaces `docs/09`)

### Phase 0 — Feasibility spikes (2–3 weeks) · *decision gate for the whole pivot*
- **S1 License:** contact Newclid maintainers for a license declaration. No declaration → AG2 DDAR becomes
  primary.
- **S2 Solve spike:** run Newclid and AG2 DDAR on 20 hand-written angle-chase problems (Euclidea-style,
  the mathwithbaddrawings difficulty range). Measure: solve rate, wall time, and — critically — **proof
  trace quality**: can traces be mechanically translated into player-readable steps ("∠BAC = ∠BDC, both
  subtend arc BC")? This is the pivot's #1 unknown.
- **S3 Generation spike:** random construction sampling → closure → enumerate derived numeric angle facts
  as candidate goals → traceback. Verify quantity-goal extraction works on engine output.
- **Gate:** if S2 shows traces can't reach readable steps with bounded effort, the fallback is a *hybrid*:
  homegrown thin rule layer for presentation over the engine's fact closure (engine finds *what's true and
  why*, custom layer re-derives *the pretty path*). Decide here, deliberately.

### Phase 1 — Generator MVP on imported engine (4–6 weeks)
Solver Abstraction Layer; JGEX-compatible sampler with corpus-weighted grammar; goal selection + premise
minimization; numeric degeneracy + well-posedness gates (with configuration-fact fix); attrition report.
**AC:** fixed seed → reproducible batch; 100 validated quantity puzzles across ≥2 difficulty bands;
zero invalid puzzles under AG2 cross-validation.

### Phase 2 — Product bank (4–6 weeks)
Difficulty scorer (DAG features + elegance ratio); interestingness filters; isomorphism dedup; layout +
anti-leak; bank builder + independent validator (AG2 DDAR + numeric + optional Gröbner). Frontend
integration per existing `docs/06`. **AC:** `make bank` → ≥2,000 validated puzzles; spot-check quality
floor from `docs/01` met.

### Phase 3 — Difficulty depth (6–8 weeks)
Aux-construction puzzles via generate-with/hide (Newclid agent API + LLM proposer, engine-verified);
harder tiers; difficulty calibration against self-play data. **AC:** expert band populated; hint UX for
hidden constructions.

### Phase 4 — Formal tier & platform seed (ongoing)
LeanGeo export + verification for featured puzzles; second domain pilot (algebra via SymPy-verified
generation) reusing bank/difficulty/product spine.

## 10.2 Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Newclid license never declared** | Medium | High (blocks primary) | Phase-0 S1; fallback AG2 DDAR (Apache-2.0); abstraction layer makes swap cheap |
| R2 | **Proof traces → readable steps harder than expected** (AR/algebraic steps especially) | **Medium-high** | **High — product-defining** | Phase-0 S2 gate; hybrid presentation layer fallback; restrict v1 goals to puzzles whose traces use whitelisted readable rules (attrition, not failure) |
| R3 | Small-team dependency abandonment (Newclid 95★) | Medium | Medium | Vendor pinned fork; adapter interface; upstream contributions |
| R4 | GPL contamination (Tong/FormalGeo code copied into pipeline) | Low | High | Policy in [07 §7.2](07-open-source-ecosystem.md): ideas-only or subprocess isolation; review at PR time |
| R5 | Quantity-goal mismatch (engines optimized for predicate goals) | Medium | Medium | Phase-0 S3; engines' AR layers do carry numeric angle/ratio values — adapter extracts them |
| R6 | Generated-puzzle quality plateaus at "workmanlike" | Medium | Medium | Accepted in old `docs/07 L2`; elegance-ratio ranking + gem promotion; Tong-style value-guided sampling as the v2 lever |
| R7 | Throughput shortfall for expert band | Low (Yuclid/C++ changes the economics vs. hand-built Python) | Medium | Per-band attrition targets (per earlier review); corpus-weighted grammar; parallel sharding already specced |
| R8 | Frontier LLMs trivially solve all puzzles → perceived product obsolescence | High (already true) | Low-Medium | Product value = curated progression + interaction, same as chess apps post-Stockfish; don't compete on unsolvability |
| R9 | Ecosystem churn (better engine appears mid-build, e.g., Seed-Geometry release) | Medium | Low (opportunity) | Abstraction layer turns churn into upgrades |
| R10 | Owner's learning goal (build-it-yourself) silently lost | Certain unless decided | Personal | Make the reversal of `docs/07 R3` an explicit, recorded decision; the last-resort homegrown backend keeps a sanctioned learning sandbox |

## 10.3 Scalability notes

- **Generation compute:** TongGeometry's 10k-core month targeted olympiad aux-construction depth. GeoForge
  v1 bands need closure-only generation — Yuclid-class engines run constructions in milliseconds-to-seconds;
  a single workstation or the owner's server meets the old 500-puzzles/hour target with margin. Scale-out
  remains embarrassingly parallel (seed-sharded, as specced).
- **Bank scale:** static-shard delivery (unchanged) is CDN-cacheable to millions of users; no server math.
- **Multi-domain scale:** the expensive asset (per-domain oracle) is amortized by the shared product spine;
  Lean-based domains inherit an entire external prover ecosystem's ongoing progress for free.

## 10.4 Expected implementation challenges (honest list)

1. Translating engine proof DAGs into GeoForge's step/highlight JSON (R2) — the real work of the pivot.
2. Mapping the anti-leak layout and figure-pruning logic onto engine-native constructions.
3. Well-posedness semantics on engine premises (configuration facts; carried over from the earlier
   docs review — the flaw and its fix are engine-independent).
4. Debugging across an FFI boundary (Yuclid C++) vs. the old all-Python plan.
5. Keeping determinism guarantees through third-party engines (verify seed plumbing in Phase 0).
