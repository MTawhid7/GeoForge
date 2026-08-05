# Handover — Phase 3, end of the difficulty rebuild

**Written 2026-08-05.** Branch `feat/generation-rebuild`, **uncommitted and not fully verified.**
Read this with `ONBOARDING.md` (current status, verified commands) and `docs/07` (the record of what
has been tried and reversed). This file is the session-to-session context those two do not carry.

---

## 1. Read this first: the state you are inheriting

`main` is clean and linear at `19c7f4b`. Everything below sits **uncommitted on
`feat/generation-rebuild`**.

| | |
|---|---|
| `ruff check` / `ruff format` | clean |
| `mypy --strict` | clean, 40 source files |
| `tests/generator`, `tests/solvers`, `tests/scoring` | **358 passed in 403 s** |
| `tests/generator/test_corpora.py` | **13 passed** (new file) |
| Full `pytest -q` (incl. `tests/bank`, `tests/schema`, `tests/translation`) | **started, result not seen before the session ended** — treat as unverified |
| Web suite (`tsc`, eslint, vitest, playwright) | **not run** |
| Determinism across `PYTHONHASHSEED` | **not re-run since these changes** |

**Your first task is to finish verifying this branch, not to build on it.** The last full green suite
was 538 tests at `19c7f4b`, before any of this. Three tests were rewritten here (two in
`test_degeneracy.py`, one in `test_layout.py`) and one new file added (`test_corpora.py`, 9 tests).

If verification fails and the cause is not obvious, the safe move is to split the branch: the
degeneracy rescope (§3) is independently valuable and independently verifiable; the seeding work (§4)
is off by default and can wait.

---

## 2. Where the project actually is

The correctness spine is done and works: SAL over two engines, cross-engine validation, byte-reproducible
builds, premise minimization, well-posedness resampling, configuration facts, schema + typed frontend.
That is the expensive half and it is not in question.

**Generation and difficulty measurement are the open problems**, and Phase 3 was four milestones of
finding out how open. Baseline before this branch, seed 42, n=3000:

| | |
|---|---|
| End-to-end yield | 0.83% (25 puzzles) |
| Expert band | **empty** |
| Newclid rules ever used | 13 of 93 |
| Working difficulty instruments | **0 of 4** |

### The four dead difficulty instruments (docs/07 T22)

Do not re-propose these. Each was measured, not argued:

1. **Filter 9, the shortcut check** — cannot be asked of this engine. `SolveOptions` has no step cap,
   `FollowDeductions` ignores its `rules` argument, a saturating closure emits **no** `aconst` (measured:
   all 181 in 117 closures were stated givens), and `ProofState.apply` is write-once so there is one
   justification per fact and no alternative route to find.
2. **`requires_auxiliary`** — zero by definition, not by accident. Forward chaining only derives facts
   about existing points.
3. **`shortcut_margin`** — computed from filter 9, so it does not exist.
4. **`unused_points`** — its replacement; measured to correlate with figure *size*, not difficulty.
   Shipped as a sampler diagnostic, deliberately unscored.

Difficulty is therefore currently decided by proof structure alone — the signal docs/07 T19 measured as
**anti-correlated** with human difficulty in the expert band. That is the hole §6 is meant to fill.

---

## 3. What landed on this branch that is probably right

### The degeneracy rescope (docs/07 T23) — the clear win

`check_figure` rejected the **whole figure** if any one of its C(n,3) point triples was near-flat.
Rejection probability therefore climbed with figure richness: the check was structurally biased against
exactly the figures the product needs.

Ground truth, from human competition figures which are correct by definition:

| | rejected as "degenerate" |
|---|---|
| JGEX textbook configurations | **52%** |
| IMO configurations | **85%** |

Split into two questions: `check_figure` keeps the whole-figure invariants (unrealizable, too few
points, coincident points); `degenerate_triples` returns the flat triples as **data**; `extract.py`
refuses a goal whose own subject triple is flat (`ExtractionReason.DEGENERATE_GOAL`). It had to move to
Stage 5 because Stage 3 runs before the goal is known.

**Measured effect at seed 42, n=3000:** grown-source yield went **0.83% → 5.6%**, distinct answers
9 → 31, and the **expert band went from empty to populated**. `degenerate_goal` fires 204 times, so the
scoped check is doing real work rather than being disabled.

This is the single most valuable change on the branch and it is the part I would fight to keep.

### The `Step.extra` fix

`Step` could not represent a JGEX clause with several comma-separated predicates
(`d = on_line d o h, on_line d a b` — `d` at the intersection of two lines). The first corpus parser
silently kept only the first, leaving the point **underdetermined**, which realizes to a *different
figure* rather than to an error. Caught by a test I wrote expecting it to pass. `Step.extra` and
`Step.all_args` now carry them, and `prune_figure` closes dependencies over `all_args`.

---

## 4. What landed that is NOT yet earning its keep

### Configuration seeding (docs/07 T24) — built, tested, and **off by default**

`src/geoforge/generator/corpora.py` reads **635 human competition configurations** from the Apache-2.0
reference clones (`Newclid/newclid/problems_datasets/`, `alphageometry/`), already in our own JGEX
syntax. 404 are IMO/shortlist/USAMO, 231 are JGEX textbook. All 635 parse. `sampler.decorate` appends
band-palette `s_angle` givens to a skeleton; `sampler.draw` chooses between library and clause growth by
`GENERATION.corpus_share`.

**The probe that justified it and the end-to-end result disagree, and the end-to-end result wins.**

| | probe (goal extraction, 60 skeletons) | end to end (seed 42, n=3000) |
|---|---|---|
| Seeded | 33% yield a goal, 25 distinct answers, 11.1% modal | **1470 constructions → 10 puzzles (0.7%)** |
| Grown | 5.4% | 1530 constructions → 86 puzzles (5.6%) |

Seeded skeletons are **6× better at finding goals and 8× worse at shipping them**, and cost **11×
throughput** (29.9 → 2.7 constructions/s), which also made the test suite unusable.

`corpus_share` is therefore **0.0**. The machinery, tests and docs are all in place; the switch is off.

**Hypothesis for the downstream loss, consistent with the aggregate attrition but NOT yet measured
per-source:** seeded goals die at `translate:unknown_rule`, `translate:unspeakable_conclusion` and
`translate:ar_chain_too_long`. Richer configurations are proved by theorems the 19-rule whitelist cannot
pronounce — and that whitelist is precisely what M7's LLM renderer retires (docs/07 T17). If that holds,
seeding is *gated on M7*, not broken. **The run that would have confirmed this was interrupted. Do it
first.** It is a small script: run `batch.run` twice with `corpus_share` 0.0 and 1.0 and diff
`by_reason()`.

`GENERATION.max_seed_points = 12` was added afterwards to cut the cost tail (keeps 514 of 635; the
library runs to 31 points and closure cost is superlinear). **Every number above predates that cap.**
Re-measure throughput before concluding anything about cost.

---

## 5. Insights worth carrying forward

**Measure the thing you will ship, not the thing that is easy to measure.** The seeding probe measured
goal extraction because that was cheap; the answer it gave was 6× optimistic in the wrong direction. Four
of the five surprises this phase came from a measurement being one stage away from the decision it
informed.

**Reasoning from a predicate's existence to a capability is the recurring failure.** docs/07 T18 claimed
√2 answers were free because `l2const` exists. Nothing *derives* it — all 5 squared constants in 117
closures were assumptions at depth 0, and Pythagoras never fires under Yuclid. Same shape of error in
T7's promotion of ratio/length, and in the P5 plan that proposed *training on* datasets that turned out
to be directly usable.

**Tests that assert a defect look exactly like tests that pass.** Four have now been rewritten across
M4–M6, including one that named the missing band plumbing as its own cause and one that passed on 37
primitives that drew no circles.

**Attrition numbers can be evidence about the measurement rather than the thing measured.** "86%
degeneracy, the sampler is the bottleneck" was partly our own checker refusing correct figures.

---

## 6. What I would do next, in order

1. **Finish verifying this branch.** Full suite (**allow 1800 s** — see §6a), determinism across
   `PYTHONHASHSEED` 0 and 99991, then commit and PR. Split it if verification is messy.
2. **Measure the seeded-vs-grown attrition split** (§4). It is ~20 lines and it decides whether seeding
   is gated on M7 or is a dead end. Re-measure throughput post-`max_seed_points` at the same time.
3. **M7, the LLM renderer** (Gemini 3.6 Flash, content-keyed cache committed with the bank, `--strict`
   forbidding live calls, no test making a network call). It is the only remaining item that *adds*
   puzzles, and on the §4 hypothesis it is also what unblocks seeding.
4. **The LLM difficulty oracle** (docs/07 T25, adopted this session, not built). Promoted from a report
   column to a first-class signal because every deterministic instrument is dead. Same cache mechanism as
   the renderer, which is why they belong in one milestone. Text only — `given[].display`,
   `goal.question`, point labels. **Never coordinates**, or it becomes a protractor that answers every
   angle puzzle.
5. **docs/05 §5.1c ground truth.** 404 olympiad vs 231 textbook skeletons. It cannot rank a puzzle; it
   can refute a scorer, which is the first automatable claim about difficulty this project has had.
6. **M6b**: answer-entropy cap (filter 8) and the configuration table.

---

## 6a. Test and batch runtimes — budget for these, they bit hard

The single most practical thing this session learned the slow way. **Engine closure cost is superlinear
in point count**, and both the test suite and every batch measurement run the engine per construction, so
anything that enlarges figures multiplies wall time everywhere at once.

| what | before this branch | `corpus_share=0.5`, uncapped | this branch as it stands (`corpus_share=0.0`) |
|---|---|---|---|
| Full `pytest -q` | **148 s**, 538 tests | **> 25 min, never completed** (killed) | not yet seen |
| `pytest tests/generator tests/solvers tests/scoring` | ~90 s | **> 600 s**, exceeded the tool timeout | **403 s, 358 passed** |
| Batch throughput | **29.9** constructions/s | **2.7** constructions/s | not re-measured |
| `run(3000, 42)` | ~100 s | **1101 s** (18 min) | not re-measured |

**If a suite hangs, check `corpus_share` first** — it is the one knob worth an order of magnitude.

Note the third column is still ~4x the old targeted-subset time even with seeding off. That is the
degeneracy rescope working as intended: figures that used to be thrown away now proceed to a closure, so
more of the pipeline runs per construction. It buys a 6.8x yield improvement, so it is a good trade — but
it means the "148 s" baseline is gone for good and the full-suite budget should assume several hundred
seconds even on the default configuration.

**One caveat on my own numbers, because it is exactly the trap this section is warning about.** The full
`pytest -q` run at the end of this session was still at ~26% after 40 minutes — but a second pytest
process was running concurrently for part of that, competing for CPU. **That timing is contaminated and
should not be quoted.** The 403 s targeted-subset figure was measured cleanly and is trustworthy. Run the
full suite on an otherwise idle machine before believing any full-suite number, including this file's.

Practical notes:

- **The test suite builds real corpora.** `tests/scoring/test_features.py` runs `run(300, 42)`,
  `tests/generator/test_batch.py` and `tests/bank/test_layout.py` run `run(60, 42)` each, all
  module-scoped fixtures. There is no mocking layer; these are genuine engine runs. That is deliberate
  (docs/08) but it means test time tracks generation cost exactly.
- **Give `pytest -q` at least 1800 s** when anything upstream of Stage 3 has changed, and prefer running
  a targeted subset first — `tests/generator/test_degeneracy.py` and `tests/generator/test_corpora.py`
  are seconds, and catch most of what this branch touches.
- **Run long measurements in the background from the start.** Anything over ~500 constructions will
  exceed a 600 s foreground timeout. Several measurements this session were lost to being started in the
  foreground, and two more were rendered stale because code changed underneath a run already going.
- **Re-check what a background run was measuring before trusting its output.** Two runs completed against
  code that had changed since they started; their numbers were discarded. If you change generator code,
  kill and restart in-flight measurements rather than reading them.
- **`make bank` and the determinism pair are the expensive ones.** The standing verification block in
  `docs/09` runs two full `bank.build --n 400` invocations plus the web e2e suite; budget accordingly and
  do not put it inside a foreground call.

## 7. Traps that cost hours

- **`gh pr merge --rebase` leaves stale remote-tracking refs locally.** `fetch.prune=true` is now set for
  this repo.
- **90° is its own negation mod π.** It hid a validator miscalibration (docs/03 §3.2a) *and* a reflection
  bug in `emit.frame` where every non-90° `aconst` given was negated in the figure the player sees. Any
  new angle fixture should be scalene.
- **The Python (non-Yuclid) engine crashes with `KeyError: '1/2'`** on any figure where r51 is matchable,
  i.e. anything with a midpoint. Known upstream, pinned by
  `test_python_backend_still_hits_unpatched_matcher_bug`. Yuclid is primary for this reason.
- **A numerically false goal raises `ProofBuildError`** rather than returning unsolved.
- **Newclid's valued-predicate attribute names follow no convention** — `angle`, `length`, `value`,
  `square_length`, `square_ratio`. `ConstantRatio` has both a `ratio` field (the segments) and a `value`
  field (the number). Writing that table by inspection got it wrong; it is now pinned per kind by
  behaviour.
- **Seeded figures make the test suite very slow.** If a suite hangs, check `GENERATION.corpus_share`.

---

## 8. Uncommitted files

Modified: `NOTICE`, `ONBOARDING.md`, `docs/04`, `docs/05`, `docs/07`, `docs/09`,
`config/thresholds.py`, `generator/{batch,construction,degeneracy,extract,sampler,traceback}.py`,
`tests/bank/test_layout.py`, `tests/generator/test_degeneracy.py`.

New: `src/geoforge/generator/corpora.py`, `tests/generator/test_corpora.py`.

Untracked and **not mine to commit** — decide and either ignore or add: `.claude/`.

Scratchpad probes (throwaway, not in the repo) are under
`/private/tmp/claude-501/-Users-tawhid-Documents-GeoForge/291944db-f1f3-429d-9d19-bb49b4a81dce/scratchpad/`:
`probe_corpora.py`, `probe_hybrid.py`, `spike_quantities.py`, `m5_aux.py`. `probe_hybrid.py` is the one
worth re-reading — it is the measurement §4 says to redo properly.

---

## 9. Doc changes made this session

- **docs/07 T23** (new) — degeneracy rescope, with the 52%/85% ground truth.
- **docs/07 T24** (new) — configuration seeding, its licensing, and the honest yield comparison.
- **docs/07 T25** (new) — LLM oracle promoted to a first-class difficulty signal.
- **docs/07 L4** — amended: part of "86% degenerate" was our own checker.
- **docs/05 §5.0** — amended: layer 1 is down to one gate, layer 2 is empty.
- **docs/05 §5.1c** (new) — difficulty ground truth.
- **docs/04** — Stage 1 two sources, Stage 3 rescoped.
- **docs/09** — M6 rewritten; the learned value model dropped from near-term P5.
- **NOTICE** — attribution for the configuration library.
