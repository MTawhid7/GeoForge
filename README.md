# GeoForge — Geometry Puzzle Generator

GeoForge generates an unlimited supply of valid, well-posed, interesting geometry puzzles — find an
unknown **angle, length, ratio, or shaded area** (quantity types enabled in waves; **angle and area
are registered**, length and ratio deferred — `docs/04 §QTR`) — with
machine-verified, human-readable step-by-step solutions, delivered as a static Euclidea-like web app.

**Architecture in one paragraph:** an offline Python pipeline samples random geometric constructions,
computes their deductive closure with an imported AlphaGeometry-lineage engine (**Newclid 3 / Yuclid**),
selects derived numeric facts deep in the proof DAG as puzzle goals, traces back minimal premises,
translates the traced proof into readable solution steps, gates on well-posedness and difficulty, and
packs survivors into a validated JSON bank — every puzzle independently re-derived by a *second* engine
(**AlphaGeometry 2 DDAR**) before it can ship. A static React/TS frontend renders the JSON as-is. LLMs
never touch the correctness path.

## Repository map

| Path | Contents |
|---|---|
| `docs/` | **Authoritative specification** (01-overview … 10-area-layer). Read the doc for the subsystem you touch |
| `research/` | Frozen research record behind the 2026 build-on-existing-engines pivot |
| `CLAUDE.md` | Project conventions for Claude Code sessions (kept in sync with docs/08) |
| `src/geoforge/` | Pipeline code: `solvers/` (engine adapters), `generator/`, `scoring/`, `bank/` *(to be created — see docs/09 P0)* |
| `web/` | Frontend TS workspace *(to be created)* |
| `banks/` | Built puzzle banks (generated artifacts — never hand-edited) |
| `Newclid/`, `alphageometry/`, `alphageometry2/`, `mathlib4/`, `penrose/`, `sympy/`, `tong-geometry/` | **Read-only reference clones.** Study freely; never modify; never copy from GPL clones (docs/07 P2). Excluded from the repo once git is initialized |

## Getting started

1. Read `docs/01-project-overview.md` (why and what), then `docs/02-architecture.md` (how).
2. Current work: **Phase 0 feasibility spikes** — `docs/09-roadmap.md`.
3. Working in a Claude Code session: point it at the specific doc(s) governing the task; conventions load
   automatically from `CLAUDE.md`.

## Glossary

- **Construction:** ordered sequence of primitive steps (JGEX-compatible) defining a figure symbolically.
- **Fact:** typed geometric statement about the figure (angle values, equalities, cyclicity…).
- **Proof/Deduction DAG:** graph whose nodes are facts and whose hyperedges are rule applications,
  recorded by the engine.
- **SAL:** Solver Abstraction Layer — the adapter interface behind which engines live (`docs/03`).
- **Goal:** the single numeric fact the player must find.
- **Traceback:** extraction of the minimal sub-DAG (premises + rule chain) deriving the goal.
- **Configuration facts:** the figure's topological facts (betweenness, arc side, orientation) treated as
  implicit premises — the figure is part of the puzzle statement (`docs/07` T2).
- **Well-posed:** stated premises + configuration facts uniquely determine the goal quantity.
- **Readability gate:** a puzzle ships only if every proof step translates through the readable-step
  whitelist (`docs/03` §3.5).
