"""Typed construction layer over JGEX (docs/03 §3.4).

A `Construction` is an ordered list of steps that renders to JGEX surface syntax. JGEX stays
the wire format because it is the lingua franca of the AlphaGeometry lineage, which buys
interoperability with engine benchmarks and reference corpora for free.

The type is pure data: it knows nothing about any engine, and realizing it (assigning
coordinates) happens through the SAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from geoforge.solvers.types import ProblemSpec

#: JGEX point names: a..z, then a1..z1, a2..z2, ... Deterministic and unbounded.
_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def point_names() -> list[str]:
    """First 26 names; `fresh_point_names` extends past that."""
    return list(_LETTERS)


def fresh_point_names(taken: frozenset[str], how_many: int) -> tuple[str, ...]:
    """Deterministically pick `how_many` names not already in `taken`."""
    out: list[str] = []
    for suffix in count():
        tag = "" if suffix == 0 else str(suffix)
        for letter in _LETTERS:
            name = f"{letter}{tag}"
            if name not in taken and name not in out:
                out.append(name)
                if len(out) == how_many:
                    return tuple(out)
    raise AssertionError("unreachable: name generator is infinite")


@dataclass(frozen=True, slots=True)
class Step:
    """One construction clause, e.g. `d = on_circum d a b c`.

    JGEX puts the introduced points on the left of `=` and repeats them inside the argument
    list at the position the primitive expects, so both are recorded.
    """

    construction: str
    outputs: tuple[str, ...]
    args: tuple[str, ...]
    """Full argument list in the primitive's own order, points and values interleaved."""

    def to_jgex(self) -> str:
        return f"{' '.join(self.outputs)} = {self.construction} {' '.join(self.args)}".rstrip()

    @property
    def numeric_values(self) -> tuple[str, ...]:
        """Arguments that are values rather than point names, e.g. ('30o',)."""
        return tuple(a for a in self.args if not a.isalnum() or a[0].isdigit())


@dataclass(frozen=True, slots=True)
class Construction:
    """An ordered, engine-independent figure description."""

    steps: tuple[Step, ...]

    @property
    def points(self) -> tuple[str, ...]:
        """Every point introduced, in introduction order (deduplicated)."""
        seen: list[str] = []
        for step in self.steps:
            for p in step.outputs:
                if p not in seen:
                    seen.append(p)
        return tuple(seen)

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def introduces_circle(self) -> bool:
        from geoforge.solvers.catalog import catalog

        defs = catalog()
        return any(
            step.construction in defs and defs[step.construction].introduces_circle
            for step in self.steps
        )

    def to_jgex(self) -> str:
        return "; ".join(step.to_jgex() for step in self.steps)

    def to_spec(self, goals: tuple[str, ...] = ()) -> ProblemSpec:
        return ProblemSpec(construction=self.to_jgex(), goals=goals)

    def provenance(self) -> str:
        """Compact serialization stored in puzzle JSON (docs/02 `provenance`)."""
        return self.to_jgex()

    def __str__(self) -> str:
        return self.to_jgex()
