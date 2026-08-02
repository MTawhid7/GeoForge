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
from newclid.numerical.geometries import PointNum
from newclid.predicate_types import PredicateArgument
from newclid.problem import (
    PredicateConstruction,
    ProblemSetup,
    predicate_to_construction,
)
from newclid.proof_data import ProofData, ProofId, proof_data_from_state
from newclid.symbols.points_registry import Point

from geoforge.config import SOLVER
from geoforge.solvers.types import (
    VALUED_KINDS,
    Fact,
    FactId,
    FactKind,
    Justification,
    JustificationKind,
    PremiseSpec,
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
    `to_tokens`. Returns None for predicates outside our vocabulary — unlike derived facts, an
    unmapped *declared* assumption is not a soundness risk (it weakens the premise set, so a
    goal verified without it is still true), it only costs yield. `realize` records what it
    dropped so the loss stays visible.

    A valued predicate's value must be lifted out of the argument list here exactly as
    `_fact_from_predicate` does, or the same geometric fact would get two different fact_ids
    depending on whether it arrived as a premise or as a derived fact — and premise
    minimization, which matches premises against DAG leaves, would never find a match.
    """
    try:
        kind = FactKind(str(construction.predicate_type.value))
    except ValueError:
        return None
    args = tuple(str(a) for a in construction.args)
    if kind in VALUED_KINDS and args:
        value = _parse_value_token(args[-1])
        if value is None:
            return None
        return Fact(kind=kind, args=args[:-1], value=value)
    return Fact(kind=kind, args=args)


def _parse_value_token(token: str) -> Fraction | None:
    """Parse a predicate's value token, e.g. '5pi/18' or '3/1'. None if it is not one."""
    try:
        return Fraction(token.replace("pi", ""))
    except (ValueError, ZeroDivisionError):
        return None


#: How each valued kind spells its value as a predicate token. Angles carry an explicit `pi`
#: because the engine's angle atoms are fractions of a half-turn (see types.py).
_VALUE_TOKEN: dict[FactKind, str] = {
    FactKind.CONSTANT_ANGLE: "{n}pi/{d}",
    FactKind.CONSTANT_LENGTH: "{n}/{d}",
    FactKind.SQUARED_CONSTANT_LENGTH: "{n}/{d}",
    FactKind.CONSTANT_RATIO: "{n}/{d}",
    FactKind.SQUARED_CONSTANT_RATIO: "{n}/{d}",
}


def _construction_from_fact(fact: Fact) -> PredicateConstruction:
    """Render one of our Facts back into an engine predicate — the inverse of
    `_fact_from_predicate`.

    The engine canonicalizes on construction, so callers may pass any spelling. Verified in
    M3: canonicalization reorders the points *within* each line of an angle (which leaves a
    line-to-line angle unchanged) and never silently rewrites the value.

    Raises `UnsupportedFactKind` rather than approximating: this feeds premise minimization,
    where quietly dropping a premise would report it as unnecessary when it is not.
    """
    tokens: tuple[str, ...] = (fact.kind.value, *fact.args)
    if fact.value is not None:
        template = _VALUE_TOKEN.get(fact.kind)
        if template is None:
            raise UnsupportedFactKind(
                f"no value spelling registered for valued kind {fact.kind.value!r}"
            )
        tokens += (template.format(n=fact.value.numerator, d=fact.value.denominator),)
    try:
        return PredicateConstruction.from_tuple(tokens)
    except Exception as exc:
        raise UnsupportedFactKind(
            f"Newclid rejected {' '.join(tokens)!r} as a predicate construction: {exc}"
        ) from exc


def _setup_from_premise_spec(spec: PremiseSpec) -> ProblemSetup:
    """Build an engine problem over fixed coordinates and an explicit premise set."""
    return ProblemSetup(
        points=tuple(
            Point(name=PredicateArgument(name), num=PointNum(x=x, y=y))
            for name, x, y in spec.points
        ),
        assumptions=tuple(_construction_from_fact(f) for f in spec.premises),
        goals=tuple(_construction_from_fact(f) for f in spec.goals),
    )


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
        declared = [(a, _fact_from_construction(a)) for a in setup.assumptions]
        return RealizedFigure(
            points=tuple(
                sorted((str(p.name), float(p.num.x), float(p.num.y)) for p in setup.points)
            ),
            # Deduplicated: the engine can state the same assumption twice (two clauses both
            # requiring `ncoll a b c`), and a repeated premise is not a second premise.
            declared=tuple(sorted({fact for _, fact in declared if fact is not None})),
            dropped_assumptions=tuple(sorted(str(a) for a, fact in declared if fact is None)),
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
        rng = np.random.default_rng(opts.seed)
        started = time.perf_counter()
        setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(spec.to_jgex()).build()
        return self._run(setup, spec, saturating=not spec.goals, opts=opts, started=started)

    def solve_facts(self, spec: PremiseSpec, opts: SolveOptions | None = None) -> SolveResult:
        """Solve over fixed coordinates and an explicit premise set (docs/04 Stages 5 and 6).

        Used for goal verification (does the closure of these premises prove this value?) and
        for premise minimization (does it still, with one premise removed?). Both need the
        figure held still while the premise set varies, which the construction-level `solve`
        cannot express.
        """
        opts = opts or SolveOptions()
        started = time.perf_counter()
        setup = _setup_from_premise_spec(spec)
        return self._run(setup, spec, saturating=not spec.goals, opts=opts, started=started)

    def _run(
        self,
        setup: Any,
        spec: ProblemSpec | PremiseSpec,
        *,
        saturating: bool,
        opts: SolveOptions,
        started: float,
    ) -> SolveResult:
        """Shared engine run. Both entry points differ only in how `setup` was obtained."""
        backend = opts.backend or SOLVER.backend
        rng = np.random.default_rng(opts.seed)

        builder = (
            GeometricSolverBuilder(rng=rng, api_default=PythonDefault())
            if backend == "python"
            else GeometricSolverBuilder(rng=rng)
        )
        solver = builder.build(setup)
        solved = bool(solver.run())
        wall = time.perf_counter() - started

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
