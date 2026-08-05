"""Reviewed area construction templates (docs/10 step A1b).

**Why templates and not weighted random growth.** A1 biased the sampler toward region-bearing
primitives and got figures *containing* regions: 198 of 200. The area layer then computed **0
areas over 150 of them** (docs/10 §10.10b). The gap between those two numbers is the whole
reason this module exists — a generically-grown region has no determined area at all. Something
like `on_tline c a a b` places `c` on a perpendicular but leaves `|ac|` free, so the region's
area is not a function of the givens; there is nothing for any layer to compute, and Stage 8
would reject it regardless.

A template pins its region by design. MEASURED over the same generator: templated figures gave
**95 of 100** areas against random growth's 0, at 38 distinct values and 10.5% modal share, and
with decomposition available 45 distinct values at 6.0% — against angle's 9 values at 36.0%.

This is docs/07 L4 in a new quantity type ("the difficulty ceiling is the generator"), and the
response is the one docs/09 P5 already reaches for — a reviewed library of archetypes — at much
smaller scale, because an area template is four clauses rather than a competition configuration.

**Reviewed is load-bearing, exactly as it is for the translation table and the configuration
library.** A template nobody has checked is a figure nobody can vouch for, so each entry below
records what it yields and whether its answers are irrational.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from geoforge.generator.construction import Construction, Step

#: Angle values templates may state, in degrees. Deliberately excludes 90: a right angle makes
#: `sin C` = 1 and the SAS area rational, and it is the one angle that is its own supplement,
#: which is how two separate defects hid themselves (ONBOARDING gotcha 6). Multiples of 30 and 45
#: are kept here even though Stage 5 rejects them as *angle answers* (docs/07 T5) — an area of
#: `5*sqrt(3)/2` is not sight-readable just because the angle behind it was 60 degrees.
TEMPLATE_ANGLES: tuple[int, ...] = (30, 45, 60, 120, 135, 150)


@dataclass(frozen=True, slots=True)
class AreaTemplate:
    """One reviewed area archetype: a parameterised construction and the region it pins."""

    name: str
    clauses: str
    """JGEX text with `{p}`, `{q}` and `{t}` placeholders for two lengths and an angle."""
    region: tuple[str, str, str]
    """The triangle whose area the puzzle asks for. Not necessarily the pinned triangle."""
    irrational: bool
    """Whether this template's answers are irrational. MEASURED, not intended -- see the note on
    `right_legs`, whose answers are rational and which is therefore easy-band filler."""
    steps_to_solve: int
    """How many area steps the published solution takes. A one-step template is an arithmetic
    exercise; the midpoint templates are two."""
    uses: frozenset[str] = field(default_factory=lambda: frozenset({"p", "q", "t"}))
    """Which placeholders the template actually consumes."""


#: The reviewed library. Every entry was instantiated 20 times and measured before landing
#: (docs/10 §10.10b, §10.10c); the `irrational` and `steps_to_solve` columns are those results.
TEMPLATES: tuple[AreaTemplate, ...] = (
    AreaTemplate(
        name="sas",
        clauses="a = free a; b = lconst b a {p}; c = s_angle b a c {t}o, lconst c a {q}",
        region=("a", "b", "c"),
        irrational=True,
        steps_to_solve=1,
    ),
    AreaTemplate(
        name="equilateral",
        clauses="a = free a; b = lconst b a {p}; c = lconst c a {p}, lconst c b {p}",
        region=("a", "b", "c"),
        irrational=True,
        steps_to_solve=1,
        uses=frozenset({"p"}),
    ),
    AreaTemplate(
        name="right_legs",
        clauses="a = free a; b = lconst b a {p}; c = on_tline c a a b, lconst c a {q}",
        region=("a", "b", "c"),
        # (1/2)pq over integers is rational. Kept as honest easy-band filler, but a band built
        # only from these would reproduce angle's guessability problem in a new unit.
        irrational=False,
        steps_to_solve=1,
        uses=frozenset({"p", "q"}),
    ),
    AreaTemplate(
        name="sas_median",
        clauses=(
            "a = free a; b = lconst b a {p}; c = s_angle b a c {t}o, lconst c a {q};"
            " m = midpoint m b c"
        ),
        region=("a", "b", "m"),
        irrational=True,
        steps_to_solve=2,
    ),
    AreaTemplate(
        name="equilateral_median",
        clauses=(
            "a = free a; b = lconst b a {p}; c = lconst c a {p}, lconst c b {p}; m = midpoint m b c"
        ),
        region=("a", "b", "m"),
        irrational=True,
        steps_to_solve=2,
        uses=frozenset({"p"}),
    ),
    AreaTemplate(
        name="sas_two_medians",
        clauses=(
            "a = free a; b = lconst b a {p}; c = s_angle b a c {t}o, lconst c a {q};"
            " m = midpoint m b c; n = midpoint n b m"
        ),
        region=("a", "b", "n"),
        irrational=True,
        steps_to_solve=3,
    ),
)

TEMPLATES_BY_NAME: dict[str, AreaTemplate] = {t.name: t for t in TEMPLATES}


def render(
    template: AreaTemplate, rng: np.random.Generator, *, min_length: int, max_length: int
) -> str:
    """Instantiate a template's placeholders with drawn values.

    Lengths are small integers: they are *stated givens*, so they must be values a human would
    write on a figure, and a large one makes the answer's surd coefficient unreadable rather than
    harder. The angle comes from `TEMPLATE_ANGLES`, which excludes 90 degrees.
    """
    values = {
        "p": str(int(rng.integers(min_length, max_length + 1))),
        "q": str(int(rng.integers(min_length, max_length + 1))),
        "t": str(int(rng.choice(np.array(TEMPLATE_ANGLES)))),
    }
    return template.clauses.format(**values)


def to_construction(text: str) -> Construction:
    """Parse rendered JGEX into our own `Construction`.

    Deliberately the same shape as `corpora.Configuration.to_construction`, including keeping
    every comma-separated predicate of a clause: dropping the tail leaves a point
    underdetermined, which realizes to a *different figure* rather than to an error. That defect
    cost a milestone once already (`Step.extra`, docs/07 T24).
    """
    steps: list[Step] = []
    for clause in text.split(";"):
        head, sep, rest = clause.partition("=")
        if not sep:
            return Construction(steps=())
        outputs = tuple(head.split())
        predicates = [tuple(part.split()) for part in rest.split(",") if part.split()]
        if not predicates or not outputs:
            return Construction(steps=())
        first, *tail = predicates
        steps.append(
            Step(
                construction=first[0],
                outputs=outputs,
                args=tuple(first[1:]),
                extra=tuple(tail),
            )
        )
    return Construction(steps=tuple(steps))


def draw_area(
    rng: np.random.Generator,
    *,
    min_length: int = 2,
    max_length: int = 6,
    names: tuple[str, ...] | None = None,
) -> tuple[Construction, AreaTemplate, str]:
    """Draw one area construction: a template, instantiated.

    Returns the parsed construction, the template it came from, and the rendered JGEX text. The
    template travels with the construction because the **region is part of the question** — Stage
    5 cannot recover which triangle was meant by looking at the figure, and guessing would let
    the pipeline ask about a region the template never pinned.
    """
    library = (
        TEMPLATES
        if names is None
        else tuple(TEMPLATES_BY_NAME[n] for n in names if n in TEMPLATES_BY_NAME)
    )
    if not library:
        raise ValueError("no templates selected")
    template = library[int(rng.integers(0, len(library)))]
    text = render(template, rng, min_length=min_length, max_length=max_length)
    return to_construction(text), template, text
