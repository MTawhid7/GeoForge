"""Stage 3 degeneracy pre-checks (docs/04)."""

from __future__ import annotations

from geoforge.generator.degeneracy import DegeneracyReason, check_figure
from geoforge.solvers.types import Fact, FactKind, RealizedFigure

TRIANGLE = (("a", 0.0, 0.0), ("b", 1.0, 0.0), ("c", 0.4, 0.9))


class TestBasicRejections:
    def test_healthy_triangle_passes(self) -> None:
        assert check_figure(RealizedFigure(points=TRIANGLE)).ok

    def test_unrealizable_figure_is_reported_not_raised(self) -> None:
        """A construction the engine cannot build is ordinary attrition, not a crash."""
        verdict = check_figure(RealizedFigure(points=(), error="JGEXConstructionError: nope"))
        assert not verdict.ok
        assert verdict.reason is DegeneracyReason.UNREALIZABLE

    def test_too_few_points(self) -> None:
        verdict = check_figure(RealizedFigure(points=TRIANGLE[:2]))
        assert verdict.reason is DegeneracyReason.TOO_FEW_POINTS

    def test_coincident_points_rejected(self) -> None:
        points = (*TRIANGLE, ("d", 1.0 + 1e-9, 0.0))
        verdict = check_figure(RealizedFigure(points=points))
        assert verdict.reason is DegeneracyReason.COINCIDENT_POINTS

    def test_accidental_collinearity_rejected(self) -> None:
        """Three points nearly collinear that nothing declared collinear."""
        points = (("a", 0.0, 0.0), ("b", 1.0, 0.0), ("c", 2.0, 1e-9))
        verdict = check_figure(RealizedFigure(points=points))
        assert verdict.reason in (
            DegeneracyReason.DEGENERATE_TRIANGLE,
            DegeneracyReason.FLAT_ANGLE,
        )


class TestDeclaredCollinearityIsExempt:
    """The check that a naive implementation gets wrong.

    on_line, midpoint and foot all create collinear points *on purpose*. Rejecting those
    would throw away most of the sample space; docs/04 Stage 3 rejects only collinearity the
    construction did not declare.
    """

    def test_declared_collinear_triple_is_allowed(self) -> None:
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("d", 1.0, 0.0), ("c", 0.4, 0.9))
        declared = (Fact(kind=FactKind.COLLINEAR, args=("a", "b", "d")),)
        assert check_figure(RealizedFigure(points=points, declared=declared)).ok

    def test_same_figure_without_the_declaration_is_rejected(self) -> None:
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("d", 1.0, 0.0), ("c", 0.4, 0.9))
        assert not check_figure(RealizedFigure(points=points)).ok

    def test_midpoint_declaration_exempts_its_triple(self) -> None:
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("m", 1.0, 0.0), ("c", 0.4, 0.9))
        declared = (Fact(kind=FactKind.MIDPOINT, args=("m", "a", "b")),)
        assert check_figure(RealizedFigure(points=points, declared=declared)).ok


class TestScaleInvariance:
    """Thresholds are relative to the figure's diameter.

    Otherwise the checks would measure the engine's arbitrary drawing scale rather than the
    geometry: a small figure would fail everything, a large one would pass everything.
    """

    def test_uniform_scaling_does_not_change_the_verdict(self) -> None:
        for factor in (1e-3, 1.0, 1e3):
            scaled = tuple((n, x * factor, y * factor) for n, x, y in TRIANGLE)
            assert check_figure(RealizedFigure(points=scaled)).ok

    def test_degenerate_stays_degenerate_at_every_scale(self) -> None:
        thin = (("a", 0.0, 0.0), ("b", 1.0, 0.0), ("c", 0.5, 1e-9))
        for factor in (1e-3, 1.0, 1e3):
            scaled = tuple((n, x * factor, y * factor) for n, x, y in thin)
            assert not check_figure(RealizedFigure(points=scaled)).ok
