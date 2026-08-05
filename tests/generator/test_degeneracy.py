"""Stage 3 degeneracy pre-checks (docs/04).

**Rewritten in Phase 3 M6 (docs/07 T23).** Three tests here used to assert that a whole figure
is rejected because one of its triples is flat. That behaviour was the defect: rejection
probability grows with C(n,3), so the check refused 52% of JGEX and 85% of IMO competition
figures — figures correct by definition. They now assert the split: `check_figure` answers "is
this figure broken", `degenerate_triples` answers "which triples cannot carry a numeric check",
and the second is acted on where the goal is known (Stage 5).

The flat-triple *tests* themselves are unchanged in substance — same thresholds, same exemption
for declared collinearity. Only the question they are asked of moved.
"""

from __future__ import annotations

from geoforge.generator.degeneracy import DegeneracyReason, check_figure, degenerate_triples
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

    def test_accidental_collinearity_is_reported_not_rejected(self) -> None:
        """Three points nearly collinear that nothing declared collinear.

        The figure passes — a flat triple is not a broken figure — and the triple is named, so
        Stage 5 can refuse a goal that is *about* it. This is the M6 inversion in one test.
        """
        points = (("a", 0.0, 0.0), ("b", 1.0, 0.0), ("c", 2.0, 1e-9))
        figure = RealizedFigure(points=points)
        assert check_figure(figure).ok
        assert degenerate_triples(figure) == frozenset({frozenset({"a", "b", "c"})})

    def test_a_flat_corner_no_longer_condemns_the_rest_of_the_figure(self) -> None:
        """The behaviour the rescope exists for, at the smallest scale that shows it.

        One flat triple sits in a corner; a healthy triangle sits elsewhere. The old check threw
        away the whole figure, and with it the perfectly good question about the healthy part.
        """
        points = (
            ("a", 0.0, 0.0),
            ("b", 1.0, 0.0),
            ("c", 0.4, 0.9),
            ("x", 5.0, 5.0),
            ("y", 6.0, 5.0),
            ("z", 7.0, 5.0 + 1e-9),
        )
        figure = RealizedFigure(points=points)
        assert check_figure(figure).ok
        flat = degenerate_triples(figure)
        assert frozenset({"x", "y", "z"}) in flat
        assert frozenset({"a", "b", "c"}) not in flat


class TestDeclaredCollinearityIsExempt:
    """The check that a naive implementation gets wrong.

    on_line, midpoint and foot all create collinear points *on purpose*. Rejecting those
    would throw away most of the sample space; docs/04 Stage 3 rejects only collinearity the
    construction did not declare.
    """

    def test_declared_collinear_triple_is_not_flat(self) -> None:
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("d", 1.0, 0.0), ("c", 0.4, 0.9))
        declared = (Fact(kind=FactKind.COLLINEAR, args=("a", "b", "d")),)
        figure = RealizedFigure(points=points, declared=declared)
        assert check_figure(figure).ok
        assert frozenset({"a", "b", "d"}) not in degenerate_triples(figure)

    def test_same_figure_without_the_declaration_is_flat(self) -> None:
        """The near-miss for the exemption: without the declaration the very same coordinates
        are flagged, so the exemption is doing the work and not the geometry."""
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("d", 1.0, 0.0), ("c", 0.4, 0.9))
        figure = RealizedFigure(points=points)
        assert check_figure(figure).ok
        assert frozenset({"a", "b", "d"}) in degenerate_triples(figure)

    def test_midpoint_declaration_exempts_its_triple(self) -> None:
        points = (("a", 0.0, 0.0), ("b", 2.0, 0.0), ("m", 1.0, 0.0), ("c", 0.4, 0.9))
        declared = (Fact(kind=FactKind.MIDPOINT, args=("m", "a", "b")),)
        figure = RealizedFigure(points=points, declared=declared)
        assert check_figure(figure).ok
        assert frozenset({"a", "b", "m"}) not in degenerate_triples(figure)


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
            assert degenerate_triples(RealizedFigure(points=scaled)) == frozenset(
                {frozenset({"a", "b", "c"})}
            )

    def test_the_number_of_points_does_not_change_a_triples_verdict(self) -> None:
        """The property the old whole-figure check could not have.

        Adding unrelated healthy points used to make rejection *more* likely, because every new
        point adds C(n,2) new triples and any one of them could condemn the figure. Now a
        triple's verdict depends on that triple alone, which is why figure richness stopped
        being self-defeating (docs/07 T23).
        """
        base = [("a", 0.0, 0.0), ("b", 1.0, 0.0), ("c", 0.4, 0.9)]
        extras = [("p", 3.0, 0.5), ("q", 4.2, 2.1), ("r", 5.5, 0.3), ("s", 2.2, 3.4)]
        for count in range(len(extras) + 1):
            figure = RealizedFigure(points=tuple(base + extras[:count]))
            assert check_figure(figure).ok
            assert frozenset({"a", "b", "c"}) not in degenerate_triples(figure)
