"""Human-authored configuration library (docs/04 Stage 1, docs/07 T24).

Phase 3 M6 replaces random clause growth as the *only* source of figures. The reference clones
carry roughly 700 competition problems already written in the JGEX construction syntax this
pipeline emits, and they realize through the SAL at ~100%. Two uses, both measured before being
adopted:

* **Configuration seeding.** Take a problem's construction and discard its goal — their goals are
  `perp`/`cyclic` statements to *prove*, ours are values to *find*. The construction is a
  competition-grade skeleton; Stage 2 decorates it with an angle given, and Stage 5 asks our own
  question of it. Measured over 60 JGEX skeletons: 33% yield a goal against the sampler's 5.4%,
  with 25 distinct answers against 9 and a modal answer share of 11.1% against 36.0%.
* **Difficulty ground truth.** ~130 of these are IMO and IMO-shortlist problems, i.e. a corpus
  labelled hard by an authority outside this project. M5 established that we have no working
  difficulty instrument (docs/07 T22); a scorer that cannot separate these from textbook JGEX
  problems is refuted by data rather than by argument.

**Licensing (docs/07 P4).** The files live in `alphageometry/` and `Newclid/newclid/`, both
Apache-2.0, and the formalizations are the licensed artifact. Apache-2.0 permits derivative use
with attribution, which `NOTICE` carries. This module reads the reference clones and never copies
them into the repo, so the checkout stays the single source and nothing is re-licensed by us.

The clones are optional developer checkouts, so every function here degrades to an empty result
rather than raising when a dataset is absent — a missing corpus must not break a build.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from geoforge.generator.construction import Construction, Step


class Provenance(StrEnum):
    """Where a configuration came from, and what that says about its difficulty."""

    OLYMPIAD = "olympiad"
    """IMO, IMO shortlist or USAMO. The difficulty ground truth (docs/05 §5.1c)."""
    TEXTBOOK = "textbook"
    """JGEX's `complete2` collection: real geometry, routine difficulty."""


@dataclass(frozen=True, slots=True)
class Configuration:
    """One human-authored figure, with its own goal already stripped."""

    name: str
    construction: str
    """JGEX clauses only — everything before the `?`. Never includes their goal."""
    provenance: Provenance
    source: str
    """Dataset file stem, kept so a puzzle can cite where its skeleton came from."""

    @property
    def points(self) -> tuple[str, ...]:
        """Points the skeleton introduces, in order, deduplicated."""
        seen: list[str] = []
        for clause in self.construction.split(";"):
            head, sep, _ = clause.partition("=")
            if not sep:
                continue
            for token in head.split():
                if token not in seen:
                    seen.append(token)
        return tuple(seen)

    def to_construction(self) -> Construction:
        """Parse into our own `Construction`, so decorated skeletons reuse Stage 2 and pruning.

        Returns an empty construction for a clause we cannot parse rather than raising: these
        files are third-party data, and one unparseable line must cost one configuration, not
        the build.
        """
        steps: list[Step] = []
        for clause in self.construction.split(";"):
            head, sep, rest = clause.partition("=")
            if not sep:
                return Construction(steps=())
            outputs = tuple(head.split())
            # A clause may carry several comma-separated predicates constraining the same
            # outputs — `d = on_line d o h, on_line d a b` intersects two lines. All of them are
            # kept: dropping the tail leaves the point underdetermined, which realizes to a
            # *different figure* rather than to an error (`Step.extra`).
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


#: Dataset files, relative to the repo root, with the difficulty label each carries.
#: `imo_102_requires_aux` is deliberately absent from seeding use: by construction those are the
#: problems DDAR could *not* solve, so their skeletons are the least likely to yield a verified
#: goal. They remain valuable as ground truth, which is why the label rather than the path
#: decides how a dataset is used.
DATASETS: dict[str, tuple[str, Provenance]] = {
    "jgex_ag_231": ("Newclid/newclid/problems_datasets/jgex_ag_231.txt", Provenance.TEXTBOOK),
    "imo": ("Newclid/newclid/problems_datasets/imo.txt", Provenance.OLYMPIAD),
    "imo_sl": ("Newclid/newclid/problems_datasets/imo_sl.txt", Provenance.OLYMPIAD),
    "usamo": ("Newclid/newclid/problems_datasets/usamo.txt", Provenance.OLYMPIAD),
    "larger_imo_eval": (
        "Newclid/newclid/problems_datasets/larger_imo_eval.txt",
        Provenance.OLYMPIAD,
    ),
    "imo_102_requires_aux": (
        "Newclid/newclid/problems_datasets/imo_102_requires_aux.txt",
        Provenance.OLYMPIAD,
    ),
}


def repo_root() -> Path:
    """The checkout root, from this file's location. The clones are siblings of `src/`."""
    return Path(__file__).resolve().parents[3]


def _parse(text: str, source: str, provenance: Provenance) -> tuple[Configuration, ...]:
    """These files alternate a name line and a problem line, with no blank-line separator."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out: list[Configuration] = []
    for i in range(0, len(lines) - 1, 2):
        name, problem = lines[i], lines[i + 1]
        construction = problem.split("?")[0].strip().rstrip(";").strip()
        if not construction or "=" not in construction:
            continue
        out.append(
            Configuration(
                name=name, construction=construction, provenance=provenance, source=source
            )
        )
    return tuple(out)


def load(
    names: tuple[str, ...] | None = None, root: Path | None = None
) -> tuple[Configuration, ...]:
    """Every configuration from the named datasets, in deterministic order.

    Ordering is by (source, position in file) and never by set iteration, because Stage 1 indexes
    into this list and the whole pipeline must stay reproducible from its seed (docs/02
    invariant 2). A missing dataset contributes nothing and is not an error.
    """
    base = root or repo_root()
    out: list[Configuration] = []
    # Sorted even when the caller names them: Stage 1 indexes into this list, so the order
    # must depend on the datasets present and never on the order they were asked for.
    for key in sorted(names or DATASETS):
        relative, provenance = DATASETS[key]
        path = base / relative
        if not path.is_file():
            continue
        out.extend(_parse(path.read_text(encoding="utf-8"), key, provenance))
    return tuple(out)


def by_provenance(provenance: Provenance, root: Path | None = None) -> tuple[Configuration, ...]:
    """The ground-truth split (docs/05 §5.1c)."""
    return tuple(c for c in load(root=root) if c.provenance is provenance)


def available(root: Path | None = None) -> bool:
    """Whether any dataset is present. Callers gate on this rather than on a path."""
    base = root or repo_root()
    return any((base / relative).is_file() for relative, _ in DATASETS.values())
