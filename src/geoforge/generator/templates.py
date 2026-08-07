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

#: Angles a template may pin **by the opposite side** instead of by `s_angle` (docs/10 A5).
#:
#: The law of cosines gives r^2 = p^2 + q^2 - 2pq*cos(t), and `l2const` holds a `Fraction`, so
#: this only works where cos(t) is rational. Among the useful angles that is exactly 60 and 120
#: (cos = +/- 1/2), which give the integer r^2 = p^2 + q^2 -/+ pq. 90 would also qualify and is
#: excluded for the same reason it is excluded above.
#:
#: **Why bother**: MEASURED (70 draws, seed 42), every template stating an angle loses Stage 8 --
#: `sas` 0/11, `sas_centroid` 0/27, `sas_median` 3/39, `sas_two_medians` 3/42 -- while every
#: template pinning by length passes 100%. `s_angle b a c 60o` is a *directed* angle mod pi, so
#: the realizer places `c` on either side and the given renders as 60 degrees in one figure and
#: 120 in another. Three side lengths have one reading each.
SSS_ANGLES: tuple[int, ...] = (60, 120)


@dataclass(frozen=True, slots=True)
class AreaTemplate:
    """One reviewed area archetype: a parameterised construction and the region it pins."""

    name: str
    clauses: str
    """JGEX text with `{p}`, `{q}`, `{t}` and `{r2}` placeholders: two lengths, an angle, and
    the square of the side opposite it (docs/10 A5)."""
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
    hideable: tuple[str, ...] = ()
    """Region points this template can name in prose instead of drawing (docs/07 T29).

    Empty for the one-step templates: their region IS the pinned triangle, and hiding a vertex
    of it would leave nothing to ask about. The median templates hide `m` (and `n`), which turns
    "find the area of ABM" into "M is the midpoint of BC -- find the area of ABM", so the solver
    has to construct the point before the region even exists for them."""


#: The reviewed library. Every entry was instantiated 20 times and measured before landing
#: (docs/10 §10.10b, §10.10c); the `irrational` and `steps_to_solve` columns are those results.
TEMPLATES: tuple[AreaTemplate, ...] = (
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
        name="equilateral_median",
        clauses=(
            "a = free a; b = lconst b a {p}; c = lconst c a {p}, lconst c b {p}; m = midpoint m b c"
        ),
        region=("a", "b", "m"),
        irrational=True,
        steps_to_solve=2,
        uses=frozenset({"p"}),
        hideable=("m",),
    ),
    # --- pinned by the opposite side rather than by the angle (docs/10 A5) --------------
    #
    # These replaced an `s_angle` family of the same four shapes, RETIRED 2026-08-06 (docs/10
    # §10.10i). `l2const b c 19` says |BC| = sqrt(19) exactly, and an irrational side stated on
    # the figure is the target genre's own idiom rather than a workaround.
    #
    # `sss_centroid` is the best construction in the library to have to discover: the solver is
    # told two midpoints and an intersection, and must recognise the centroid and that it cuts a
    # third of the area. It needs the cevian rule in `area.py`, which needs the engine-derived
    # ratio CG/GM = 2 -- see `cevian_ratio_candidates`.
    AreaTemplate(
        name="sss",
        clauses="a = free a; b = lconst b a {p}; c = lconst c a {q}, l2const c b {r2}",
        region=("a", "b", "c"),
        irrational=True,
        steps_to_solve=1,
        uses=frozenset({"p", "q", "r2"}),
    ),
    AreaTemplate(
        name="sss_median",
        clauses=(
            "a = free a; b = lconst b a {p}; c = lconst c a {q}, l2const c b {r2};"
            " m = midpoint m b c"
        ),
        region=("a", "b", "m"),
        irrational=True,
        steps_to_solve=2,
        uses=frozenset({"p", "q", "r2"}),
        hideable=("m",),
    ),
    AreaTemplate(
        name="sss_two_medians",
        clauses=(
            "a = free a; b = lconst b a {p}; c = lconst c a {q}, l2const c b {r2};"
            " m = midpoint m b c; n = midpoint n b m"
        ),
        region=("a", "b", "n"),
        irrational=True,
        steps_to_solve=3,
        uses=frozenset({"p", "q", "r2"}),
        hideable=("m", "n"),
    ),
    AreaTemplate(
        name="sss_centroid",
        clauses=(
            "a = free a; b = lconst b a {p}; c = lconst c a {q}, l2const c b {r2};"
            " m = midpoint m a b; n = midpoint n b c; g = intersection_ll g c m a n"
        ),
        region=("a", "b", "g"),
        irrational=True,
        steps_to_solve=3,
        uses=frozenset({"p", "q", "r2"}),
        hideable=("m", "n", "g"),
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

    A template that consumes `{r2}` pins its triangle by the side opposite the angle rather than
    by the angle itself, so it draws from `SSS_ANGLES` and the angle never reaches the statement
    (docs/10 A5). `r2` is exact: the law of cosines at cos(t) = +/- 1/2 lands on an integer.
    """
    p = int(rng.integers(min_length, max_length + 1))
    q = int(rng.integers(min_length, max_length + 1))
    pins_by_side = "r2" in template.uses
    angles = SSS_ANGLES if pins_by_side else TEMPLATE_ANGLES
    t = int(rng.choice(np.array(angles)))
    if pins_by_side and t == 60 and p == q:
        # p == q at 60 degrees gives r^2 = p^2, i.e. an equilateral triangle stated as three
        # equal sides -- a duplicate of the `equilateral` template, and one the engine chokes
        # on: MEASURED, `l2const c b 25` beside `lconst b a 5` and `lconst c a 5` raises
        # DoubleCheckError out of AR ratio chasing, 5 times in 70 draws. 120 degrees on the same
        # two lengths is a legitimate isosceles triangle with an irrational base, so it is used
        # instead of re-drawing, which would consume rng draws and change every later figure.
        t = 120
    # r^2 = p^2 + q^2 - 2pq*cos(t); cos(60) = 1/2 and cos(120) = -1/2.
    r2 = p * p + q * q + (-p * q if t == 60 else p * q)
    return template.clauses.format(p=str(p), q=str(q), t=str(t), r2=str(r2))


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


def cevian_ratio_candidates(construction: Construction) -> tuple[tuple[str, str, str, str], ...]:
    """Ratio facts the area layer needs but the engine does not *declare* -- only derives.

    `area._cevian_split` reads a certified `rconst X P P Y`. On a centroid figure the engine
    proves `rconst c g g m 2/1` but never declares it, so the caller has to ask for it. This
    returns the argument tuples worth asking about: for each `intersection_ll` point P, the pairs
    (X, P, P, Y) where X and Y are the endpoints of a line P was built on.

    Returned as candidates, not facts -- proposing is all this may do, and the engine decides
    (docs/02 invariant 4).
    """
    out: list[tuple[str, str, str, str]] = []
    for step in construction.steps:
        if step.construction != "intersection_ll" or len(step.outputs) != 1:
            continue
        point = step.outputs[0]
        others = [a for a in step.all_args if a != point]
        # `intersection_ll p a b c d` -- two lines, so two (endpoint, endpoint) pairs.
        for i in range(0, len(others) - 1, 2):
            x, y = others[i], others[i + 1]
            out.append((x, point, point, y))
            out.append((y, point, point, x))
    return tuple(out)


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
