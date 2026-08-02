"""Runtime patches for upstream defects in newclid 3.0.1.

Permanent infrastructure, not a stopgap (docs/07 P1a): upstream CI builds the Yuclid C++
backend, which replaces both the AR deductor and the rule matcher, so the pure-Python path
is effectively untested upstream and we should expect to keep carrying fixes.

Each patch documents the defect and its evidence so it can be reported upstream and dropped
when fixed. `apply_all()` is called on import of `geoforge.solvers`, before any solver is
built. It is idempotent.

BUG-1  newclid.deductors.sympy_ar.ar_predicates.enumerate_lconsts
       `RatiosTable.expected_lconsts` is a `dict[SympySymbol, float]` (table_ratios.py:12),
       but the function iterates `table.expected_lconsts.copy()` and unpacks each item as a
       2-tuple. Iterating a dict yields keys only, so every call raises
       `TypeError: cannot unpack non-iterable Symbol object`.
       Fix: iterate `.items()`.
       Impact: any problem whose AR ratio table gets a length constant — i.e. most problems
       touching distances (on_circle, eqdistance, midpoint, orthocenter, lconst, ...).
       Why upstream misses it: their CI builds the Yuclid C++ backend, which replaces
       SympyARDeductor entirely, so the pure-Python path is not exercised. We need the
       pure-Python path because Yuclid does not support `acompute` goals.
       Verified present in both PyPI 3.0.1 and the git clone at ac65507.

BUG-3  newclid.proof_state.ProofState.justify
       `proof_justifications._proof_of_predicate` is written to report an unprovable goal by
       raising, and its caller catches `JustificationError` with the comment "Could not justify
       this goal, so we skip it" — setting `goal_is_proven[goal] = False`. But the raise it is
       meant to catch is `ProofState.justify`'s bare `ValueError`, and `JustificationError`
       derives from `Exception`, not from `ValueError`. The intended path is therefore dead:
       instead of reporting the goal unproven, `proof_data_from_state` propagates a ValueError.
       Fix: raise `JustificationError`, the type the caller already expects.
       Impact: any query about a goal that does *not* follow from the premises — which for us
       is not an edge case but the single most common answer during premise minimization
       (docs/04 Stage 6), where "the goal no longer holds" is precisely the signal that the
       premise was needed. Without this, a normal negative answer arrives as a crash.
       Found: M3, on 39 of 60 sampled constructions.

Style note
----------
Patched function bodies are kept **verbatim from upstream except for the fixed line**, so
they stay diffable against the original and are trivial to drop once upstream fixes them.
That means upstream's idioms (and untyped sympy internals) survive here, so this one file is
exempted from our lint/type rules in `pyproject.toml`. The exemption is scoped to this file
only and the patched path is covered by a real regression test
(`tests/solvers/test_contract.py::TestPatches`).
"""

from __future__ import annotations

import logging
from typing import Iterator, cast

import sympy as sp
from newclid.deductors.deductor_interface import justify_from_deductors
from newclid.deductors.sympy_ar import algebraic_manipulator, ar_predicates
from newclid.deductors.sympy_ar.table_ratios import RatiosTable
from newclid.justifications._index import JustificationError
from newclid.justifications.justify_predicates import justify_predicate
from newclid.numerical import close_enough
from newclid.predicate_types import PredicateArgument
from newclid.predicates._index import PredicateType
from newclid.problem import PredicateConstruction
from newclid.proof_state import ProofState
from newclid.tools import fraction_to_ratio, get_quotient

LOGGER = logging.getLogger(__name__)

_APPLIED: list[str] = []


def _enumerate_lconsts_fixed(
    table: RatiosTable,
) -> Iterator[tuple[PredicateConstruction, sp.Expr]]:
    """Upstream `enumerate_lconsts` with the dict-iteration fixed (`.items()`)."""
    for segment, expected_length_value in table.expected_lconsts.copy().items():
        lconst_expression = cast(sp.Expr, segment)
        subbed_in = table.inner_table.substitute_in_existing_expressions(lconst_expression)
        if not len(subbed_in.free_symbols) == 0:
            continue

        length: sp.Expr = sp.exp(subbed_in)
        if not close_enough(float(length), expected_length_value):
            LOGGER.error(f"Length {length} is not equal to expected length {expected_length_value}")

        p0, p1 = table.sympy_symbol_to_str_symbol[segment]
        points = tuple(PredicateArgument(pt.name) for pt in (p0, p1))

        length_arg = PredicateArgument(fraction_to_ratio(get_quotient(length)))
        lconst_construction = PredicateConstruction.from_predicate_type_and_args(
            PredicateType.CONSTANT_LENGTH, points + (length_arg,)
        )
        yield lconst_construction, lconst_expression


def _justify_fixed(self, predicate):
    """Upstream `ProofState.justify` raising the exception type its caller catches.

    Verbatim apart from the raised type: `JustificationError` instead of `ValueError`.
    """
    justification_cached = self.graph.hyper_graph.get(predicate)
    if justification_cached is not None:
        return justification_cached

    justification = justify_predicate(predicate, self.deductors, self.symbols)
    if justification is None:
        justification = justify_from_deductors(predicate, self.deductors, self.symbols)
    if justification is None:
        raise JustificationError(f"Could not justify predicate {predicate}")

    self.apply(justification)
    return justification


def apply_all() -> list[str]:
    """Apply every patch. Idempotent. Returns the list of applied patch ids."""
    if _APPLIED:
        return _APPLIED

    # BUG-1. Patch both the defining module and the consuming module's global, because
    # AlgebraicManipulator.__init__ builds its enumerator list from its own module globals.
    ar_predicates.enumerate_lconsts = _enumerate_lconsts_fixed  # type: ignore[assignment]
    algebraic_manipulator.enumerate_lconsts = _enumerate_lconsts_fixed  # type: ignore[assignment]
    _APPLIED.append("BUG-1:enumerate_lconsts-dict-items")

    # BUG-3. Bound method replacement: every ProofState instance picks this up, including the
    # ones built inside the engine where we never see the constructor.
    ProofState.justify = _justify_fixed  # type: ignore[method-assign]
    _APPLIED.append("BUG-3:justify-raises-justification-error")

    return _APPLIED
