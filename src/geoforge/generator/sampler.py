"""Stage 1-2: sample a construction and assign its numeric givens (docs/04).

A weighted grammar over the engine's construction catalogue, biased toward circles because
Phase 0 found they carry most of the non-trivial difficulty in angle chasing.

Design credit: the clause-by-clause growth strategy follows `ncdgen.build_diagram` from the
Newclid project (Apache-2.0). This is an independent implementation of that approach against
our own catalogue and configuration; see NOTICE.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from geoforge.config import GENERATION
from geoforge.config.thresholds import BandProfile
from geoforge.generator.construction import Construction, Step, fresh_point_names
from geoforge.generator.corpora import Configuration, load
from geoforge.solvers.catalog import ConstructionDef, catalog

Band = str


def draw(rng: np.random.Generator, *, band: Band = "easy") -> tuple[Construction, SamplerStats]:
    """Stage 1: produce one candidate construction, from either source (docs/04 Stage 1).

    `GENERATION.corpus_share` decides how often the figure comes from the human configuration
    library rather than from clause growth. It is a share and not a switch because the two
    sources fail differently — the library is finite and its skeletons repeat, growth is
    unbounded and mostly poor — and a bank wants both. Both draws come from the construction's
    own rng, so the choice stays a pure function of `(seed, index)` (docs/02 invariant 2).

    Falls back to growth when the reference clones are absent: the corpora are optional developer
    checkouts and a build without them must still produce puzzles (docs/07 P4).
    """
    library = _library()
    if library and rng.random() < GENERATION.corpus_share:
        configuration = library[int(rng.integers(0, len(library)))]
        construction, stats = decorate(rng, configuration, band)
        if construction.steps:
            return construction, stats
    return sample_construction(rng, band=band)


@lru_cache(maxsize=1)
def _library() -> tuple[Configuration, ...]:
    """The configuration library, read once, capped by size.

    Empty when the clones are not checked out. The size cap is `GENERATION.max_seed_points`; see
    there for the throughput measurement behind it.
    """
    return tuple(c for c in load() if len(c.points) <= GENERATION.max_seed_points)


@dataclass(frozen=True, slots=True)
class SamplerStats:
    """Why steps were abandoned. Feeds the per-stage attrition report (docs/04)."""

    steps_attempted: int = 0
    steps_committed: int = 0
    no_candidate: int = 0
    """No primitive could be applied with the points available."""
    origin: str = "grown"
    """`grown` for clause growth, or the seed configuration's name (docs/07 T24). Carried into
    the attrition report so the two sources can be compared without a separate run — the whole
    argument for seeding is a yield and answer-entropy comparison, and it should stay visible."""


def _usable(defs: tuple[ConstructionDef, ...], n_points: int) -> tuple[ConstructionDef, ...]:
    return tuple(
        d for d in defs if d.name not in GENERATION.excluded_constructions and d.arity <= n_points
    )


def profile_for(band: Band) -> BandProfile:
    """The Stage-1 profile for a band, falling back to easy for an unknown one."""
    return GENERATION.band_profiles.get(band, GENERATION.band_profiles["easy"])


def _weights(defs: tuple[ConstructionDef, ...], profile: BandProfile) -> np.ndarray:
    """Pick weights for one band's profile.

    Four small families are up-weighted and everything else sits at 1.0: those that draw a
    circle, state an angle value, bound a closed region, or state a length. Every one of them is
    tiny against ~62 usable extensions, so without a weight they are effectively never sampled —
    which is exactly what produced a corpus of squares answering 45 degrees with no angle given
    (docs/09 P3 M4), and what leaves a 6-step figure with no region to ask about (docs/10 §10.2).

    `max`, not sum or product: a primitive in two families gets the stronger pull rather than
    their compound, so adding a family cannot silently re-scale one that was already measured.
    `region_weight` and `length_weight` default to 1.0, so every existing band's draw is
    unchanged and only the `area` profile moves.
    """
    return np.array(
        [
            max(
                profile.circle_weight if d.introduces_circle else 1.0,
                profile.angle_weight if d.states_angle_value else 1.0,
                profile.region_weight if d.bounds_region else 1.0,
                profile.length_weight if d.states_length_value else 1.0,
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


def decorate(
    rng: np.random.Generator, configuration: Configuration, band: Band
) -> tuple[Construction, SamplerStats]:
    """Stage 2 over a human-authored skeleton (docs/04 Stage 1b, docs/07 T24).

    Competition configurations are *metric-free*: `triangle a b c` samples generic angles, so no
    angle in the figure has a nice value and Stage 5 has nothing to propose. Measured bare, 60
    JGEX skeletons yielded 4 goals. The skeleton supplies the shape; this supplies the values, by
    appending the same `s_angle` given clause growth already uses — the band's palette, unchanged
    (docs/04 Stage 2).

    Decorating rather than replacing is the whole idea: their configurations are richer than
    anything our grammar reaches, and our question is one they never ask.
    """
    profile = profile_for(band)
    base = configuration.to_construction()
    if not base.steps:
        return Construction(steps=()), SamplerStats(origin=configuration.name)

    points = list(base.points)
    steps = list(base.steps)
    attempted = committed = len(steps)

    # One given per band step-budget bracket, capped by what the skeleton can carry. More than
    # one pins the figure harder and yields more goals; too many make the answer a restatement
    # of a given, which Stage 5's `already_given` then discards.
    wanted = max(1, min(profile.max_givens, len(points) // 2))
    for _ in range(wanted):
        if len(points) < 2:
            break
        attempted += 1
        chosen = rng.choice(np.array(points), size=2, replace=False)
        a, b = str(chosen[0]), str(chosen[1])
        fresh = fresh_point_names(frozenset(points), 1)[0]
        degrees = _render_numeric_param(rng, "s_angle", band)
        steps.append(Step(construction="s_angle", outputs=(fresh,), args=(a, b, fresh, degrees)))
        points.append(fresh)
        committed += 1

    # Scale pinning (docs/10 §10.6). Area is the first *dimensional* quantity, so unlike angle it
    # needs a stated unit; `lconst x a 3` introduces `x` at a fixed distance from an existing
    # point, which fixes the figure's scale without constraining its shape.
    #
    # Deliberately ONE length by default (`max_length_givens` is 0 for every difficulty band and
    # 1 for the area profile). Two independent pinned lengths over-determine a figure and are
    # usually inconsistent, and the pinned length is a premise Stage 6 must keep, so each one
    # costs a given that the puzzle then has to earn back.
    for _ in range(profile.max_length_givens):
        if not points:
            break
        attempted += 1
        anchor = str(rng.choice(np.array(points)))
        fresh = fresh_point_names(frozenset(points), 1)[0]
        length = _render_numeric_param(rng, "lconst", band)
        steps.append(Step(construction="lconst", outputs=(fresh,), args=(fresh, anchor, length)))
        points.append(fresh)
        committed += 1

    return (
        Construction(steps=tuple(steps)),
        SamplerStats(
            steps_attempted=attempted, steps_committed=committed, origin=configuration.name
        ),
    )


def sample_construction(
    rng: np.random.Generator,
    *,
    band: Band = "easy",
    n_steps: int | None = None,
) -> tuple[Construction, SamplerStats]:
    """Draw one candidate construction by clause growth (docs/04 Stage 1a).

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

    # The same argument, for scale rather than for angle (docs/10 §10.6). An area is dimensional,
    # so a figure that pins no length has no determined area at all — the question cannot be
    # asked, let alone answered.
    #
    # A forced step rather than `length_weight` alone, because this repo has already measured
    # that weighting does not get you a given: at `angle_weight` 6-12, 91% of surviving puzzles
    # still stated no angle, since a weighted draw that misses never comes back to it. MEASURED
    # here at `length_weight` 10.0: only **78 of 200** area-profile constructions pinned a scale.
    if profile.require_length_given:
        length_defs = tuple(
            d for d in _usable(extension_defs, len(points)) if d.states_length_value
        )
        for _ in range(GENERATION.max_clause_attempts):
            if not length_defs:
                break
            attempted += 1
            length_step = _build_step(rng, _pick(rng, length_defs, profile), tuple(points), band)
            if length_step is not None:
                steps.append(length_step)
                committed += 1
                points.extend(length_step.outputs)
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
