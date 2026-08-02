"""Directed line-to-line angles → human vertex angles (docs/03 §3.5 item 2c).

**This is the translator's central job, not an edge case.** Every angle fact an AG-lineage engine
emits is a directed angle between two *lines*, modulo pi — 48 of 48 in the Phase 0 corpus. A human
reads vertex angles: ∠ABC, between two *rays*, in (0°, 180°).

The two differ by more than notation. `∠(BA,BC) = 40°` is consistent with ∠ABC = 40° **and** with
∠ABC = 140°; which one holds depends on the figure's configuration. That is exactly what the
configuration facts of `docs/04` Stage 6 pin down, and why they are premises of the puzzle rather
than incidental detail.

How the choice is made here: the reference diagram is a model of (premises + configuration facts),
so the vertex angle is read off it and checked to be one of the two values the proved directed fact
allows. If it is neither, the conversion is refused rather than guessed. This is a *presentation*
choice resolved by a model, not a derivation — the mathematical content stays the directed fact the
engine proved.

**Depends on M5.** Its soundness rests on every configuration-matching resample agreeing, which is
what the Stage 8 well-posedness gate checks. That gate must therefore check the vertex angles of
*solution steps* too, not only the goal value (`docs/04` Stage 8, amended).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from geoforge.config import EXTRACTION

Coords = Mapping[str, tuple[float, float]]
Line = tuple[str, str]


def label(point: str) -> str:
    """Point name as it appears to a player: engine `a1` becomes `A1` (docs/02)."""
    return point[0].upper() + point[1:]


@dataclass(frozen=True, slots=True, order=True)
class VertexAngle:
    """An angle at a vertex, between the rays to `p` and `q`."""

    p: str
    vertex: str
    q: str
    degrees: Fraction | None = None
    """Exact value when known, in degrees, in (0, 180)."""

    @property
    def text(self) -> str:
        return f"∠{label(self.p)}{label(self.vertex)}{label(self.q)}"

    @property
    def highlight(self) -> str:
        """Normative highlight id (docs/02): `angle:<P>:<VERTEX>:<P>`."""
        return f"angle:{label(self.p)}:{label(self.vertex)}:{label(self.q)}"

    def with_value(self, degrees: Fraction) -> VertexAngle:
        return VertexAngle(p=self.p, vertex=self.vertex, q=self.q, degrees=degrees)


def lines_of(args: tuple[str, ...]) -> tuple[Line, Line] | None:
    """Split a 4-point angle argument tuple into its two lines."""
    if len(args) != 4:
        return None
    return (args[0], args[1]), (args[2], args[3])


def shared_point(first: Line, second: Line) -> str | None:
    """The point two lines are stated through in common, if exactly one."""
    common = set(first) & set(second)
    return next(iter(common)) if len(common) == 1 else None


def measure(coords: Coords, p: str, vertex: str, q: str) -> float | None:
    """Undirected angle at `vertex` between the rays to `p` and `q`, in degrees."""
    try:
        ax, ay = coords[vertex]
        ux, uy = coords[p][0] - ax, coords[p][1] - ay
        vx, vy = coords[q][0] - ax, coords[q][1] - ay
    except KeyError:
        return None
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu == 0.0 or nv == 0.0:
        return None
    cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / (nu * nv)))
    return math.degrees(math.acos(cosine))


def to_vertex_angle(args: tuple[str, ...], coords: Coords) -> VertexAngle | None:
    """Convert one directed line-to-line angle into a vertex angle.

    Returns None when the two lines do not meet at a stated point. That is a real angle — the
    angle between two non-incident lines — but it has no ∠ABC spelling, so the step naming it is
    untranslatable and becomes attrition rather than awkward prose.
    """
    pair = lines_of(args)
    if pair is None:
        return None
    first, second = pair
    vertex = shared_point(first, second)
    if vertex is None:
        return None
    p = first[0] if first[1] == vertex else first[1]
    q = second[0] if second[1] == vertex else second[1]
    if p == q:
        return None
    return VertexAngle(p=p, vertex=vertex, q=q)


def resolve_value(angle: VertexAngle, directed: Fraction, coords: Coords) -> VertexAngle | None:
    """Attach the exact vertex-angle value implied by a proved directed value.

    `directed` is in units of pi, as everywhere in GeoForge. The vertex angle is either that value
    in degrees or its supplement; the reference diagram says which. A measurement matching neither
    means the fact and the figure disagree, which is never a rounding problem — the conversion is
    refused so the mismatch surfaces instead of shipping a wrong angle.
    """
    measured = measure(coords, angle.p, angle.vertex, angle.q)
    if measured is None:
        return None
    as_degrees = directed * 180
    for candidate in (as_degrees, 180 - as_degrees):
        if abs(measured - float(candidate)) <= EXTRACTION.angle_snap_tolerance_degrees:
            return angle.with_value(candidate)
    return None
