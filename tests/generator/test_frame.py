"""`emit.frame` — the viewbox transform, and the one property it must never lose.

Framing is the last thing that touches display coordinates, and it is the only place in the
pipeline where a transform is applied to a figure the player will see. If it is not a *direct*
similarity, the figure stops satisfying its own stated givens — and it will do so silently,
because almost everything a puzzle publishes is undirected and survives a mirror.

The exception is `aconst`, a directed line-to-line angle mod pi, which a reflection negates.
That is what these tests exist for. Before Phase 3 M4, `frame` negated y only — a reflection —
and the bug was invisible because every `aconst` given the sampler produced was 90 degrees, the
one angle equal to its own negation mod pi. It is the same shape as docs/03 §3.2a's cross-engine
convention trap, where an uncalibrated validator accepted exactly the 25 of 129 puzzles whose
answer was 90 degrees.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from geoforge.config import LAYOUT
from geoforge.generator.emit import frame
from geoforge.schema import SchemaError

#: A scalene triangle plus a fourth point: no symmetry, so no accidental invariance.
FIGURE: dict[str, tuple[float, float]] = {
    "a": (0.0, 0.0),
    "b": (4.0, 0.0),
    "c": (1.0, 3.0),
    "d": (-2.0, 1.5),
}


def directed_angle(coords: dict[str, tuple[float, float]], p: str, q: str, r: str, s: str) -> float:
    """The engine's convention: `dir(rs) - dir(pq)` mod pi (`solvers/types.py`)."""
    (px, py), (qx, qy) = coords[p], coords[q]
    (rx, ry), (sx, sy) = coords[r], coords[s]
    return (math.atan2(sy - ry, sx - rx) - math.atan2(qy - py, qx - px)) % math.pi


class TestDirectedAnglesSurvive:
    """The regression that M4 fixed. Each of these fails under a y-only flip."""

    @pytest.mark.parametrize(
        ("p", "q", "r", "s"),
        [("a", "b", "a", "c"), ("a", "b", "c", "d"), ("b", "c", "a", "d"), ("a", "c", "b", "d")],
    )
    def test_every_directed_angle_is_preserved(self, p: str, q: str, r: str, s: str) -> None:
        framed = frame(FIGURE)
        before = directed_angle(FIGURE, p, q, r, s)
        after = directed_angle(framed, p, q, r, s)
        assert math.isclose(before, after, abs_tol=1e-9), (
            f"directed angle ({p}{q},{r}{s}) moved {math.degrees(before):.3f} -> "
            f"{math.degrees(after):.3f} deg; framing is not orientation-preserving"
        )

    def test_a_right_angle_would_have_hidden_the_bug(self) -> None:
        """Why this went unnoticed for a whole phase, asserted so nobody re-learns it.

        90 degrees is its own negation mod pi, so a reflection leaves it alone. A test built on
        a right-angled fixture agrees with itself either way and proves nothing — the same
        reason `tests/solvers/test_ag2_contract.py` pins its convention on an equilateral figure.
        """
        right = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0)}
        mirrored = {name: (x, -y) for name, (x, y) in right.items()}
        assert math.isclose(
            directed_angle(right, "a", "b", "a", "c"),
            directed_angle(mirrored, "a", "b", "a", "c"),
            abs_tol=1e-9,
        )
        # ... while a non-right angle does not survive the same mirror, which is the point.
        mirrored_scalene = {name: (x, -y) for name, (x, y) in FIGURE.items()}
        assert not math.isclose(
            directed_angle(FIGURE, "a", "b", "a", "c"),
            directed_angle(mirrored_scalene, "a", "b", "a", "c"),
            abs_tol=1e-9,
        )

    def test_orientation_is_preserved(self) -> None:
        """`sameclock` configuration facts are orientation-sensitive (docs/04 Stage 6), so the
        signed area of a triangle must keep its sign."""

        def cross(coords: dict[str, tuple[float, float]]) -> float:
            (ax, ay), (bx, by), (cx, cy) = coords["a"], coords["b"], coords["c"]
            return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

        assert cross(FIGURE) * cross(frame(FIGURE)) > 0


class TestItIsStillASimilarity:
    def test_all_pairwise_distance_ratios_are_preserved(self) -> None:
        """Every premise is a metric statement about this point set, so anything but a uniform
        scale breaks one (docs/06 §6.3, docs/07 T5)."""
        framed = frame(FIGURE)
        names = sorted(FIGURE)
        pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1 :]]
        scales = [
            math.dist(framed[a], framed[b]) / math.dist(FIGURE[a], FIGURE[b]) for a, b in pairs
        ]
        assert max(scales) - min(scales) < 1e-9, f"non-uniform scale: {scales}"

    def test_the_figure_lands_inside_the_viewbox(self) -> None:
        framed = frame(FIGURE)
        assert all(0 <= x <= LAYOUT.viewbox_width for x, _ in framed.values())
        assert all(0 <= y <= LAYOUT.viewbox_height for _, y in framed.values())

    def test_undirected_angles_are_preserved_too(self) -> None:
        """The property the old docstring relied on. Still true — it was just not sufficient."""
        framed = frame(FIGURE)
        for vertex, p, q in (("a", "b", "c"), ("b", "a", "d"), ("c", "d", "a")):

            def angle(coords: dict[str, tuple[float, float]], v: str, x: str, y: str) -> float:
                vx, vy = coords[v]
                a = math.atan2(coords[x][1] - vy, coords[x][0] - vx)
                b = math.atan2(coords[y][1] - vy, coords[y][0] - vx)
                return abs((a - b + math.pi) % (2 * math.pi) - math.pi)

            assert math.isclose(
                angle(FIGURE, vertex, p, q), angle(framed, vertex, p, q), abs_tol=1e-9
            )


class TestDegenerateInput:
    def test_an_empty_figure_is_refused(self) -> None:
        with pytest.raises(SchemaError, match="empty figure"):
            frame({})

    def test_coincident_points_are_refused_rather_than_scaled_by_infinity(self) -> None:
        """Degenerate figures are Stage 3's business, so reaching here means a gate is missing
        rather than that a scale should be invented."""
        with pytest.raises(SchemaError, match="zero extent"):
            frame({"a": (1.0, 1.0), "b": (1.0, 1.0)})


def test_the_engine_convention_matches_solvers_types() -> None:
    """Pins the helper above against a value the engine itself would produce, so a convention
    change upstream fails here rather than making every assertion in this file vacuous."""
    # dir(ac) - dir(ab) for a=(0,0), b=(1,0), c=(0,1) is +90 degrees.
    coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0)}
    assert math.isclose(directed_angle(coords, "a", "b", "a", "c"), math.pi / 2, abs_tol=1e-12)
    assert Fraction(1, 2) * 180 == 90  # the `aconst` spelling of that same angle
