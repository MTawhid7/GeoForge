"""Display layout: choosing which drawing of a puzzle the player sees (docs/06 §6.3).

**We choose instantiations; we never move points.** docs/06 asks the layout to "optimize over
the remaining free parameters" and to "never perturb declared facts", and docs/07 T5 forbids
not-to-scale figures. Together those leave exactly one design: any nudge that is not a
similarity transform breaks some premise, because every premise is a metric statement about
this point set. So candidates are produced by *re-realizing the construction* through the SAL
at different seeds, and premise satisfaction is structural rather than a constraint an
optimizer has to be trusted with.

That also settles the numpy-versus-scipy question, which is not really about determinism. The
SAL exposes `realize(spec, opts)` keyed by a **seed**; seed → coordinates is a sampler, not a
differentiable map, so there is no continuous handle for an optimizer to take. What is left
decomposes into three problems scipy does not improve: candidate selection is an argmax over a
finite set, framing is closed-form in scale and translation and a one-dimensional grid scan in
rotation, and label placement is a small discrete assignment coupled only through label-label
collisions. If figures ever plateau at "acceptable, not beautiful" (docs/07 O4), the escalation
is more candidates and a better objective — and only then a geometric constraint solver that
moves points and re-projects onto the premise manifold, which is a different guarantee
(premises satisfied *to a tolerance*, not exactly) and needs a docs/07 entry before it lands.

Anti-leak perturbation (docs/06 §6.3 item 2) is deliberately **not** here yet; it arrives with
the forcedness query in a later milestone. Until then a built bank is marked non-shippable.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from geoforge.config import LAYOUT
from geoforge.generator.construction import Construction
from geoforge.generator.traceback import Derivation
from geoforge.generator.translation import Translation, translate
from geoforge.generator.translation.vertex_angles import VertexAngle, measure
from geoforge.generator.wellposed import same_configuration
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import SolveOptions

Coords = Mapping[str, tuple[float, float]]
Segment = tuple[str, str]


@dataclass(frozen=True, slots=True)
class LayoutResult:
    """The chosen drawing, or the reason there is none."""

    coords: dict[str, tuple[float, float]]
    labels: dict[str, tuple[float, float]]
    """Label offsets, in viewbox units, keyed by engine point name."""
    considered: int
    admissible: int
    score: float
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.reason is None


def lay_out(
    backend: SolverBackend,
    pruned: Construction,
    derivation: Derivation,
    translation: Translation,
    goal_angle: VertexAngle,
    reference_coords: Coords,
    segments: Sequence[Segment],
    seed: int,
) -> LayoutResult:
    """Pick the best admissible instantiation to draw, and place its labels.

    The reference figure is always among the candidates, so the layout can only improve on what
    Stage 9 would have drawn anyway — it never fails a puzzle that was already drawable.
    """
    drawn = tuple(pruned.points)
    scored: list[tuple[float, dict[str, tuple[float, float]]]] = []
    considered = 0

    for coords in _candidates(backend, pruned, reference_coords, drawn, seed):
        considered += 1
        if not _admissible(backend, coords, derivation, translation, goal_angle):
            continue
        rotated = _best_rotation(coords)
        scored.append((_score(rotated, segments), rotated))

    if not scored:
        return LayoutResult(
            coords=dict(reference_coords),
            labels={},
            considered=considered,
            admissible=0,
            score=0.0,
            reason="no_admissible_instantiation",
        )

    # Ties break on the score alone, and the reference figure is generated first, so an exact
    # tie keeps the reference — the deterministic choice rather than whichever seed came last.
    best_score, best = max(scored, key=lambda pair: pair[0])
    return LayoutResult(
        coords=best,
        labels=place_labels(best, segments),
        considered=considered,
        admissible=len(scored),
        score=best_score,
    )


def _candidates(
    backend: SolverBackend,
    pruned: Construction,
    reference_coords: Coords,
    drawn: tuple[str, ...],
    seed: int,
) -> list[dict[str, tuple[float, float]]]:
    """The reference figure, then fresh instantiations at deterministic seeds.

    The offset keeps these clear of the well-posedness gate's resample seeds, so a layout
    candidate is never silently the same figure Stage 8 already used to confirm the puzzle.
    """
    out = [{p: reference_coords[p] for p in drawn if p in reference_coords}]
    for k in range(LAYOUT.instantiation_samples):
        figure = backend.realize(pruned.to_spec(), SolveOptions(seed=seed + LAYOUT.seed_offset + k))
        if not figure.ok:
            continue
        coords = figure.coords()
        if all(p in coords for p in drawn):
            out.append({p: coords[p] for p in drawn})
    return out


def _admissible(
    backend: SolverBackend,
    coords: Coords,
    derivation: Derivation,
    translation: Translation,
    goal_angle: VertexAngle,
) -> bool:
    """Whether this drawing still supports the sentences the puzzle ships with.

    Three conditions docs/06 §6.3 does not state: the configuration matches the reference, the
    solution re-renders to identical text, and the goal still measures its published value.
    Matching the configuration is necessary and not sufficient, because configuration facts do
    not pin a figure completely (docs/07 T13) — so the direct question, "does the text still
    hold here", is asked directly by re-rendering it.

    **Measured: this never rejects a real candidate.** Across every instantiation of every
    puzzle in a seed-42 batch, and 400 further resamples of one construction, nothing was
    refused. Two reasons, and neither makes the check pointless:

    * Everything the puzzle publishes is *undirected* — vertex angles, distances, congruences.
      A reflection preserves all of those, so a mirrored drawing is genuinely a correct drawing
      and this rightly accepts it. (An earlier version of this docstring claimed reflection
      turns each angle into its supplement. That is what a *configuration flip* does; a global
      reflection is an isometry and does no such thing.)
    * Newclid's `realize` makes the same discrete topological choices for a fixed construction
      and varies only continuous parameters, so its instantiations share one configuration.

    So this is insurance against a backend that *does* explore configurations, and against a
    future where the drawn figure carries directed content. Kept because the failure it guards
    is silent and severe — a player shown a diagram in which the shipped text is false — and
    unit-tested directly rather than left asserted by nothing.
    """
    points = tuple(sorted((name, xy[0], xy[1]) for name, xy in coords.items()))
    if not same_configuration(backend, points, derivation.configuration):
        return False
    redrawn = translate(derivation.subdag, coords)
    if not redrawn.ok:
        return False
    if [s.text for s in redrawn.steps] != [s.text for s in translation.steps]:
        return False
    observed = measure(coords, goal_angle.p, goal_angle.vertex, goal_angle.q)
    if observed is None or goal_angle.degrees is None:
        return False
    return abs(observed - float(goal_angle.degrees)) <= LAYOUT.goal_render_tolerance_degrees


# --------------------------------------------------------------------------------------
# Objective
# --------------------------------------------------------------------------------------


def _normalized(coords: Coords) -> dict[str, tuple[float, float]]:
    """Scale to unit diameter so the score does not depend on the engine's arbitrary scale."""
    names = sorted(coords)
    array = np.array([coords[n] for n in names], dtype=float)
    span = float(np.max(np.ptp(array, axis=0)))
    if span <= 0:
        return {n: (0.0, 0.0) for n in names}
    centred = (array - array.mean(axis=0)) / span
    return {n: (float(centred[i][0]), float(centred[i][1])) for i, n in enumerate(names)}


def _score(coords: Coords, segments: Sequence[Segment]) -> float:
    """docs/06 §6.3 item 1, as a weighted sum. Higher is better.

    Every term is scale-free, so it compares drawings rather than sizes.
    """
    unit = _normalized(coords)
    names = sorted(unit)
    if len(names) < 2:
        return 0.0
    array = np.array([unit[n] for n in names], dtype=float)

    diff = array[:, None, :] - array[None, :, :]
    distances = np.hypot(diff[..., 0], diff[..., 1])
    np.fill_diagonal(distances, np.inf)
    min_separation = float(distances.min())

    width, height = (float(v) for v in np.ptp(array, axis=0))
    aspect = (width / height) if height > 0 else math.inf
    target = LAYOUT.viewbox_width / LAYOUT.viewbox_height
    aspect_penalty = abs(math.log(aspect / target)) if math.isfinite(aspect) and aspect > 0 else 4.0

    weights = LAYOUT.weights
    return (
        weights["separation"] * min_separation
        + weights["feature_angle"] * _min_feature_angle(unit, segments) / 90.0
        + weights["clearance"] * _min_clearance(unit, segments)
        - weights["aspect"] * aspect_penalty
    )


def _min_feature_angle(coords: Coords, segments: Sequence[Segment]) -> float:
    """The sharpest angle between two drawn segments meeting at a point, in degrees.

    A figure whose smallest feature angle is two degrees is unreadable however well spaced its
    points are, which is why separation alone is not the objective.
    """
    incident: dict[str, list[str]] = {}
    for a, b in segments:
        incident.setdefault(a.lower(), []).append(b.lower())
        incident.setdefault(b.lower(), []).append(a.lower())

    sharpest = 180.0
    for vertex, others in incident.items():
        if vertex not in coords:
            continue
        for i, first in enumerate(others):
            for second in others[i + 1 :]:
                if first not in coords or second not in coords or first == second:
                    continue
                angle = _angle_at(coords[vertex], coords[first], coords[second])
                if angle is not None:
                    sharpest = min(sharpest, angle)
    return sharpest


def _angle_at(
    apex: tuple[float, float], u: tuple[float, float], v: tuple[float, float]
) -> float | None:
    ux, uy = u[0] - apex[0], u[1] - apex[1]
    vx, vy = v[0] - apex[0], v[1] - apex[1]
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu == 0.0 or nv == 0.0:
        return None
    cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / (nu * nv)))
    return math.degrees(math.acos(cosine))


def _min_clearance(coords: Coords, segments: Sequence[Segment]) -> float:
    """Smallest distance from a point to a segment it is not an endpoint of.

    Stands in for label-collision risk: a point sitting almost on an unrelated line has nowhere
    to put its label, and reads as an incidence the puzzle never claimed.
    """
    clearance = 1.0
    for a, b in segments:
        first, second = a.lower(), b.lower()
        if first not in coords or second not in coords:
            continue
        for name, point in coords.items():
            if name in (first, second):
                continue
            clearance = min(
                clearance, _point_segment_distance(point, coords[first], coords[second])
            )
    return clearance


def _point_segment_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    if length == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _best_rotation(coords: Coords) -> dict[str, tuple[float, float]]:
    """Rotate on a fixed grid to fill the viewbox best.

    A grid scan rather than a local optimizer: the objective is periodic, so a descent method
    finds whichever local minimum it started nearest, and there is nothing to gain from
    sub-degree precision in a figure nobody measures with a protractor.

    Reflection is absent because it buys nothing, not because it would be unsafe — every
    published quantity is undirected and survives a mirror. `emit.frame` already applies one
    reflection (the y-flip into SVG's axis) for that reason.
    """
    names = sorted(coords)
    array = np.array([coords[n] for n in names], dtype=float)
    centre = array.mean(axis=0)
    centred = array - centre
    target = LAYOUT.viewbox_width / LAYOUT.viewbox_height

    best_cost, best = math.inf, array
    steps = max(1, int(round(180.0 / LAYOUT.rotation_grid_degrees)))
    for step in range(steps):
        theta = math.radians(step * LAYOUT.rotation_grid_degrees)
        cos, sin = math.cos(theta), math.sin(theta)
        rotated = centred @ np.array([[cos, -sin], [sin, cos]], dtype=float).T
        width, height = (float(v) for v in np.ptp(rotated, axis=0))
        if width <= 0 and height <= 0:
            continue
        # How much of the viewbox this pose fills, once framing scales it uniformly.
        scale = min(
            target / width if width > 0 else math.inf, 1.0 / height if height > 0 else math.inf
        )
        cost = -scale
        if cost < best_cost - 1e-12:
            best_cost, best = cost, rotated + centre
    return {n: (float(best[i][0]), float(best[i][1])) for i, n in enumerate(names)}


# --------------------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------------------


def place_labels(coords: Coords, segments: Sequence[Segment]) -> dict[str, tuple[float, float]]:
    """Offset each point label away from the figure, then relax label-label collisions.

    Greedy over a fixed set of compass directions, in canonical point order, so the result is a
    pure function of the geometry. Points are considered in order and each takes the direction
    that is furthest from the drawn ink and from labels already placed — which is why the
    relaxation passes matter: the first point chooses without knowing about the last.
    """
    unit = _normalized(coords)
    names = sorted(unit)
    directions = [
        (
            math.cos(2 * math.pi * k / LAYOUT.label_directions),
            math.sin(2 * math.pi * k / LAYOUT.label_directions),
        )
        for k in range(LAYOUT.label_directions)
    ]
    radius = LAYOUT.label_radius / max(LAYOUT.viewbox_width, LAYOUT.viewbox_height)
    chosen: dict[str, tuple[float, float]] = {n: directions[0] for n in names}

    for _ in range(LAYOUT.label_relaxation_passes):
        moved = False
        for name in names:
            best_direction, best_cost = chosen[name], math.inf
            for direction in directions:
                spot = (
                    unit[name][0] + direction[0] * radius,
                    unit[name][1] + direction[1] * radius,
                )
                cost = _label_cost(spot, name, unit, segments, chosen, radius)
                if cost < best_cost - 1e-12:
                    best_cost, best_direction = cost, direction
            if best_direction != chosen[name]:
                chosen[name] = best_direction
                moved = True
        if not moved:
            break

    return {
        # Back to viewbox units, and y is negated because framing flips the axis for SVG.
        name: (
            round(direction[0] * LAYOUT.label_radius, 2),
            round(-direction[1] * LAYOUT.label_radius, 2),
        )
        for name, direction in chosen.items()
    }


def _label_cost(
    spot: tuple[float, float],
    owner: str,
    coords: Coords,
    segments: Sequence[Segment],
    chosen: Mapping[str, tuple[float, float]],
    radius: float,
) -> float:
    """Lower is better: sum of inverse distances to everything a label should avoid."""
    cost = 0.0
    for name, point in coords.items():
        if name == owner:
            continue
        cost += 1.0 / (math.hypot(spot[0] - point[0], spot[1] - point[1]) + 1e-6)
        other = chosen.get(name)
        if other is not None:
            other_spot = (point[0] + other[0] * radius, point[1] + other[1] * radius)
            cost += 1.0 / (math.hypot(spot[0] - other_spot[0], spot[1] - other_spot[1]) + 1e-6)
    for a, b in segments:
        first, second = a.lower(), b.lower()
        if first in coords and second in coords:
            cost += 1.0 / (_point_segment_distance(spot, coords[first], coords[second]) + 1e-6)
    return cost
