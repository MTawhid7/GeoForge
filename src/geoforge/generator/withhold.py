"""Naming a point instead of drawing it, so the solver has to construct it (docs/07 T29).

**Why this exists.** docs/07 T22 traced `requires_auxiliary ≡ 0` to the pipeline drawing every
point, and T26 measured that withholding the goal's ancestor-closure complement leaves an
auxiliary requirement on only **1.8%** of goals. Both took the rule for *choosing what to
withhold* as given. It is not given -- it is ours.

1.8% is the rate at which a withheld point turns out to be **accidentally** load-bearing. Nothing
forces us to withhold accidentally. A statement may name a point descriptively -- "the midpoint of
BC" -- and omit it from the figure, and then the solver must construct it to answer at all. That
is an auxiliary construction **by design, at 100%**, and the engine still certifies the whole
derivation because the point exists in the construction that was solved.

**What this module does NOT do.** It does not change what is true, so it cannot make a sound
puzzle unsound; the answer is computed from the full construction either way. What it can break is
*well-posedness* (a description the solver cannot resolve) and *leakage* (a withheld point whose
position is readable off a visible one). Both are refusals here, not warnings.

**The description is correctness-bearing, so it is never LLM-written.** docs/02 invariant 5 lets
an LLM populate `solution[].text` and `given[].display` and nothing else. A phrase that *defines a
point* is part of the statement's meaning -- get it wrong and the puzzle asks a different
question -- so descriptions come from the table below, keyed by construction name, exactly as the
translation table works.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoforge.generator.construction import Construction, Step

#: Construction name -> a format string over the clause's *input* point names.
#:
#: Only primitives whose description pins the point **uniquely** may appear here. `on_line`
#: is absent on purpose: "a point on BC" does not determine which one, so withholding it would
#: make the statement ill-posed rather than hard. That is the distinction this table encodes, and
#: it is why the table is a whitelist rather than a fallback.
DESCRIPTIONS: dict[str, str] = {
    "midpoint": "the midpoint of {0}{1}",
    "foot": "the foot of the perpendicular from {0} to {1}{2}",
    "circumcenter": "the circumcenter of triangle {0}{1}{2}",
    "orthocenter": "the orthocenter of triangle {0}{1}{2}",
    "centroid": "the centroid of triangle {0}{1}{2}",
    "incenter": "the incenter of triangle {0}{1}{2}",
    "reflect": "the reflection of {0} in the line {1}{2}",
    "mirror": "the reflection of {0} in the point {1}",
    "intersection_ll": "the intersection of lines {0}{1} and {2}{3}",
}


class WithholdingError(ValueError):
    """A requested withholding would make the statement unreadable or ill-posed."""


@dataclass(frozen=True, slots=True)
class Withholding:
    """The result: which points the figure omits, and the prose that names them."""

    hidden: tuple[str, ...]
    """Points omitted from the figure, in construction order so descriptions resolve in order."""
    descriptions: tuple[str, ...]
    """One phrase per hidden point, aligned with `hidden`. Never LLM-written."""
    visible: tuple[str, ...]
    """Points the figure still draws."""

    @property
    def is_empty(self) -> bool:
        return not self.hidden


def _input_points(step: Step, known: frozenset[str]) -> tuple[str, ...]:
    """The already-existing points a clause references, in argument order, deduplicated.

    A clause repeats its own outputs inside the argument list (JGEX convention), and numeric
    parameters are interleaved, so both are filtered out. `all_args` rather than `args` because a
    point named only by a trailing predicate is still one this clause needs.
    """
    seen: list[str] = []
    for token in step.all_args:
        if token in step.outputs or token not in known or token in seen:
            continue
        seen.append(token)
    return tuple(seen)


def describe(step: Step, known: frozenset[str]) -> str | None:
    """The prose naming this clause's point, or None when it cannot be named uniquely."""
    pattern = DESCRIPTIONS.get(step.construction)
    if pattern is None:
        return None
    inputs = _input_points(step, known)
    try:
        return pattern.format(*(p.upper() for p in inputs))
    except IndexError:
        # The clause has fewer inputs than the phrase needs; refusing beats emitting "the
        # midpoint of B{}".
        return None


def candidates(construction: Construction) -> tuple[str, ...]:
    """Points that *could* be withheld, ignoring interactions between them.

    Two requirements, both about the statement rather than the geometry: the point must have a
    description that pins it uniquely (`DESCRIPTIONS`), and every input its clause names must
    already exist at that point in the construction.
    """
    known: set[str] = set()
    out: list[str] = []
    for step in construction.steps:
        if len(step.outputs) == 1 and describe(step, frozenset(known)) is not None:
            out.append(step.outputs[0])
        known.update(step.outputs)
    return tuple(out)


def plan(construction: Construction, hidden: tuple[str, ...]) -> Withholding:
    """Withhold `hidden`, or raise if that would leak or make the statement unresolvable.

    Two refusals, and the first is the one worth stating carefully:

    **No visible point may depend on a hidden one.** If `n = midpoint n b m` is drawn while `m`
    is withheld, the figure shows where `n` is, and `m` is recoverable from it by eye -- the
    puzzle would *look* like it hides a construction while giving it away. Requiring the hidden
    set to be closed downward under "is used by" removes that whole class.

    **A hidden point's description may only reference points the solver can resolve** -- visible
    ones, or hidden ones described earlier. Chains are allowed (hide `m`, then `n` defined from
    `m`) because the solver can construct them in order.
    """
    hidden_set = set(hidden)
    if not hidden_set:
        return Withholding((), (), tuple(construction.points))

    unknown = hidden_set - set(construction.points)
    if unknown:
        raise WithholdingError(f"not points of this construction: {sorted(unknown)}")

    known: set[str] = set()
    ordered: list[str] = []
    descriptions: list[str] = []
    for step in construction.steps:
        inputs = set(_input_points(step, frozenset(known)))
        produces_hidden = bool(set(step.outputs) & hidden_set)

        if not produces_hidden and inputs & hidden_set:
            raise WithholdingError(
                f"visible point(s) {sorted(set(step.outputs))} depend on hidden "
                f"{sorted(inputs & hidden_set)}; their position would give it away"
            )
        if produces_hidden:
            if len(step.outputs) != 1:
                raise WithholdingError(
                    f"clause introduces {list(step.outputs)} together; cannot hide one of them"
                )
            phrase = describe(step, frozenset(known))
            if phrase is None:
                raise WithholdingError(
                    f"no unique description for {step.outputs[0]} "
                    f"(construction {step.construction!r})"
                )
            ordered.append(step.outputs[0])
            descriptions.append(phrase)
        known.update(step.outputs)

    return Withholding(
        hidden=tuple(ordered),
        descriptions=tuple(descriptions),
        visible=tuple(p for p in construction.points if p not in hidden_set),
    )


def hide_for_region(construction: Construction, region: tuple[str, ...]) -> Withholding:
    """Withhold as much of the region's own scaffolding as is legal.

    This is the shape that makes an area question hard rather than arithmetic (docs/10 §10.10d):
    hiding a point the *region itself* is defined by means the solver must first work out which
    triangle is being asked about. Points outside the region are left visible -- hiding those adds
    reading difficulty without adding geometry, which docs/05 §5.5 rules out.

    Returns an empty `Withholding` when nothing is legally hideable, which is ordinary attrition.
    """
    hideable = [p for p in candidates(construction) if p in region]
    for size in range(len(hideable), 0, -1):
        try:
            return plan(construction, tuple(hideable[:size]))
        except WithholdingError:
            continue
    return Withholding((), (), tuple(construction.points))
