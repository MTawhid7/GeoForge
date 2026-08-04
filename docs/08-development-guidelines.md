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
7. **The LLM writes prose and nothing else** (added 2026-08-04, doc 07 T17). It may populate
   `solution[].text` and `given[].display`; doc 02 invariant 5 enumerates every field it may not touch,
   and that list is exhaustive by design. Three rules follow for anyone working near the renderer:
   never send it a goal, an answer, or a figure — it renders one already-proved step at a time and
   cannot solve what it is never shown; never accept a sentence that has not passed the fidelity check;
   and never make a live call in a code path a bank build depends on, because reproducibility comes from
   the cache (doc 02 invariant 6), not from the model.
8. **Measure before you write it down** (added 2026-08-04). The difficulty model shipped a whole phase
   on the unexamined assumption that a longer proof is a harder puzzle, and one playtest refuted it
   (doc 07 T19). Any claim about what the corpus contains — band distributions, answer variety, figure
   richness, how often a gate fires — goes in a doc only with the number that supports it and the seed
   it was measured at. "A gate that never fires is untested" is the same principle applied to code.

## 8.2 Code standards

- Python 3.12; `ruff` (lint+format); `mypy --strict` on `src/geoforge/`; frozen dataclasses for
  facts/steps/DAG/SAL types.
- TS `strict: true`, ESLint; small stateless components; no geometry math beyond viewport transforms.
- Naming: translation template IDs are `snake_case` and **public API** (appear in puzzle JSON `rule`
  field); renaming one is a schema-affecting change. Since 2026-08-04 a step rendered from an
  untemplated rule carries the namespaced engine rule id instead (doc 03 §3.5a item 1) — also public
  API, and also not renameable at will. Adding a template for such a rule *changes* the published
  `rule` value, so it is a schema-affecting change too, not a cosmetic improvement.
- One config module per package under `src/geoforge/config/`; every tolerance/threshold/weight lives
  there; no inline magic numbers.
- Conventional commits, one logical change each.
- **Branch per milestone; PR; rebase merge; linear history** (settled 2026-08-04). `main` stays stable
  and is never committed to directly. A milestone branch carries several conventional commits, opens as
  a PR via `gh`, and merges with `--rebase` once `make lint typecheck && uv run pytest -q` and the
  bench-batch attrition diff are clean. The repo is configured rebase-only (merge and squash are
  disabled) so the setting enforces the rule rather than relying on memory.
  *Why rebase and not squash:* squashing collapses a milestone into one commit, which contradicts the
  line above — and the one-logical-change granularity is exactly what makes `git bisect` worth having on
  a pipeline where a soundness bug is the top-priority failure. *Why not a merge commit:* on a
  single-developer repo with hours-long branches it buys topology nobody reads.

## 8.3 Testing policy

| Layer | Required tests |
|---|---|
| SAL adapters | Contract suite vs. every backend: determinism double-run diff, fact normalization, DAG integrity, resource-cap surfacing; shared fixture corpus (classic configurations; Langley-with-auxiliary; JGEX dataset samples) |
| Translator (templates) | Per-template: positive fixture + a trace it must *refuse*; golden-text snapshots per locale |
| Step renderer (LLM) | Fidelity check unit-tested from both sides — a sentence naming a point the step does not involve must be rejected, and a correct sentence must be accepted (a checker that rejects everything passes half a test suite). Golden fixtures: every templated rule rendered through the LLM path must stay semantically equivalent, run in CI against the cache so it costs no calls. Cache-key test: same step ⇒ same key ⇒ no network call. **No test may make a live API call** |
| Difficulty gates | Every gate needs a reject/near-miss pair *and* a measured firing rate on the real corpus committed alongside: a gate that quietly stops firing looks exactly like success. Applies to filter 8 (answer entropy) and the configuration table; **filter 9 (shortcut) is not implementable on this engine and must not be re-attempted without reading doc 05 §5.2 filter 9 first.** The same rule has a second edge, learned in M5: a *feature* whose value never varies, or which measures something other than its name (`requires_auxiliary`, `unused_points`), is as misleading as a gate that never fires — so a new scored feature needs its correlation against the existing ones committed before it gets a weight |
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
