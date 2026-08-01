# 05 — Symbolic Engines & Formal Proof Systems

## 5.1 Proof assistants

### Lean 4 + mathlib — the ecosystem winner
- [leanprover-community/mathlib4](https://github.com/leanprover-community/mathlib4): Apache-2.0, 3.7k★,
  pushed daily. Every serious ML-prover effort (AlphaProof, Seed-Prover, Kimina, DeepSeek-Prover, Goedel,
  Aristotle) targets Lean. For any long-term "universal mathematics platform", Lean is the substrate —
  network effects are decisive.
- **Geometry gap, now partially closed:** mathlib's synthetic Euclidean geometry was historically thin
  (`EuclideanGeometry` is analytic). **LeanGeo** (arXiv 2508.14644) adds a unified competition-geometry
  layer: 260 formally proved theorems, high-level declarative tactics, mathlib integration, and
  **LeanGeo-Bench** (IMO-level formal geometry benchmark).
- **LeanEuclid / E** ([loganrjmurphy/LeanEuclid](https://github.com/loganrjmurphy/LeanEuclid), MIT, 139★):
  formalizes Euclid's *Elements* with implicit diagrammatic reasoning made explicit — academically elegant,
  relevant to figure-consistency semantics, not an engineering dependency.
- **GeoForge use:** optional **formal tier** — export flagship/featured puzzles' solutions to LeanGeo and
  machine-check them. Marketing-grade guarantee ("this puzzle's solution is formally verified") at modest
  cost. Not in the generation hot path.

### Rocq (Coq) / GeoCoq
[GeoCoq/GeoCoq](https://github.com/GeoCoq/GeoCoq): LGPL-3.0, 207★, pushed Nov 2025. The deepest
formalization of foundational geometry (Tarski/Hilbert axiom systems, parallel-postulate equivalences).
Scholarly reference for axiomatic subtleties; no automation relevant to generation; smaller ML ecosystem
than Lean. **Not recommended** as a dependency.

### Isabelle/HOL, HOL Light
Mature, powerful (Sledgehammer automation; HOL Light hosts Harrison's geometry/analysis work and the
Flyspeck project). But the ML-for-math community consolidated on Lean; choosing these means swimming
against tooling and model availability. **Not recommended** for this project.

## 5.2 SMT and algebraic decision procedures

- **Z3 / cvc5** (MIT/BSD): encode coordinates as reals, geometry facts as polynomial constraints → decide
  satisfiability. Useful for **impossibility/ambiguity detection** (e.g., "does a configuration satisfying
  premises with a different goal value exist?" — a complement to GeoForge's numeric well-posedness
  sampling). Caveats: nonlinear real arithmetic is expensive and incomplete in practice; treat as an
  *additional* validator where numeric sampling is inconclusive, budgeted per-puzzle.
- **Wu's method / Gröbner bases**: decide equational geometry statements; certificates unreadable. A
  Gröbner check (via SymPy or Giac) is a cheap third opinion for the bank validator on equality-type facts.

## 5.3 Computer algebra systems

| System | License | Fit |
|---|---|---|
| **SymPy** ([sympy/sympy](https://github.com/sympy/sympy), 14.8k★, daily pushes) | BSD | Exact rational/symbolic arithmetic, `sympy.geometry` (slow but fine for spot validation), Gröbner bases. The natural in-process CAS for the Python pipeline — adopt for validation math, per the old `docs/07 R5` plan but earlier |
| SageMath | GPL | Heavyweight; unnecessary given SymPy + specialized engines |
| Mathematica / Maple | Proprietary | Capable but license-hostile to an open pipeline; no |
| NumPy (already planned) | BSD | Stays: vectorized numeric checks |

## 5.4 Verdict

Lean 4 (+LeanGeo) is the only formal system worth adopting, and only as an optional verification tier and
the future multi-domain substrate. SymPy joins the numeric-validation layer immediately. Z3 and a Gröbner
check are cheap optional validators. Rocq/Isabelle/HOL Light: reference material only.
