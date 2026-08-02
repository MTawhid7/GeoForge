"""AlphaGeometry 2 DDAR adapter — the independent bank validator (docs/02 invariant 3).

The only module in GeoForge that touches the vendored AG2 code. Its job is one question:
*given these premises over this diagram, does an engine that shares no lineage with Newclid
derive the same answer?* A soundness bug in one engine is then unlikely to be mirrored in the
other, which is the entire point of running two.

Three things distinguish this adapter from `newclid_backend`:

**It is a `ValidatorBackend`, not a `SolverBackend`.** DDAR has no construction language and no
proof recorder, so `solve` and `realize` do not exist here — see `interface.ValidatorBackend`.
`proof_dag.steps` is always empty: DDAR certifies truth, it does not narrate it. Readable
proofs come from the generation engine, and always did.

**The angle convention is inverted, and correcting it is not optional.** DDAR's `aconst p q r s`
asserts `dir(pq) - dir(rs) = value`; Newclid's asserts `dir(rs) - dir(pq) = value`, GeoForge's
normative convention (`types.py`). The same fact therefore has to be handed to DDAR with its two
line pairs *swapped*. Measured negative control (M6, over the 129-puzzle acceptance
bank): validating without the swap accepts 25 of 129 — exactly the 25 whose answer is 90 deg,
the one angle equal to its own supplement. Uncalibrated, this validator would reject every
puzzle that is not a right angle and would have looked like a catastrophic soundness failure.
`test_ag2_contract.py` pins the convention against a figure whose angle is not 90 deg, so it
cannot silently drift back.

Swapping the pairs is preferred over rewriting the value as `180 - value`: it is exact on
Fractions and needs no mod-180 normalization at value 0.

**Coordinates never travel as text.** DDAR's `AGProblem.pstring` round-trips points through
`name@x_y`, and it asserts premises numerically at roughly 1e-6, so a decimal-formatted export
could shift a figure enough to matter. We build `AGPoint` objects from the float64 coordinates
directly. `problem_string()` exists only to write a human-runnable reproduction case.

Vendoring note: `vendor/ag2_ddar/` ships no package (upstream has no `pyproject.toml` and is
not on PyPI — see its `PROVENANCE.md`), and its modules import each other by bare name. The
directory is therefore *appended* to `sys.path`, never prepended, so a vendored module named
`parse` or `test` can never shadow a stdlib or site-packages one.
"""

from __future__ import annotations

import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from geoforge.solvers.types import (
    CONFIGURATION_KINDS,
    Fact,
    FactId,
    FactKind,
    PremiseSpec,
    ProofDAG,
    SolveOptions,
    SolveResult,
    SolveStats,
)

ENGINE_NAME = "ag2ddar"

#: Upstream commit of the vendored snapshot. DDAR ships no version number, so the commit *is*
#: the version. Kept in sync with `vendor/ag2_ddar/PROVENANCE.md` by a contract test rather
#: than by discipline.
ENGINE_VERSION = "251e7e16f0bba8ac7c83cdea789fccc195d0c0c7"

VENDOR_DIR = Path(__file__).resolve().parents[3] / "vendor" / "ag2_ddar"


class UnsupportedByValidator(ValueError):
    """A fact the validator cannot state to DDAR.

    Raised, never skipped. Quietly dropping a premise would hand DDAR a *weaker* problem than
    the puzzle claims, so a "validated" verdict would certify something the puzzle never said.
    """


def _vendor() -> tuple[Any, Any, Any]:
    """Import the vendored DDAR modules, appending their directory to `sys.path` once."""
    path = str(VENDOR_DIR)
    if path not in sys.path:
        if not (VENDOR_DIR / "ddar.py").is_file():
            raise ImportError(
                f"vendored AG2 DDAR not found at {VENDOR_DIR}. Bank validation requires the "
                "second engine; it is not optional (docs/02 invariant 3)."
            )
        sys.path.append(path)
    import ddar  # type: ignore[import-not-found]
    import parse  # type: ignore[import-not-found]

    import numpy  # isort: skip

    return ddar, parse, numpy


# --------------------------------------------------------------------------------------
# Fact -> DDAR predicate
# --------------------------------------------------------------------------------------


def _aconst(args: tuple[str, ...], value: Fraction) -> tuple[str, ...]:
    """Render a constant angle, applying the convention calibration (module docstring).

    `aconst a b c d = v` means "the directed angle from line ab to line cd is v" for us and
    "from cd to ab" for DDAR, so the pairs swap. The value spelling `{n}pi/{d}` is the one
    both engines already use, so nothing is lost converting it.
    """
    a, b, c, d = args
    return (f"aconst {c} {d} {a} {b} {value.numerator}pi/{value.denominator}",)


def _midp(args: tuple[str, ...]) -> tuple[str, ...]:
    """`midp m a b` — DDAR has no midpoint predicate, so state what it means.

    Betweenness is not asserted: DDAR has no predicate for it, and it holds in the exported
    diagram anyway. Both halves that DDAR *can* use are stated, so nothing is weakened in the
    direction that matters (an unstated hypothesis can only make validation harder to pass).
    """
    m, a, b = args
    return (f"coll {m} {a} {b}", f"cong {m} {a} {m} {b}")


def _circle(args: tuple[str, ...]) -> tuple[str, ...]:
    """`circle o a b c` — o is the circumcenter, i.e. equidistant from the other three."""
    o, a, b, c = args
    return (f"cong {o} {a} {o} {b}", f"cong {o} {a} {o} {c}")


def _rconst(args: tuple[str, ...], value: Fraction) -> tuple[str, ...]:
    a, b, c, d = args
    return (f"rconst {a} {b} {c} {d} {value.numerator}/{value.denominator}",)


def _contri(args: tuple[str, ...]) -> tuple[str, ...]:
    """`contri a b c p q r` — triangles ABC and PQR congruent. SSS states it exactly."""
    a, b, c, p, q, r = args
    return (f"cong {a} {b} {p} {q}", f"cong {b} {c} {q} {r}", f"cong {c} {a} {r} {p}")


def _simtri(args: tuple[str, ...]) -> tuple[str, ...]:
    """`simtri a b c p q r` — triangles ABC and PQR similar, as two ratio equalities.

    Three sides in proportion is SSS similarity, so this is the metric content in full.
    """
    a, b, c, p, q, r = args
    return (f"eqratio {a} {b} {p} {q} {b} {c} {q} {r}", f"eqratio {b} {c} {q} {r} {c} {a} {r} {p}")


#: Fact kinds DDAR states verbatim. Orientation-invariant by construction: `eqangle`, `para`
#: and `perp` all reduce to a *difference* of directed angles, which the inverted convention
#: negates and therefore leaves equal to zero (or to a right angle, its own supplement). Only
#: valued angles need the calibration.
_VERBATIM: frozenset[FactKind] = frozenset(
    {
        FactKind.COLLINEAR,
        FactKind.PARALLEL,
        FactKind.PERPENDICULAR,
        FactKind.CONGRUENT,
        FactKind.EQUAL_ANGLES,
        FactKind.EQUAL_RATIOS,
        FactKind.CYCLIC,
    }
)


def to_ddar_predicates(fact: Fact) -> tuple[str, ...]:
    """Render one GeoForge fact as the DDAR predicate string(s) that state it.

    A fact may need more than one predicate (`midp`, `circle`, `contri`) because DDAR's
    vocabulary is smaller. Raises `UnsupportedByValidator` for anything else, including
    configuration facts: those are properties of the diagram DDAR is given, and stating them is
    neither possible (DDAR has no `sameclock`) nor meaningful (see `bank/validate.py`).

    Where DDAR's vocabulary is smaller, the expansion states the *metric* content and lets DDAR
    recover the rest. `contri` and `simtri` carry an orientation (clock vs reflect) that SSS
    congruence and SSS proportion do not; DDAR's own similar-triangle search reads orientation
    off the coordinates, exactly as Newclid's numerical checks do, and re-derives the angle
    consequences. The expansion is therefore *weaker* than the fact, never stronger — which is
    the safe direction, since an unstated hypothesis can only make validation harder to pass.
    """
    if fact.kind in _VERBATIM:
        return (f"{fact.kind.value} {' '.join(fact.args)}",)
    if fact.kind is FactKind.MIDPOINT:
        return _midp(fact.args)
    if fact.kind is FactKind.CIRCUMCENTER:
        return _circle(fact.args)
    if fact.kind in (FactKind.CONTRI_CLOCK, FactKind.CONTRI_REFLECT):
        return _contri(fact.args)
    if fact.kind in (FactKind.SIMTRI_CLOCK, FactKind.SIMTRI_REFLECT):
        return _simtri(fact.args)
    if fact.kind is FactKind.CONSTANT_ANGLE and fact.value is not None:
        return _aconst(fact.args, fact.value)
    if fact.kind is FactKind.CONSTANT_RATIO and fact.value is not None:
        return _rconst(fact.args, fact.value)
    if fact.kind in CONFIGURATION_KINDS:
        raise UnsupportedByValidator(
            f"{fact.fact_id} is a configuration fact; DDAR has no vocabulary for it and it "
            "holds of the exported diagram by construction. Filter these out before calling "
            "the validator rather than pretending they were asserted."
        )
    raise UnsupportedByValidator(
        f"{fact.fact_id}: no DDAR predicate is registered for kind {fact.kind.value!r}. "
        "Add one here (with a calibration test) rather than letting the fact be dropped."
    )


def problem_string(spec: PremiseSpec) -> str:
    """The spec as a DDAR problem string, for reproduction cases.

    Not used by validation itself — `pstring`'s decimal round-trip is exactly the precision
    loss the module docstring warns about. This is for pasting into a debugging session.
    """
    points = "; ".join(f"{name}@{x!r}_{y!r} = " for name, x, y in spec.points)
    preds = ", ".join(p for f in spec.premises for p in to_ddar_predicates(f))
    goals = "; ".join(p for f in spec.goals for p in to_ddar_predicates(f))
    return f"{points}{preds}" + (f" ? {goals}" if goals else "")


# --------------------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------------------


class AG2DDARBackend:
    """Implements `ValidatorBackend` over the vendored AlphaGeometry 2 DDAR."""

    name = ENGINE_NAME
    engine_version = ENGINE_VERSION

    def solve_facts(self, spec: PremiseSpec, opts: SolveOptions | None = None) -> SolveResult:
        """Force `spec.premises`, saturate, and report which goals DDAR derives.

        `opts.seed` is ignored, and that is a property rather than a gap: DDAR draws no random
        numbers — the diagram arrives fully determined in `spec.points` — so the run is
        deterministic without seeding. It is why a determinism test here is cheap.

        `opts.max_wall_seconds` is enforced **after the fact**, surfacing as `stats.hit_cap`.
        DDAR's closure loop offers no interruption point, so a cap cannot stop a run in
        progress; what it can do is stop a blow-up being silently accepted as a result
        (docs/08 §8.1). Measured, the cap is three orders above a normal puzzle.
        """
        from geoforge.config import VALIDATION

        opts = opts or SolveOptions()
        ddar, parse, numpy = _vendor()
        started = time.perf_counter()

        points = {name: parse.AGPoint(name, numpy.array([x, y])) for name, x, y in spec.points}
        engine = ddar.DDAR(list(points.values()))

        for fact in spec.premises:
            for text in to_ddar_predicates(fact):
                engine.force_pred(_parse(parse, text, points))
        # progress_dot=False: the default prints a dot per closure round to stdout, which would
        # corrupt any machine-readable output the validator CLI writes.
        engine.deduction_closure(progress_dot=False)

        proved: list[FactId] = []
        unproved: list[str] = []
        for fact in spec.goals:
            # A goal may expand to several predicates (a `contri` goal, say). All of them must
            # hold: the goal is the conjunction, and accepting the first would be a weaker claim.
            checks = (
                bool(engine.check_pred(_parse(parse, text, points)))
                for text in to_ddar_predicates(fact)
            )
            (proved if all(checks) else unproved).append(fact.fact_id)

        wall = time.perf_counter() - started
        facts = tuple(sorted({*spec.premises, *spec.goals}))
        dag = ProofDAG(
            facts=facts,
            # DDAR records no derivation, so there is nothing honest to put here. An invented
            # single "step" from premises to goal would look like a proof and be none.
            steps=(),
            assumptions=tuple(f.fact_id for f in spec.premises),
            numerical_checks=(),
            trivial=(),
            proved_goals=tuple(proved),
            unproved_goals=tuple(sorted(unproved)),
        )
        return SolveResult(
            spec=spec,
            facts=facts,
            proof_dag=dag,
            numeric_model=spec.points,
            stats=SolveStats(
                engine=ENGINE_NAME,
                engine_version=ENGINE_VERSION,
                n_facts=len(facts),
                saturated=True,
                hit_cap=wall > (opts.max_wall_seconds or VALIDATION.max_wall_seconds),
                wall_seconds=wall,
            ),
            solved=bool(spec.goals) and not unproved,
        )


def _parse(parse_module: Any, text: str, points: dict[str, Any]) -> Any:
    """Parse a DDAR predicate string and bind its point names to this problem's AGPoints."""
    predicate = parse_module.AGPredicate.parse(text)
    missing = [p for p in predicate.points if p not in points]
    if missing:
        raise UnsupportedByValidator(
            f"predicate {text!r} names points {missing} that the figure does not contain"
        )
    return predicate.replace_points(points)
