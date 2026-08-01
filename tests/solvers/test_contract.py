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
    SolveOptions,
)
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.newclid_backend import UnsupportedFactKind, _fact_from_predicate
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


class TestPatches:
    def test_upstream_patches_applied_on_import(self) -> None:
        """The pure-Python AR path is broken upstream without this (BUG-1)."""
        from geoforge.solvers import APPLIED_PATCHES

        assert "BUG-1:enumerate_lconsts-dict-items" in APPLIED_PATCHES

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
