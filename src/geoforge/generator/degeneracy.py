"""Stage 3: cheap numeric pre-checks, run before the engine's closure (docs/04).

Rejecting a degenerate figure here costs microseconds; discovering it after a full deduction
costs milliseconds to seconds. Throughput comes from cheap early rejection, not from making
every sample succeed.

These checks *verify*, they never *derive* (docs/02 invariant 4): a rejection discards a
candidate, it never asserts a geometric fact.

**Rescoped in Phase 3 M6 (docs/07 T23).** This module used to reject the *whole figure* if any
one of its C(n,3) point triples was near-flat. That is combinatorial in the point count, so the
rejection probability climbed with figure richness and the check was structurally biased against
exactly the figures the product needs. Measured against ground truth — human competition figures,
which are correct by definition — it rejected **52% of JGEX** and **85% of IMO** configurations,
and on our own hybrid output it discarded 14 of the 20 constructions that produced a goal.

The fix is scope, not threshold. Two questions were conflated:

* *Is this figure broken?* — coincident points, nothing to draw, the engine could not build it.
  Whole-figure, cheap, and still rejected here.
* *Is this particular triple too flat to be trusted?* — a property of a triple, which only
  matters for the triples something downstream actually **uses**. A near-collinear triple in a
  far corner of the figure harms nothing: the proof is symbolic, and numerics only ever verify
  (docs/02 invariant 4), so the exposure is to the *numeric* checks — the goal's own angle, and
  the configuration facts the derivation records.

So `check_figure` keeps the whole-figure invariants and `degenerate_triples` reports the rest as
data. Stage 5 refuses a goal built on a flat triple; that is where the goal is finally known,
which is why the test could not simply be scoped in place.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from enum import StrEnum

from geoforge.config import DEGENERACY
from geoforge.solvers.types import RealizedFigure


class DegeneracyReason(StrEnum):
    """Why a figure was rejected. Logged per discard for the attrition report."""

    UNREALIZABLE = "unrealizable"
    """The engine could not instantiate the construction at all."""
    TOO_FEW_POINTS = "too_few_points"
    COINCIDENT_POINTS = "coincident_points"
    DEGENERATE_TRIANGLE = "degenerate_triangle"
    """Three points nearly collinear: the figure collapses and side conditions get fragile."""
    FLAT_ANGLE = "flat_angle"
    """An angle within epsilon of 0 or 180 degrees."""


@dataclass(frozen=True, slots=True)
class DegeneracyVerdict:
    ok: bool
    reason: DegeneracyReason | None = None
    detail: str = ""

    @staticmethod
    def passed() -> DegeneracyVerdict:
        return DegeneracyVerdict(ok=True)

    @staticmethod
    def rejected(reason: DegeneracyReason, detail: str = "") -> DegeneracyVerdict:
        return DegeneracyVerdict(ok=False, reason=reason, detail=detail)


def _scale(points: list[tuple[float, float]]) -> float:
    """Figure diameter, used to make the thresholds scale-invariant.

    Without this, a figure drawn small would fail every absolute threshold and one drawn
    large would pass them all — the checks would measure the engine's arbitrary scale rather
    than the geometry.
    """
    diameter = max(
        (math.dist(a, b) for a, b in itertools.combinations(points, 2)),
        default=0.0,
    )
    return diameter or 1.0


def _triangle_area(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


def check_figure(figure: RealizedFigure) -> DegeneracyVerdict:
    """Apply the Stage-3 pre-checks to a realized figure."""
    if not figure.ok:
        return DegeneracyVerdict.rejected(
            DegeneracyReason.UNREALIZABLE, figure.error or "no points"
        )

    names = [name for name, _, _ in figure.points]
    coords = [(x, y) for _, x, y in figure.points]
    if len(coords) < 3:
        return DegeneracyVerdict.rejected(DegeneracyReason.TOO_FEW_POINTS, f"{len(coords)} points")

    scale = _scale(coords)

    for (i, a), (j, b) in itertools.combinations(enumerate(coords), 2):
        if math.dist(a, b) / scale < DEGENERACY.min_point_separation:
            return DegeneracyVerdict.rejected(
                DegeneracyReason.COINCIDENT_POINTS, f"{names[i]}~{names[j]}"
            )

    return DegeneracyVerdict.passed()


def degenerate_triples(figure: RealizedFigure) -> frozenset[frozenset[str]]:
    """Point triples too flat to carry a trustworthy numeric check (docs/04 Stage 3).

    Reported rather than rejected on. A triple is flat if its area is below the scale-relative
    floor or if any of its angles is within `DEGENERACY.min_angle_degrees` of 0 or 180 — the same
    two tests this module has always applied, now returned as data so the caller can ask about
    the triples it actually depends on.

    Only *accidental* near-collinearity counts. Constructions like `on_line`, `midpoint` and
    `foot` declare collinearity on purpose, and a figure containing them is perfectly good — so
    declared triples are exempt, exactly as before.

    Cost is unchanged at O(n^3) but the result is computed once per figure and reused, where the
    old whole-figure test also paid O(n^3) and then threw the information away with the figure.
    """
    if not figure.ok or len(figure.points) < 3:
        return frozenset()

    names = [name for name, _, _ in figure.points]
    coords = [(x, y) for _, x, y in figure.points]
    scale = _scale(coords)
    declared_collinear = figure.declared_collinear()
    area_floor = DEGENERACY.min_triangle_area * scale * scale
    min_angle_rad = math.radians(DEGENERACY.min_angle_degrees)

    flat: set[frozenset[str]] = set()
    for (i, a), (j, b), (k, c) in itertools.combinations(enumerate(coords), 3):
        triple = frozenset((names[i], names[j], names[k]))
        if triple in declared_collinear:
            continue
        if _triangle_area(a, b, c) < area_floor:
            flat.add(triple)
            continue
        for vertex, u, v in ((j, a, c), (i, b, c), (k, a, b)):
            angle = _angle_at(coords[vertex], u, v)
            if angle < min_angle_rad or angle > math.pi - min_angle_rad:
                flat.add(triple)
                break
    return frozenset(flat)


def _angle_at(apex: tuple[float, float], u: tuple[float, float], v: tuple[float, float]) -> float:
    """Undirected angle at `apex` between rays to `u` and `v`, in radians."""
    ux, uy = u[0] - apex[0], u[1] - apex[1]
    vx, vy = v[0] - apex[0], v[1] - apex[1]
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu == 0.0 or nv == 0.0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / (nu * nv)))
    return math.acos(cosine)
