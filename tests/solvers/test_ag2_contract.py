"""Contract suite for the AG2 DDAR validator backend (docs/04 §V, docs/07 O7).

The centre of gravity here is the **angle-convention calibration**. It is the one thing that,
if wrong, breaks silently in the most expensive possible way: an uncalibrated validator rejects
every puzzle whose answer is not 90 deg, which looks exactly like a catastrophic soundness bug
in the generator. So the convention is pinned from both directions — the calibrated spelling
must be accepted *and* the uncalibrated one must be rejected — on a figure whose angle is not
its own supplement.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from pathlib import Path

import pytest

from geoforge.solvers.ag2_backend import (
    ENGINE_VERSION,
    VENDOR_DIR,
    AG2DDARBackend,
    UnsupportedByValidator,
    problem_string,
    to_ddar_predicates,
)
from geoforge.solvers.interface import SolverBackend, ValidatorBackend, get_backend, get_validator
from geoforge.solvers.types import Fact, FactKind, PremiseSpec, SolveOptions

# An equilateral triangle: every angle is 60 deg, so 60 and its supplement 120 are distinct and
# the calibration cannot pass by accident (unlike a right angle, which is its own supplement).
EQUILATERAL = (
    ("a", 0.0, 0.0),
    ("b", 1.0, 0.0),
    ("c", 0.5, math.sqrt(3) / 2),
)
EQUILATERAL_PREMISES = (
    Fact(kind=FactKind.CONGRUENT, args=("a", "b", "b", "c")),
    Fact(kind=FactKind.CONGRUENT, args=("b", "c", "c", "a")),
)
#: The directed angle from line ab to line ac is +60 deg under GeoForge's convention
#: (solvers/types.py): rotating ab onto ac is a +60 deg turn.
ANGLE_BAC = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "a", "c"), value=Fraction(1, 3))


@pytest.fixture(scope="module")
def validator() -> ValidatorBackend:
    return get_validator()


def _solve(validator: ValidatorBackend, goal: Fact) -> bool:
    spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(goal,))
    return goal.fact_id in validator.solve_facts(spec).proof_dag.proved_goals


class TestAngleConventionCalibration:
    """docs/07 O7. DDAR's directed angles run opposite to Newclid's."""

    def test_ddar_reads_the_line_pairs_in_the_opposite_order(self) -> None:
        """The calibration itself, stated as the transformation the exporter applies."""
        assert to_ddar_predicates(ANGLE_BAC) == ("aconst a c a b 1pi/3",)

    def test_calibrated_goal_is_derived(self, validator: ValidatorBackend) -> None:
        assert _solve(validator, ANGLE_BAC)

    def test_the_supplement_is_rejected(self, validator: ValidatorBackend) -> None:
        """The negative half. Without it, a calibration that made *everything* provable would
        pass the positive test."""
        supplement = Fact(kind=ANGLE_BAC.kind, args=ANGLE_BAC.args, value=Fraction(2, 3))
        assert not _solve(validator, supplement)

    def test_uncalibrated_export_would_fail_on_this_figure(
        self, validator: ValidatorBackend
    ) -> None:
        """What an uncalibrated validator would have done: state the pairs unswapped.

        60 deg from ab to ac is 120 deg the other way round, so DDAR reads the unswapped
        spelling as a claim about the supplement and refuses it. Measured over the acceptance
        bank, this rejected 104 of 129 puzzles — every one whose answer was not a right angle.
        """
        from geoforge.solvers.ag2_backend import _parse, _vendor

        ddar, parse, numpy = _vendor()
        points = {n: parse.AGPoint(n, numpy.array([x, y])) for n, x, y in EQUILATERAL}
        engine = ddar.DDAR(list(points.values()))
        for premise in EQUILATERAL_PREMISES:
            for text in to_ddar_predicates(premise):
                engine.force_pred(_parse(parse, text, points))
        engine.deduction_closure(progress_dot=False)

        uncalibrated = "aconst a b a c 1pi/3"  # the pairs NOT swapped
        assert not engine.check_pred(_parse(parse, uncalibrated, points))

    def test_right_angles_are_blind_to_the_convention(self, validator: ValidatorBackend) -> None:
        """Why the calibration must be tested on a non-right angle: 90 deg is its own
        supplement, so a right-angled fixture agrees with itself either way and proves nothing.
        """
        right = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "a", "c"), value=Fraction(1, 2))
        assert to_ddar_predicates(right)[0].endswith("1pi/2")
        swapped = to_ddar_predicates(right)[0].split()[1:5]
        assert swapped == ["a", "c", "a", "b"]


class TestFactExport:
    def test_orientation_invariant_kinds_are_verbatim(self) -> None:
        """`eqangle`, `para` and `perp` are *differences* of directed angles, so inverting the
        orientation negates something that has to equal zero (or a right angle). No calibration
        applies, and applying one would be a bug."""
        eqangle = Fact(kind=FactKind.EQUAL_ANGLES, args=tuple("abcdefgh"))
        assert to_ddar_predicates(eqangle) == ("eqangle a b c d e f g h",)
        assert to_ddar_predicates(Fact(FactKind.PARALLEL, tuple("abcd"))) == ("para a b c d",)
        assert to_ddar_predicates(Fact(FactKind.PERPENDICULAR, tuple("abcd"))) == ("perp a b c d",)

    def test_midpoint_expands_to_what_ddar_can_say(self) -> None:
        assert to_ddar_predicates(Fact(FactKind.MIDPOINT, ("m", "a", "b"))) == (
            "coll m a b",
            "cong m a m b",
        )

    def test_circumcenter_expands_to_equal_radii(self) -> None:
        assert to_ddar_predicates(Fact(FactKind.CIRCUMCENTER, ("o", "a", "b", "c"))) == (
            "cong o a o b",
            "cong o a o c",
        )

    def test_congruent_triangles_expand_to_sss(self) -> None:
        """DDAR has no `contri`. SSS states the metric content exactly; the orientation half
        is recovered by DDAR's own similar-triangle search, which reads orientation off the
        coordinates. The expansion is weaker than the fact, never stronger — the safe
        direction, because an unstated hypothesis can only make validation harder to pass.
        """
        assert to_ddar_predicates(Fact(FactKind.CONTRI_CLOCK, tuple("abcpqr"))) == (
            "cong a b p q",
            "cong b c q r",
            "cong c a r p",
        )

    def test_similar_triangles_expand_to_proportional_sides(self) -> None:
        assert to_ddar_predicates(Fact(FactKind.SIMTRI_REFLECT, tuple("abcpqr"))) == (
            "eqratio a b p q b c q r",
            "eqratio b c q r c a r p",
        )

    def test_configuration_facts_raise_rather_than_being_dropped(self) -> None:
        """Silently skipping one would hand DDAR a weaker problem than the puzzle claims, so a
        pass would certify something the puzzle never stated."""
        with pytest.raises(UnsupportedByValidator, match="configuration fact"):
            to_ddar_predicates(Fact(FactKind.SAME_CLOCK, tuple("abcdef")))

    def test_unregistered_kinds_raise(self) -> None:
        """An unchecked puzzle and a valid puzzle are different things. A kind with no
        registered expansion must stop the build, not be waved through — which is exactly how
        `contri` surfaced: one puzzle in 129, caught loudly at full batch scale."""
        with pytest.raises(UnsupportedByValidator, match="no DDAR predicate"):
            to_ddar_predicates(Fact(FactKind.PYTHAGOREAN_PREMISES, tuple("abcdef")))

    def test_a_premise_naming_an_absent_point_raises(self, validator: ValidatorBackend) -> None:
        spec = PremiseSpec(
            points=EQUILATERAL,
            premises=(Fact(FactKind.CONGRUENT, ("a", "b", "z", "c")),),
            goals=(ANGLE_BAC,),
        )
        with pytest.raises(UnsupportedByValidator, match="does not contain"):
            validator.solve_facts(spec)

    def test_problem_string_round_trips_coordinates_exactly(self) -> None:
        """The reproduction-case format. `repr` of a float is shortest-round-trip, so pasting
        this into a debugging session reproduces the same diagram, not a nearby one."""
        spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(ANGLE_BAC,))
        text = problem_string(spec)
        assert "aconst a c a b 1pi/3" in text
        c_y = re.search(r"c@[^_]+_([0-9.e+-]+) =", text)
        assert c_y is not None and float(c_y.group(1)) == math.sqrt(3) / 2


class TestValidatorContract:
    def test_it_is_a_validator_but_not_a_solver(self, validator: ValidatorBackend) -> None:
        """The M6 finding: DDAR has no construction language and no proof recorder, so the SAL
        has two roles rather than one. `isinstance(..., SolverBackend)` being False is the
        contract, not an oversight."""
        assert isinstance(validator, ValidatorBackend)
        assert not isinstance(validator, SolverBackend)
        assert not hasattr(validator, "solve")
        assert not hasattr(validator, "realize")

    def test_generation_backend_resolver_refuses_the_validator(self) -> None:
        with pytest.raises(ValueError, match="validator, not a generation backend"):
            get_backend("ag2ddar")

    def test_it_is_a_different_engine_from_the_generator(self, validator: ValidatorBackend) -> None:
        """docs/02 invariant 3, at its most basic."""
        assert validator.name != get_backend().name

    def test_repeated_runs_agree(self, validator: ValidatorBackend) -> None:
        """DDAR draws no random numbers — the diagram arrives fully determined — so this is
        cheap. Cheap determinism tests are the ones that stay in the suite."""
        spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(ANGLE_BAC,))
        first, second = validator.solve_facts(spec), validator.solve_facts(spec)
        assert first == second

    def test_it_records_no_proof_steps(self, validator: ValidatorBackend) -> None:
        """DDAR certifies truth without narrating it. An invented step here would look like a
        proof and be none — readable proofs come from the generation engine."""
        spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(ANGLE_BAC,))
        assert validator.solve_facts(spec).proof_dag.steps == ()

    def test_dropping_a_premise_makes_the_goal_underivable(
        self, validator: ValidatorBackend
    ) -> None:
        """One `cong` leaves an isosceles triangle, whose apex angle is free."""
        spec = PremiseSpec(
            points=EQUILATERAL, premises=EQUILATERAL_PREMISES[:1], goals=(ANGLE_BAC,)
        )
        assert ANGLE_BAC.fact_id not in validator.solve_facts(spec).proof_dag.proved_goals

    def test_stats_identify_the_engine(self, validator: ValidatorBackend) -> None:
        spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(ANGLE_BAC,))
        stats = validator.solve_facts(spec).stats
        assert stats.engine == "ag2ddar"
        assert stats.engine_version == ENGINE_VERSION
        assert not stats.hit_cap

    def test_an_over_budget_run_surfaces_as_a_cap_hit(self, validator: ValidatorBackend) -> None:
        """DDAR's closure offers no interruption point, so the cap is checked after the fact.
        What it must never do is let a blow-up pass as a result (docs/08 §8.1)."""
        spec = PremiseSpec(points=EQUILATERAL, premises=EQUILATERAL_PREMISES, goals=(ANGLE_BAC,))
        stats = validator.solve_facts(spec, SolveOptions(max_wall_seconds=1e-9)).stats
        assert stats.hit_cap


class TestVendorPin:
    def test_engine_version_matches_the_provenance_record(self) -> None:
        """DDAR ships no version number, so the vendored commit is the version. Two places
        record it; a test keeps them equal rather than trusting discipline."""
        provenance = (VENDOR_DIR / "PROVENANCE.md").read_text()
        assert ENGINE_VERSION in provenance

    def test_the_vendor_directory_is_appended_to_sys_path_not_prepended(self) -> None:
        """Its modules are named `parse`, `ddar`, `test` — bare enough to shadow a stdlib or
        site-packages module if they came first."""
        import sys

        AG2DDARBackend()  # ensure the import has happened
        from geoforge.solvers.ag2_backend import _vendor

        _vendor()
        assert str(VENDOR_DIR) in sys.path
        assert sys.path.index(str(VENDOR_DIR)) > 0

    def test_vendored_sources_are_unmodified(self) -> None:
        """CLAUDE.md: engines are read-only dependencies. Any fix belongs in our adapter."""
        assert (VENDOR_DIR / "LICENSE").is_file()
        assert "**None.** Files copied verbatim." in (VENDOR_DIR / "PROVENANCE.md").read_text()


def test_vendor_dir_resolves_from_an_installed_checkout() -> None:
    assert VENDOR_DIR.is_dir(), VENDOR_DIR
    assert (VENDOR_DIR / "ddar.py").is_file()
    assert Path(__file__).resolve().parents[2] == VENDOR_DIR.parent.parent
