"""Stage 1-2: sample a construction and assign its numeric givens (docs/04).

A weighted grammar over the engine's construction catalogue, biased toward circles because
Phase 0 found they carry most of the non-trivial difficulty in angle chasing.

Design credit: the clause-by-clause growth strategy follows `ncdgen.build_diagram` from the
Newclid project (Apache-2.0). This is an independent implementation of that approach against
our own catalogue and configuration; see NOTICE.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoforge.config import GENERATION
from geoforge.config.thresholds import BandProfile
from geoforge.generator.construction import Construction, Step, fresh_point_names
from geoforge.solvers.catalog import ConstructionDef, catalog

Band = str


@dataclass(frozen=True, slots=True)
class SamplerStats:
    """Why steps were abandoned. Feeds the per-stage attrition report (docs/04)."""

    steps_attempted: int = 0
    steps_committed: int = 0
    no_candidate: int = 0
    """No primitive could be applied with the points available."""


def _usable(defs: tuple[ConstructionDef, ...], n_points: int) -> tuple[ConstructionDef, ...]:
    return tuple(
        d for d in defs if d.name not in GENERATION.excluded_constructions and d.arity <= n_points
    )


def profile_for(band: Band) -> BandProfile:
    """The Stage-1 profile for a band, falling back to easy for an unknown one."""
    return GENERATION.band_profiles.get(band, GENERATION.band_profiles["easy"])


def _weights(defs: tuple[ConstructionDef, ...], profile: BandProfile) -> np.ndarray:
    """Pick weights for one band's profile.

    Two primitives are up-weighted and everything else sits at 1.0: those that draw a circle,
    and those that state an angle value. Both sets are tiny — 2 of 62 usable extensions each —
    so without a weight they are effectively never sampled, which is exactly what produced a
    corpus of squares answering 45 degrees with no angle given (docs/09 P3 M4).
    """
    return np.array(
        [
            max(
                profile.circle_weight if d.introduces_circle else 1.0,
                profile.angle_weight if d.states_angle_value else 1.0,
            )
            for d in defs
        ],
        dtype=float,
    )


def _pick(
    rng: np.random.Generator, defs: tuple[ConstructionDef, ...], profile: BandProfile
) -> ConstructionDef:
    weights = _weights(defs, profile)
    index = int(rng.choice(len(defs), p=weights / weights.sum()))
    return defs[index]


def _render_numeric_param(rng: np.random.Generator, construction: str, band: Band) -> str:
    """Stage 2: draw a 'nice value' for a primitive's numeric argument.

    Angles are emitted in JGEX degree syntax (`30o`); ratios and lengths as small integers.
    """
    if construction in ("s_angle", "aconst"):
        palette = GENERATION.nice_angle_degrees.get(band, GENERATION.nice_angle_degrees["easy"])
        return f"{int(rng.choice(np.array(palette)))}o"
    if construction in ("rconst", "rconst2", "r2const"):
        return f"{int(rng.integers(2, 4))}/1"
    return str(int(rng.integers(2, 6)))


def _build_step(
    rng: np.random.Generator,
    definition: ConstructionDef,
    existing: tuple[str, ...],
    band: Band,
) -> Step | None:
    """Instantiate one primitive against the current figure, or None if it does not fit."""
    if definition.arity > len(existing):
        return None

    chosen = (
        tuple(str(p) for p in rng.choice(np.array(existing), size=definition.arity, replace=False))
        if definition.arity
        else ()
    )
    new_points = fresh_point_names(frozenset(existing), len(definition.output_points))

    binding: dict[str, str] = {}
    binding.update(dict(zip(definition.input_points, chosen, strict=True)))
    binding.update(dict(zip(definition.output_points, new_points, strict=True)))
    for param in definition.numeric_params:
        binding[param] = _render_numeric_param(rng, definition.name, band)

    try:
        args = tuple(binding[a] for a in definition.arg_order)
    except KeyError:
        # An argument we could not classify. Skipping is correct: emitting a clause with a
        # placeholder name would be malformed JGEX.
        return None

    return Step(construction=definition.name, outputs=new_points, args=args)


def sample_construction(
    rng: np.random.Generator,
    *,
    band: Band = "easy",
    n_steps: int | None = None,
) -> tuple[Construction, SamplerStats]:
    """Draw one candidate construction (docs/04 Stage 1).

    The result is pure data and has not been realized: whether it describes a valid figure is
    decided when the SAL tries to instantiate it (Stage 3).
    """
    profile = profile_for(band)
    if n_steps is None:
        n_steps = int(rng.integers(profile.min_steps, profile.max_steps + 1))

    all_defs = catalog()
    seed_defs = tuple(sorted(d for d in all_defs.values() if d.is_seed))
    extension_defs = tuple(sorted(d for d in all_defs.values() if not d.is_seed))

    seed_def = _pick(rng, _usable(seed_defs, n_points=0), profile)
    first = _build_step(rng, seed_def, existing=(), band=band)
    if first is None:  # pragma: no cover - seeds take no inputs, so they always fit
        raise RuntimeError(f"seed construction {seed_def.name} failed to instantiate")

    steps = [first]
    points = list(first.outputs)
    attempted = 1
    committed = 1
    no_candidate = 0

    # A figure that states no angle can only have its angles fixed by its own symmetry, and
    # those are exactly the multiples of 30 and 45 that Stage 5 now rejects (docs/07 T5).
    # MEASURED at seed 42 without this: 600 constructions produced one puzzle.
    if profile.require_angle_given:
        angle_defs = tuple(d for d in _usable(extension_defs, len(points)) if d.states_angle_value)
        for _ in range(GENERATION.max_clause_attempts):
            if not angle_defs:
                break
            attempted += 1
            angle_step = _build_step(rng, _pick(rng, angle_defs, profile), tuple(points), band)
            if angle_step is not None:
                steps.append(angle_step)
                committed += 1
                points.extend(angle_step.outputs)
                break

    while len(steps) < n_steps:
        candidates = _usable(extension_defs, n_points=len(points))
        if not candidates:
            no_candidate += 1
            break

        step: Step | None = None
        for _ in range(GENERATION.max_clause_attempts):
            attempted += 1
            step = _build_step(rng, _pick(rng, candidates, profile), tuple(points), band)
            if step is not None:
                break
        if step is None:
            no_candidate += 1
            break

        steps.append(step)
        committed += 1
        points.extend(step.outputs)

    return (
        Construction(steps=tuple(steps)),
        SamplerStats(
            steps_attempted=attempted,
            steps_committed=committed,
            no_candidate=no_candidate,
        ),
    )
