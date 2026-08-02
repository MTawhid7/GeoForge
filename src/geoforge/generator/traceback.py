"""Stage 6: traceback, premise minimization, figure pruning (docs/04).

Three things happen here, in order:

1. **Minimal sub-DAG.** The engine's trace is goal-relative but not minimal — it records the
   derivation it found, which can carry premises the goal does not need. We re-select the
   cheapest hyperpath to the goal.
2. **Premise minimization.** Greedily drop stated premises and re-run a restricted closure,
   keeping every drop the goal survives. Redundant givens feel sloppy and leak hints.
   **Configuration facts are never dropped** — see below.
3. **Figure pruning.** Scaffolding no surviving fact mentions is removed from the drawn figure.

Configuration facts (`sameside`, `sameclock`, `ncoll`, ... — `CONFIGURATION_KINDS`) are
first-class here. No rule consumes them symbolically, so a minimizer that treats premises
uniformly strips them all and produces a puzzle whose answer silently depends on a
configuration nobody stated. That was the central soundness hole in the pre-pivot design; the
fix is that minimization never even considers them.

Greedy minimization gives a *locally* minimal premise set, not a globally minimum one: the
result depends on the order premises are tried in. The order is canonical (sorted by fact id),
so it is at least deterministic, which is what reproducibility needs (docs/02 invariant 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from geoforge.config import MINIMIZATION
from geoforge.generator.construction import Construction
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import (
    Fact,
    FactId,
    PremiseSpec,
    ProofDAG,
    ProofStep,
    SolveOptions,
    distinct_rules,
)


@dataclass(frozen=True, slots=True)
class SubDAG:
    """The minimal derivation of one goal."""

    goal: FactId
    facts: tuple[Fact, ...]
    steps: tuple[ProofStep, ...]
    premises: tuple[Fact, ...]
    """Stated leaves: what the puzzle gives the solver. Minimizable."""
    configuration: tuple[Fact, ...]
    """Configuration leaves. Premises for correctness, never minimized, and what disambiguates
    the directed-to-vertex angle conversion in M4."""
    trivial: tuple[Fact, ...] = ()
    """Tautologies the engine supplies for itself (`eqangle a o c o a o c o`). They are leaves
    of the derivation but they are not premises: the puzzle must not state them, and they must
    never be fed back as assumptions — Yuclid aborts with "Trying to re-prove a statement" when
    asked to assume something it derives as trivially true."""

    @property
    def depth(self) -> int:
        return ProofDAG(
            facts=self.facts,
            steps=self.steps,
            assumptions=tuple(f.fact_id for f in self.premises),
            numerical_checks=tuple(f.fact_id for f in self.configuration),
            trivial=tuple(f.fact_id for f in self.trivial),
            proved_goals=(self.goal,),
            unproved_goals=(),
        ).depth()

    @property
    def distinct_rules(self) -> int:
        """Conceptual variety of *this* derivation — the number that ships (docs/05 §5.1)."""
        return distinct_rules(self.steps)

    @property
    def width(self) -> int:
        """Total rule applications in the minimal derivation (docs/05 §5.1 `width`)."""
        return len(self.steps)

    def points(self) -> frozenset[str]:
        """Every point any surviving fact mentions."""
        return frozenset(arg for fact in self.facts for arg in fact.args)


@dataclass(frozen=True, slots=True)
class FigurePruning:
    """Which construction steps survive into the drawn figure."""

    kept_points: frozenset[str]
    kept_steps: tuple[int, ...]
    """Indices into the original construction's steps, in order."""
    dropped_steps: tuple[int, ...]

    def construction(self, original: Construction) -> Construction:
        return Construction(steps=tuple(original.steps[i] for i in self.kept_steps))


def minimal_subdag(dag: ProofDAG, goal: FactId) -> SubDAG | None:
    """Select the cheapest derivation of `goal` from the traced DAG.

    Cost is proof size — 1 per step plus the cost of its premises — minimized by relaxation
    over the hypergraph (the hypergraph generalization of shortest paths; a plain BFS is wrong
    here because a step has several premises, not one). Ties break on fewer distinct premises,
    then on the step's canonical ordering so the choice is deterministic.
    """
    index = dag.index()
    if goal not in index:
        return None

    derivations: dict[FactId, list[ProofStep]] = {}
    for step in dag.steps:
        derivations.setdefault(step.conclusion, []).append(step)

    leaves = set(dag.assumptions) | set(dag.numerical_checks) | set(dag.trivial)
    cost: dict[FactId, tuple[int, int]] = {fid: (0, 0) for fid in leaves if fid in index}
    chosen: dict[FactId, ProofStep] = {}

    # Relax until nothing improves. Bounded by the number of facts: each pass fixes at least
    # one fact's cost or the loop stops.
    for _ in range(len(index) + 1):
        changed = False
        for fid, steps in derivations.items():
            best: tuple[tuple[int, int], ProofStep] | None = None
            for step in steps:
                if any(p not in cost for p in step.premises):
                    continue
                size = 1 + sum(cost[p][0] for p in step.premises)
                candidate = ((size, len(set(step.premises))), step)
                if best is None or candidate[0] < best[0]:
                    best = candidate
            if best is not None and (fid not in cost or best[0] < cost[fid]):
                cost[fid] = best[0]
                chosen[fid] = best[1]
                changed = True
        if not changed:
            break

    if goal not in cost:
        return None

    # Walk back from the goal through the chosen steps only.
    kept_steps: list[ProofStep] = []
    kept_facts: set[FactId] = set()
    stack = [goal]
    while stack:
        fid = stack.pop()
        if fid in kept_facts:
            continue
        kept_facts.add(fid)
        deriving = chosen.get(fid)
        if deriving is None:
            continue
        kept_steps.append(deriving)
        stack.extend(deriving.premises)

    facts = tuple(sorted(index[fid] for fid in kept_facts if fid in index))
    used_leaves = tuple(f for f in facts if f.fact_id not in chosen)
    trivial_ids = set(dag.trivial)
    return SubDAG(
        goal=goal,
        facts=facts,
        steps=tuple(sorted(kept_steps)),
        premises=tuple(
            f for f in used_leaves if not f.is_configuration and f.fact_id not in trivial_ids
        ),
        configuration=tuple(f for f in used_leaves if f.is_configuration),
        trivial=tuple(f for f in used_leaves if f.fact_id in trivial_ids),
    )


@dataclass(frozen=True, slots=True)
class MinimizationOutcome:
    kept: tuple[Fact, ...]
    engine_errors: tuple[str, ...] = ()
    """Attempts the engine could not answer. A failed attempt keeps the premise — the safe
    direction, since an unanswered "is this premise needed?" must not be read as "no". Recorded
    rather than swallowed: one abort is attrition, a rising count is a defect (docs/08 §8.1)."""


def minimize_premises(
    backend: SolverBackend,
    points: tuple[tuple[str, float, float], ...],
    premises: tuple[Fact, ...],
    configuration: tuple[Fact, ...],
    goal: Fact,
    opts: SolveOptions | None = None,
) -> MinimizationOutcome:
    """Greedily drop stated premises while the goal still follows.

    Each attempt is one engine call over the same fixed coordinates, so configuration facts
    stay available to the engine's numerical checks whatever is dropped — which is exactly why
    dropping a *stated* premise is a real weakening and dropping a configuration fact would not
    be. Configuration facts are passed through untouched and are never candidates.
    """
    if not MINIMIZATION.minimize_premises:
        return MinimizationOutcome(kept=premises)

    opts = opts or SolveOptions()
    kept = list(premises)
    errors: list[str] = []
    for candidate in sorted(premises)[: MINIMIZATION.max_premise_drop_attempts]:
        trial = [f for f in kept if f != candidate]
        if len(trial) == len(kept):
            continue
        spec = PremiseSpec(points=points, premises=tuple(trial) + configuration, goals=(goal,))
        try:
            result = backend.solve_facts(spec, opts)
        except Exception as exc:  # engine-level failure, not a mathematical answer
            errors.append(f"{candidate.fact_id}: {type(exc).__name__}: {exc}")
            continue
        if result.solved:
            kept = trial
    return MinimizationOutcome(kept=tuple(sorted(kept)), engine_errors=tuple(errors))


def prune_figure(construction: Construction, needed: frozenset[str]) -> FigurePruning:
    """Drop construction steps whose points nothing surviving refers to.

    A step is kept if it introduces a needed point, or if a kept step depends on a point it
    introduces — dependencies are closed transitively, because a figure that draws a point
    whose defining scaffolding was removed cannot be drawn at all.

    Callers must include anything a translated solution step highlights in `needed`: a step may
    name a segment its premises only imply (docs/04 Stage 6).
    """
    required = set(needed)
    for _ in range(len(construction.steps) + 1):
        grew = False
        for step in construction.steps:
            if required.isdisjoint(step.outputs):
                continue
            for arg in step.args:
                if arg not in required and any(arg in s.outputs for s in construction.steps):
                    required.add(arg)
                    grew = True
        if not grew:
            break

    kept = tuple(
        i for i, step in enumerate(construction.steps) if not required.isdisjoint(step.outputs)
    )
    dropped = tuple(i for i in range(len(construction.steps)) if i not in set(kept))
    return FigurePruning(kept_points=frozenset(required), kept_steps=kept, dropped_steps=dropped)


@dataclass(frozen=True, slots=True)
class Derivation:
    """A goal plus its minimized, prunable derivation — Stage 6's output."""

    goal: Fact
    subdag: SubDAG
    premises: tuple[Fact, ...]
    """After minimization. A subset of `subdag.premises`."""
    configuration: tuple[Fact, ...]
    dropped_premises: tuple[Fact, ...]
    engine_errors: tuple[str, ...] = ()
    """Minimization attempts the engine failed to answer; the premise was kept."""

    @property
    def depth(self) -> int:
        return self.subdag.depth

    @property
    def distinct_rules(self) -> int:
        return self.subdag.distinct_rules

    @property
    def width(self) -> int:
        return self.subdag.width

    def needed_points(self) -> frozenset[str]:
        return frozenset(
            arg for fact in (*self.premises, *self.configuration, self.goal) for arg in fact.args
        )


def derive(
    backend: SolverBackend,
    points: tuple[tuple[str, float, float], ...],
    dag: ProofDAG,
    goal: Fact,
    opts: SolveOptions | None = None,
) -> Derivation | None:
    """Run the whole of Stage 6 for one verified goal.

    Minimization starts from the derivation's leaves rather than from every stated premise:
    a premise the trace never used is already absent from the sub-DAG, so re-testing it would
    buy an engine call for a known answer.
    """
    subdag = minimal_subdag(dag, goal.fact_id)
    if subdag is None:
        return None

    outcome = minimize_premises(backend, points, subdag.premises, subdag.configuration, goal, opts)
    dropped = tuple(sorted(set(subdag.premises) - set(outcome.kept)))

    if dropped:
        # The proof recorded above is the proof from the *unminimized* premises. Re-derive from
        # what survived, so the steps M4 translates are the steps the stated givens support —
        # otherwise a solution could cite a premise the puzzle no longer states.
        spec = PremiseSpec(
            points=points, premises=outcome.kept + subdag.configuration, goals=(goal,)
        )
        try:
            again = backend.solve_facts(spec, opts or SolveOptions())
        except Exception:
            # Keep the unminimized derivation rather than shipping a proof that cites premises
            # the puzzle no longer states.
            return None
        reduced = minimal_subdag(again.proof_dag, goal.fact_id) if again.solved else None
        if reduced is None:
            return None
        subdag = reduced

    return Derivation(
        goal=goal,
        subdag=subdag,
        premises=outcome.kept,
        configuration=subdag.configuration,
        dropped_premises=dropped,
        engine_errors=outcome.engine_errors,
    )
