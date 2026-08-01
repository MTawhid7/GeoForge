# 08 — Development Guidelines

## 8.1 Working principles

1. **Correctness is the product.** Any change touching `src/geoforge/solvers/`, `generator/`, or
   `bank/validate.py` requires tests in the same commit. A soundness bug is always the repo's top
   priority.
2. **Docs are the spec.** Deviating from `docs/` requires editing the doc in the same commit; recorded
   decisions reverse only via `docs/07`. `research/` is a frozen record — annotate, don't rewrite.
3. **Small vertical slices.** Keep an end-to-end pipeline runnable at all times; "one translator template,
   fully tested, wired to a fixture" beats broad half-layers.
4. **Determinism discipline.** All randomness from explicit seeds (no bare `random` calls); engine seed
   plumbing included. CI runs the pipeline twice on one seed and diffs.
5. **No silent numeric failure.** Numeric/exact mismatches raise with serialized reproductions. Attrition
   happens only at defined gates with logged reasons — never `except: continue`.
6. **Engines are read-only dependencies** (doc 03 §3.6, doc 07 P3). Reference clones are never modified
   in place; GPL clones are never imported (doc 07 P2).

## 8.2 Code standards

- Python 3.12; `ruff` (lint+format); `mypy --strict` on `src/geoforge/`; frozen dataclasses for
  facts/steps/DAG/SAL types.
- TS `strict: true`, ESLint; small stateless components; no geometry math beyond viewport transforms.
- Naming: translation template IDs are `snake_case` and **public API** (appear in puzzle JSON `rule`
  field); renaming one is a schema-affecting change.
- One config module per package under `src/geoforge/config/`; every tolerance/threshold/weight lives
  there; no inline magic numbers.
- Conventional commits, one logical change each.

## 8.3 Testing policy

| Layer | Required tests |
|---|---|
| SAL adapters | Contract suite vs. every backend: determinism double-run diff, fact normalization, DAG integrity, resource-cap surfacing; shared fixture corpus (classic configurations; Langley-with-auxiliary; JGEX dataset samples) |
| Translator | Per-template: positive fixture + a trace it must *refuse* (readability gate); golden-text snapshots per locale |
| Generator | Per-stage attrition snapshot on fixed seed corpus; configuration-fact preservation test (a puzzle whose minimization would previously strip arc-side info must retain it) |
| Well-posedness | Mutation tests: deliberately under-determined puzzle rejected; configuration-flip sample correctly treated as sample-discard, not puzzle-discard |
| Bank validation | Round-trip build → cross-engine re-derivation → schema validation → TS type check; mutation tests (corrupt answer / drop premise ⇒ reject). A validator that never fails is untested |
| Frontend | Rendering snapshot per mark type; solution stepper on fixture puzzle; Playwright happy + wrong-answer paths |

## 8.4 Claude Code session workflow

- Start sessions by naming the task and the governing doc(s); don't paste all docs.
- Engine-adjacent work: run the SAL contract suite before and after (`pytest tests/solvers -q`).
- After generator/scoring/translator changes: run `make bench-batch` (fixed seed) and diff the attrition
  report (per stage **and per band**) against the committed snapshot; investigate drift before commit.
- Never hand-edit generated artifacts (TS types, banks) or reference clones.
- Spec gaps discovered mid-session are resolved by editing the doc in the same commit — never encode an
  undocumented decision only in code.
- Engine version bumps are their own commits: pin change + contract results + attrition diff.

## 8.5 CLAUDE.md

The repository-root `CLAUDE.md` is generated from this doc's rules and must stay in sync with it (same
commit when either changes).

## 8.6 Definition of done (any feature)

Tests written and green · typecheck/lint clean · bench-batch attrition drift reviewed (pipeline changes) ·
relevant doc updated · reproducibility check passes.

**Per phase, additionally:** `ONBOARDING.md` updated from what actually happened (status, verified
commands, new gotchas) — it is the file every new session reads first.
