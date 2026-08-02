"""SAL contract suite (docs/08 §8.3).

These tests define what "being a GeoForge solver backend" means. They run against whatever
`get_backend()` returns, so the AG2 adapter (M6) inherits them unchanged — which is the
point: bank validation must run on a different engine than generation, and both must obey
one contract.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from geoforge.solvers import (
    CONFIGURATION_KINDS,
    Fact,
    FactKind,
    JustificationKind,
    ProblemSpec,
    RealizedFigure,
    SolveOptions,
)
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.newclid_backend import (
    UnsupportedFactKind,
    _construction_from_fact,
    _fact_from_predicate,
)
from geoforge.solvers.types import PremiseSpec
from tests.solvers.corpus import CORPUS, SATURATION_CORPUS


class TestDeterminism:
    """docs/02 invariant 2: every artifact reproducible from (version, seed)."""

    def test_same_seed_gives_equal_results(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        first = backend.solve(spec, SolveOptions(seed=42))
        second = backend.solve(spec, SolveOptions(seed=42))
        assert first == second, "same seed must produce an identical SolveResult"

    def test_wall_time_excluded_from_equality(self, backend: SolverBackend) -> None:
        """Timing varies run to run; if it were compared, determinism tests would be flaky
        and would mask real drift."""
        spec = CORPUS["thales_semicircle"]
        first = backend.solve(spec, SolveOptions(seed=42))
        second = backend.solve(spec, SolveOptions(seed=42))
        assert first.stats == second.stats
        # Guard the mechanism itself, not just the outcome.
        assert "wall_seconds" not in {
            f.name for f in first.stats.__dataclass_fields__.values() if f.compare
        }

    def test_different_seeds_give_different_diagrams(self, backend: SolverBackend) -> None:
        """A seed must actually reach the engine's coordinate sampling, otherwise
        well-posedness resampling (Stage 8) would silently test one figure repeatedly."""
        spec = CORPUS["thales_semicircle"]
        a = backend.solve(spec, SolveOptions(seed=1))
        b = backend.solve(spec, SolveOptions(seed=2))
        assert a.numeric_model != b.numeric_model


class TestFactNormalization:
    def test_facts_are_canonical_and_sorted(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        result = backend.solve(spec, SolveOptions(seed=42))
        assert list(result.facts) == sorted(result.facts)
        ids = [f.fact_id for f in result.facts]
        assert len(ids) == len(set(ids)), "fact ids must be unique after canonicalization"

    def test_fact_ids_are_content_derived(self) -> None:
        """Ids must not depend on engine-run position, so DAGs stay comparable across runs
        and across engines."""
        one = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "c", "d"), value=Fraction(1, 2))
        two = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "c", "d"), value=Fraction(1, 2))
        other = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "c", "d"), value=Fraction(1, 3))
        assert one.fact_id == two.fact_id
        assert one.fact_id != other.fact_id

    def test_angle_values_are_exact_in_units_of_pi(self, backend: SolverBackend) -> None:
        result = backend.solve(CORPUS["thales_semicircle"], SolveOptions(seed=42))
        angles = [f for f in result.facts if f.kind is FactKind.CONSTANT_ANGLE]
        assert angles, "the Thales fixture must derive a constant angle"
        right = next(f for f in angles if f.degrees() == 90)
        assert isinstance(right.value, Fraction)
        assert right.value == Fraction(1, 2), "90 degrees is 1/2 of a half-turn"

    def test_unknown_predicate_raises_rather_than_dropping(self) -> None:
        """Silently dropping a fact would corrupt the DAG and could make an unsound puzzle
        look well-formed, so the adapter must fail loudly."""

        class FakeType:
            value = "definitely_not_a_geoforge_fact"

        class FakePredicate:
            predicate_type = FakeType()

            def to_tokens(self) -> tuple[str, ...]:
                return ("a", "b")

        with pytest.raises(UnsupportedFactKind, match="not in the GeoForge fact vocabulary"):
            _fact_from_predicate(FakePredicate())


class TestDagIntegrity:
    def test_every_referenced_fact_exists(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        dag = backend.solve(spec, SolveOptions(seed=42)).proof_dag
        known = set(dag.index())
        for step in dag.steps:
            assert step.conclusion in known
            for premise in step.premises:
                assert premise in known, f"dangling premise {premise} in {step.conclusion}"

    def test_goals_are_derivable_from_assumptions(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        """Walking back from each goal must terminate at assumptions, numerical checks, or
        trivia — never at an unexplained fact."""
        _, spec = corpus_case
        result = backend.solve(spec, SolveOptions(seed=42))
        dag = result.proof_dag
        assert result.solved and dag.proved_goals

        derived = {s.conclusion for s in dag.steps}
        grounded = set(dag.assumptions) | set(dag.numerical_checks) | set(dag.trivial)
        by_conclusion = {s.conclusion: s for s in dag.steps}

        stack = list(dag.proved_goals)
        seen: set[str] = set()
        while stack:
            fid = stack.pop()
            if fid in seen or fid in grounded:
                continue
            seen.add(fid)
            assert fid in derived, f"{fid} is neither grounded nor derived"
            stack.extend(by_conclusion[fid].premises)

    def test_depth_is_positive_for_real_proofs(self, backend: SolverBackend) -> None:
        dag = backend.solve(CORPUS["thales_semicircle"], SolveOptions(seed=42)).proof_dag
        assert dag.depth() >= 2, "a multi-step proof must report a depth"


class TestConfigurationFacts:
    """docs/04 Stage 6: configuration facts are first-class, sourced from numerical checks."""

    def test_numerical_checks_are_configuration_facts(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        dag = backend.solve(spec, SolveOptions(seed=42)).proof_dag
        index = dag.index()
        for fid in dag.numerical_checks:
            assert index[fid].kind in CONFIGURATION_KINDS, (
                f"{fid} came from a numerical check but is not classed as a configuration "
                "fact; premise minimization would strip it and break well-posedness"
            )

    def test_configuration_facts_are_extracted(self, backend: SolverBackend) -> None:
        dag = backend.solve(CORPUS["thales_semicircle"], SolveOptions(seed=42)).proof_dag
        assert dag.configuration_facts(), "expected configuration facts on a circle problem"

    def test_configuration_facts_carry_no_value(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        dag = backend.solve(spec, SolveOptions(seed=42)).proof_dag
        for fact in dag.configuration_facts():
            assert fact.value is None


class TestSaturationMode:
    @pytest.mark.parametrize("name", sorted(SATURATION_CORPUS))
    def test_goal_free_solve_saturates(self, backend: SolverBackend, name: str) -> None:
        """Stage 4: no goals means the run never short-circuits, so the closure is complete."""
        result = backend.solve(SATURATION_CORPUS[name], SolveOptions(seed=42))
        assert result.stats.saturated
        assert len(result.facts) > 10, "saturation should yield a substantial closure"

    def test_saturation_has_no_proof_steps(self, backend: SolverBackend) -> None:
        """Newclid traces a proof only relative to a goal. Documenting this in a test so the
        pipeline's two-pass design (saturate, then re-solve per goal) stays deliberate."""
        result = backend.solve(SATURATION_CORPUS["triangle_circum"], SolveOptions(seed=42))
        assert result.proof_dag.steps == ()


class TestStatsAndCaps:
    def test_caps_surface_in_stats(self, backend: SolverBackend) -> None:
        """A cap must be reported, not disguised as an unsolvable problem (docs/08 §8.1)."""
        spec = CORPUS["circum_right_angle"]
        generous = backend.solve(spec, SolveOptions(seed=42, max_wall_seconds=600.0))
        assert not generous.stats.hit_cap

        impossible = backend.solve(spec, SolveOptions(seed=42, max_wall_seconds=1e-9))
        assert impossible.stats.hit_cap, "an exceeded wall budget must set hit_cap"

    def test_stats_report_engine_identity(self, backend: SolverBackend) -> None:
        """Provenance needs the exact engine version (docs/02 invariant 2)."""
        stats = backend.solve(CORPUS["eq_triangle_60"], SolveOptions(seed=42)).stats
        assert stats.engine == "newclid"
        assert stats.engine_version.count(".") >= 2


class TestBackendResolution:
    def test_default_backend_is_yuclid_per_config(self) -> None:
        from geoforge.config import SOLVER

        assert SOLVER.backend == "yuclid", (
            "Phase 0 measured Yuclid 23-26x faster, and the pure-Python matcher cannot "
            "apply rules containing numeric constants"
        )

    def test_backend_satisfies_protocol(self) -> None:
        assert isinstance(get_backend(), SolverBackend)

    def test_ag2_backend_is_deferred_with_a_reason(self) -> None:
        with pytest.raises(NotImplementedError, match="M6"):
            get_backend("ag2ddar")

    def test_unknown_backend_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown solver backend"):
            get_backend("not-an-engine")


class TestCrossProcessDeterminism:
    """Determinism across *processes*, which same-process comparison cannot test.

    Python randomizes string hashing per process, so anything that leaks `set` or `dict`
    iteration order over strings into a result varies run to run — while two runs inside one
    process agree, because they share that process's hash seed. `TestDeterminism` above is
    therefore blind to an entire class of reproducibility bug, and upstream BUG-4 (`cong`
    canonicalization discarding its own sort) lived in that blind spot.

    docs/02 invariant 2 is a claim about artifacts, not about a process.
    """

    SCRIPT = """
import json, sys
from geoforge.solvers import get_backend, ProblemSpec
from geoforge.solvers.types import SolveOptions
result = get_backend().solve(
    ProblemSpec(
        construction="a b = segment a b; o = midpoint o a b; c = on_circle c o a",
        goals=("aconst a c c b 1pi/2",),
    ),
    SolveOptions(seed=42),
)
print(json.dumps([f.fact_id for f in result.facts]))
"""

    def test_facts_are_identical_under_different_hash_seeds(self) -> None:
        import json
        import os
        import subprocess
        import sys

        outputs = []
        for hash_seed in ("0", "1", "12345"):
            env = {**os.environ, "PYTHONHASHSEED": hash_seed}
            proc = subprocess.run(
                [sys.executable, "-c", self.SCRIPT],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            outputs.append(json.loads(proc.stdout))

        assert outputs[0] == outputs[1] == outputs[2], (
            "fact spellings changed with the hash seed: some engine canonicalization is "
            "leaking set/dict iteration order into results"
        )


class TestFactLevelSolving:
    """`solve_facts`: fixed coordinates, explicit premise set (docs/04 Stages 5 and 6).

    Every backend must support it, not just Newclid — premise minimization cannot be expressed
    through the construction-level interface, and the M6 validator consumes premises and
    coordinates natively anyway.
    """

    def _thales(self, backend: SolverBackend) -> tuple[RealizedFigure, Fact]:
        figure = backend.realize(CORPUS["thales_semicircle"], SolveOptions(seed=42))
        goal = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "c", "c", "b"), value=Fraction(1, 2))
        return figure, goal

    def test_proves_a_goal_from_stated_premises(self, backend: SolverBackend) -> None:
        figure, goal = self._thales(backend)
        result = backend.solve_facts(
            PremiseSpec(points=figure.points, premises=figure.declared, goals=(goal,)),
            SolveOptions(seed=42),
        )
        assert result.solved
        assert result.proof_dag.steps

    def test_unprovable_goal_returns_unsolved(self, backend: SolverBackend) -> None:
        """Regression for upstream BUG-3.

        With no premises the right angle does not follow, however plainly the coordinates show
        it. Newclid signalled this by letting a `ValueError` escape from `proof_data_from_state`
        — so the ordinary negative answer arrived as a crash. It must come back as a result.
        """
        figure, goal = self._thales(backend)
        result = backend.solve_facts(
            PremiseSpec(points=figure.points, premises=(), goals=(goal,)),
            SolveOptions(seed=42),
        )
        assert not result.solved
        assert result.proof_dag.unproved_goals

    def test_is_deterministic(self, backend: SolverBackend) -> None:
        figure, goal = self._thales(backend)
        spec = PremiseSpec(points=figure.points, premises=figure.declared, goals=(goal,))
        first = backend.solve_facts(spec, SolveOptions(seed=42))
        second = backend.solve_facts(spec, SolveOptions(seed=42))
        assert first.facts == second.facts
        assert first.proof_dag == second.proof_dag

    def test_dropping_a_premise_weakens_the_problem(self, backend: SolverBackend) -> None:
        """The property minimization rests on. If premises did not matter — if the engine read
        the answer off the coordinates — every minimization would strip every given."""
        figure, goal = self._thales(backend)
        essential = tuple(f for f in figure.declared if f.kind is not FactKind.MIDPOINT)
        result = backend.solve_facts(
            PremiseSpec(points=figure.points, premises=essential, goals=(goal,)),
            SolveOptions(seed=42),
        )
        assert not result.solved


class TestFactRoundTrip:
    """Facts must survive the trip out to the engine and back (docs/03 §3.3)."""

    def test_valued_premise_keeps_its_value(self, backend: SolverBackend) -> None:
        """A given angle arrives as an argument token and must be lifted into `value`, exactly
        as a derived fact is — otherwise one geometric fact gets two ids depending on where it
        came from, and premise minimization never matches a leaf."""
        figure = backend.realize(
            ProblemSpec(construction="a b = segment a b; c = s_angle a b c 50o"),
            SolveOptions(seed=42),
        )
        angles = [f for f in figure.declared if f.kind is FactKind.CONSTANT_ANGLE]
        assert angles
        assert angles[0].value == Fraction(5, 18)
        assert angles[0].degrees() == 50
        assert "pi" not in angles[0].fact_id.removesuffix(str(angles[0].value))

    def test_unrenderable_fact_raises(self) -> None:
        """Never silently dropped: a premise that vanishes would make minimization report it as
        unnecessary when it is not."""
        bogus = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a",), value=Fraction(1, 2))
        with pytest.raises(UnsupportedFactKind):
            _construction_from_fact(bogus)

    def test_canonicalization_preserves_an_angles_value(self) -> None:
        """The engine reorders the points within each line of an angle. That leaves a
        line-to-line angle unchanged — a line has no direction — and the value must come
        through untouched. If it did not, every proposed goal would be a coin flip between an
        angle and its supplement."""
        fact = Fact(kind=FactKind.CONSTANT_ANGLE, args=("b", "c", "b", "a"), value=Fraction(13, 18))
        rendered = str(_construction_from_fact(fact))
        assert rendered.endswith("13pi/18")


class TestPatches:
    def test_upstream_patches_applied_on_import(self) -> None:
        """The pure-Python AR path is broken upstream without this (BUG-1)."""
        from geoforge.solvers import APPLIED_PATCHES

        assert "BUG-1:enumerate_lconsts-dict-items" in APPLIED_PATCHES

    def test_justify_patch_applied(self) -> None:
        from geoforge.solvers import APPLIED_PATCHES

        assert "BUG-3:justify-raises-justification-error" in APPLIED_PATCHES

    def test_cong_canonicalization_patch_applied(self) -> None:
        from geoforge.solvers import APPLIED_PATCHES

        assert "BUG-4:cong-preparse-stable-order" in APPLIED_PATCHES

    def test_cong_canonical_form_is_sorted(self) -> None:
        """BUG-4 regression, checkable without spawning a process: upstream sorted the segments
        and then dropped the sort through a `set` round-trip, so the canonical form was whatever
        the process's string hashing produced."""
        from newclid.predicates.congruence import Cong

        assert Cong.preparse(("c", "o", "a", "o")) == ("a", "o", "c", "o")
        assert Cong.preparse(("a", "o", "c", "o")) == ("a", "o", "c", "o")

    def test_python_backend_works_on_a_length_problem(self) -> None:
        """Regression for BUG-1: this problem's AR ratio table holds a length constant, which
        raised TypeError on every call before the patch. Phase 0 measured it as one of the
        two problems the patch unlocked on the pure-Python backend.

        Chosen deliberately over a midpoint-based problem: those also trip BUG-2 (the rule
        matcher choking on the constant '1/2'), which is unpatched, so they cannot isolate
        BUG-1 (see `test_python_backend_still_hits_unpatched_matcher_bug`).
        """
        backend = get_backend()
        result = backend.solve(
            CORPUS["circum_right_angle"], SolveOptions(seed=42, backend="python")
        )
        assert result.solved

    def test_python_backend_still_hits_unpatched_matcher_bug(self) -> None:
        """Pins BUG-2, which we deliberately do NOT patch (it is a design-level defect in
        Newclid's pure-Python MappingMatcher, not a one-liner).

        This test documents *why* Yuclid is the primary backend. If it ever starts passing,
        upstream has fixed the matcher and this test plus the note in docs/03 §3.2 should be
        revisited.
        """
        backend = get_backend()
        with pytest.raises(KeyError, match="1/2"):
            backend.solve(CORPUS["thales_semicircle"], SolveOptions(seed=42, backend="python"))

    def test_justification_kinds_are_mapped(
        self, backend: SolverBackend, corpus_case: tuple[str, ProblemSpec]
    ) -> None:
        _, spec = corpus_case
        dag = backend.solve(spec, SolveOptions(seed=42)).proof_dag
        for step in dag.steps:
            assert isinstance(step.justification.kind, JustificationKind)
            if step.justification.kind is JustificationKind.RULE_APPLICATION:
                assert step.justification.rule_id, "rule steps must carry their rule id"
                assert step.justification.rule_name
