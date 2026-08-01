"""Engine-neutral catalogue of construction primitives (docs/03 §3.4).

The sampler needs to know each primitive's shape — which arguments are existing points, which
are newly introduced, and which are numeric parameters. That knowledge lives inside the
engine, so it is exposed here rather than imported directly by `generator/`: nothing outside
`solvers/` may import engine code (docs/02 invariant 1). A future backend supplies its own
catalogue and the sampler is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

#: Constructions whose spare arguments are numeric values rather than points.
#: Kept as an explicit whitelist: a construction with unclassified leftover arguments is
#: excluded from the catalogue instead of being guessed at (see `_build_catalog`).
_NUMERIC_PARAM_CONSTRUCTIONS: frozenset[str] = frozenset(
    {"aconst", "s_angle", "lconst", "l2const", "rconst", "rconst2", "r2const"}
)

#: Predicate keywords that mean "this primitive puts a circle (or an equal-radius relation)
#: into the figure". Phase 0 found circles carry most of the difficulty in angle chasing, so
#: the sampler biases toward these (config.GENERATION.circle_step_weight).
_CIRCLE_KEYWORDS: tuple[str, ...] = ("cyclic", "circle", "cong")


@dataclass(frozen=True, slots=True, order=True)
class ConstructionDef:
    """One construction primitive, described without reference to any engine type."""

    name: str
    input_points: tuple[str, ...]
    """Placeholder names for points that must already exist."""
    output_points: tuple[str, ...]
    """Placeholder names for points this primitive introduces."""
    numeric_params: tuple[str, ...]
    """Placeholder names for numeric arguments, e.g. the angle in `s_angle a b x y`."""
    arg_order: tuple[str, ...]
    """Full argument order, needed to render the clause correctly."""
    is_seed: bool
    """True when the primitive needs no existing points, so it can start a figure."""
    introduces_circle: bool

    @property
    def arity(self) -> int:
        return len(self.input_points)


@lru_cache(maxsize=1)
def catalog() -> dict[str, ConstructionDef]:
    """The available primitives, keyed by name. Cached: the underlying data is static."""
    return _build_catalog()


def _build_catalog() -> dict[str, ConstructionDef]:
    from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS_BY_NAME

    out: dict[str, ConstructionDef] = {}
    for raw_name, definition in ALL_JGEX_CONSTRUCTIONS_BY_NAME.items():
        name = str(getattr(raw_name, "value", raw_name))
        inputs = tuple(str(a) for a in definition.input_points)
        outputs = tuple(str(a) for a in definition.output_points)
        args = tuple(str(a) for a in definition.args)
        leftover = tuple(a for a in args if a not in inputs and a not in outputs)

        if leftover and name not in _NUMERIC_PARAM_CONSTRUCTIONS:
            # Unclassified arguments: we cannot tell a point from a value, and guessing
            # would emit malformed clauses. Skip rather than risk it.
            continue
        if not outputs:
            continue

        clause_text = " ".join(str(c) for c in definition.clauses)
        out[name] = ConstructionDef(
            name=name,
            input_points=inputs,
            output_points=outputs,
            numeric_params=leftover,
            arg_order=args,
            is_seed=not inputs,
            introduces_circle=any(k in clause_text for k in _CIRCLE_KEYWORDS),
        )
    return out


def seeds() -> tuple[ConstructionDef, ...]:
    """Primitives that can start a figure, sorted for determinism."""
    return tuple(sorted(d for d in catalog().values() if d.is_seed))


def extensions() -> tuple[ConstructionDef, ...]:
    """Primitives that extend an existing figure, sorted for determinism."""
    return tuple(sorted(d for d in catalog().values() if not d.is_seed))
