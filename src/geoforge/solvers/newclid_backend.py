"""Newclid backend adapter (docs/03 §3.2).

The only module in GeoForge that touches Newclid's classes. Everything else consumes the
engine-neutral types in `geoforge.solvers.types`.

Backend selection: Yuclid (C++) is primary. Phase 0 measured it 23-26x faster than the
pure-Python path on non-trivial problems, and the pure-Python rule matcher cannot apply
rules containing numeric constants (BUG-2, unpatched — see `_patches`). Pure-Python remains
selectable for debugging only.
"""

from __future__ import annotations

import time
from fractions import Fraction
from typing import Any

import numpy as np
from newclid.api import GeometricSolverBuilder, PythonDefault
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.problem import predicate_to_construction
from newclid.proof_data import ProofData, ProofId, proof_data_from_state

from geoforge.config import SOLVER
from geoforge.solvers.types import (
    Fact,
    FactId,
    FactKind,
    Justification,
    JustificationKind,
    ProblemSpec,
    ProofDAG,
    ProofStep,
    RealizedFigure,
    SolveOptions,
    SolveResult,
    SolveStats,
)

ENGINE_NAME = "newclid"

_JUSTIFICATION_KINDS: dict[str, JustificationKind] = {
    "Assumption": JustificationKind.ASSUMPTION,
    "Numerical Check": JustificationKind.NUMERICAL_CHECK,
    "Rule Application": JustificationKind.RULE_APPLICATION,
    "AR Deduction": JustificationKind.AR_DEDUCTION,
    "Line Merge": JustificationKind.LINE_MERGE,
    "Circle Merge": JustificationKind.CIRCLE_MERGE,
    "Direct Consequence": JustificationKind.DIRECT_CONSEQUENCE,
    "Reflexivity": JustificationKind.REFLEXIVITY,
}


class UnsupportedFactKind(ValueError):
    """An engine predicate has no place in our vocabulary.

    Raised rather than skipped: silently dropping facts would corrupt the proof DAG and
    could make an unsound puzzle look well-formed.
    """


def _engine_version() -> str:
    from importlib.metadata import version

    return str(version("newclid"))


def _fact_from_predicate(predicate: Any) -> Fact:
    """Map a Newclid predicate onto our canonical vocabulary.

    Newclid canonicalizes arguments on construction (symmetric args sorted), so `to_tokens()`
    is already the canonical form and we do not re-sort.
    """
    raw_kind = str(predicate.predicate_type.value)
    try:
        kind = FactKind(raw_kind)
    except ValueError as exc:
        raise UnsupportedFactKind(
            f"Newclid predicate {raw_kind!r} is not in the GeoForge fact vocabulary. "
            "Add it to FactKind (and decide whether it is a configuration fact) rather "
            "than dropping it."
        ) from exc

    tokens = tuple(str(t) for t in predicate.to_tokens())
    value = _value_of(predicate, kind)
    # A valued fact's value lives in `value`, not in the argument list, so that the same
    # geometric object with different values shares a stable argument tuple.
    args = tokens[:-1] if value is not None and tokens else tokens
    return Fact(kind=kind, args=args, value=value)


def _fact_from_construction(construction: Any) -> Fact | None:
    """Map a `PredicateConstruction` (the un-instantiated form used for a problem's declared
    assumptions) onto our vocabulary.

    Distinct from `_fact_from_predicate`: constructions expose `predicate_type`/`args` but no
    `to_tokens`, and carry no numeric value. Returns None for predicates outside our
    vocabulary — unlike derived facts, an unmapped *declared* assumption is not a soundness
    risk, it just means Stage 3 has one less exemption to work with.
    """
    try:
        kind = FactKind(str(construction.predicate_type.value))
    except ValueError:
        return None
    return Fact(kind=kind, args=tuple(str(a) for a in construction.args))


def _value_of(predicate: Any, kind: FactKind) -> Fraction | None:
    """Extract the exact value carried by a valued predicate.

    Angles come back in units of pi (Newclid's `angle` field is already a Fraction of a
    half-turn), which is GeoForge's normative convention — see types.py.
    """
    if kind is FactKind.CONSTANT_ANGLE:
        return Fraction(predicate.angle)
    for attr in ("length", "ratio", "value"):
        raw = getattr(predicate, attr, None)
        if isinstance(raw, Fraction):
            return raw
        if isinstance(raw, int):
            return Fraction(raw)
    return None


def _justification_from(just: Any) -> Justification:
    kind = _JUSTIFICATION_KINDS[str(just.dependency_type.value)]
    rule = getattr(just, "rule", None)
    return Justification(
        kind=kind,
        rule_id=str(getattr(rule, "id", None)) if rule is not None else None,
        rule_name=str(getattr(rule, "description", None)) if rule is not None else None,
        ar_reason=(str(just.ar_reason.value) if kind is JustificationKind.AR_DEDUCTION else None),
    )


def _dag_from_proof_data(pd: ProofData) -> ProofDAG:
    """Convert Newclid's ProofData into our DAG, re-keying by content-derived FactIds.

    Newclid's ProofIds ('C0', 'N1', '7') are per-run positional labels. We key on the fact's
    own canonical identity instead, so DAGs remain comparable across runs and across engines.
    """
    id_map: dict[ProofId, FactId] = {}
    facts: dict[FactId, Fact] = {}

    def _register(pip: Any) -> FactId:
        fact = _fact_from_predicate(pip.predicate)
        fid = fact.fact_id
        facts[fid] = fact
        id_map[pip.id] = fid
        return fid

    assumptions = tuple(_register(p) for p in pd.construction_assumptions)
    numerical = tuple(_register(p) for p in pd.numerical_checks)
    trivial = tuple(_register(p) for p in pd.trivial_predicates)
    for step in pd.proof_steps:
        _register(step.proven_predicate)
    proved_goals = tuple(id_map[g.id] for g in pd.proven_goals)

    steps = tuple(
        ProofStep(
            conclusion=id_map[step.proven_predicate.id],
            premises=tuple(id_map[p] for p in step.applied_on_predicates if p in id_map),
            justification=_justification_from(step.justification),
        )
        for step in pd.proof_steps
    )

    return ProofDAG(
        facts=tuple(sorted(facts.values())),
        steps=steps,
        assumptions=assumptions,
        numerical_checks=numerical,
        trivial=trivial,
        proved_goals=proved_goals,
        unproved_goals=tuple(sorted(str(g) for g in pd.unproven_goals)),
    )


class NewclidBackend:
    """Implements the SolverBackend protocol over Newclid + Yuclid."""

    name = ENGINE_NAME

    def realize(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> RealizedFigure:
        """Instantiate the construction's coordinates without running deduction.

        Stage 3 uses this to reject degenerate figures before paying for a closure. A
        construction the engine cannot realize (contradictory or over-constrained clauses)
        returns an error rather than raising: that is expected attrition, and the generator
        logs it with the seed.
        """
        opts = opts or SolveOptions()
        rng = np.random.default_rng(opts.seed)
        try:
            setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(spec.to_jgex()).build()
        except Exception as exc:
            return RealizedFigure(points=(), error=f"{type(exc).__name__}: {exc}")
        return RealizedFigure(
            points=tuple(
                sorted((str(p.name), float(p.num.x), float(p.num.y)) for p in setup.points)
            ),
            declared=tuple(
                sorted(
                    fact
                    for fact in (_fact_from_construction(a) for a in setup.assumptions)
                    if fact is not None
                )
            ),
        )

    def solve(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> SolveResult:
        """Run the engine on `spec`.

        Two modes, both used by the pipeline (docs/04):

        * **Goal mode** (`spec.goals` non-empty) — the engine proves the stated goals and we
          return the traced sub-DAG. This is what Stage 6 tracebacks and the translator need.
        * **Saturation mode** (`spec.goals` empty) — the run never short-circuits, so the
          closure is computed to fixpoint and every derived fact is returned. `proof_dag.steps`
          is empty here: Newclid traces a proof only relative to a goal. Stage 4 saturates,
          Stage 5 picks goals, then re-solves in goal mode to get the trace.
        """
        opts = opts or SolveOptions()
        backend = opts.backend or SOLVER.backend
        rng = np.random.default_rng(opts.seed)

        started = time.perf_counter()
        setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(spec.to_jgex()).build()

        builder = (
            GeometricSolverBuilder(rng=rng, api_default=PythonDefault())
            if backend == "python"
            else GeometricSolverBuilder(rng=rng)
        )
        solver = builder.build(setup)
        solved = bool(solver.run())
        wall = time.perf_counter() - started

        saturating = not spec.goals
        goal_constructions = [predicate_to_construction(g) for g in solver.proof_state.goals]
        proof_data = proof_data_from_state(
            goals_constructions=goal_constructions, proof_state=solver.proof_state
        )
        dag = _dag_from_proof_data(proof_data)

        if saturating:
            # Read the whole closure, not just what a goal traced back through.
            closure = {
                fact.fact_id: fact
                for fact in (_fact_from_predicate(p) for p in solver.proof_state.graph.hyper_graph)
            }
            for fact in dag.facts:
                closure.setdefault(fact.fact_id, fact)
            facts = tuple(sorted(closure.values()))
        else:
            facts = dag.facts

        numeric_model = tuple(
            sorted((str(p.name), float(p.num.x), float(p.num.y)) for p in setup.points)
        )
        # Resource caps must surface in stats, never masquerade as an unsolvable problem
        # (docs/08 §8.1 no-silent-failure). The generator discards capped runs and logs the
        # seed rather than treating them as a mathematical result.
        wall_budget = opts.max_wall_seconds or SOLVER.max_wall_seconds
        hit_cap = wall > wall_budget or len(facts) >= SOLVER.max_facts

        stats = SolveStats(
            engine=ENGINE_NAME,
            engine_version=_engine_version(),
            steps=int(solver.run_infos.steps) if solver.run_infos is not None else 0,
            n_facts=len(facts),
            saturated=saturating,
            hit_cap=hit_cap,
            wall_seconds=wall,
        )
        return SolveResult(
            spec=spec,
            facts=facts,
            proof_dag=dag,
            numeric_model=numeric_model,
            stats=stats,
            solved=solved,
        )
