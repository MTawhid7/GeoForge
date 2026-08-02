"""Stage 5: goal selection by numeric-propose / symbolic-verify (docs/04, docs/03 §3.3a).

The engines' `*compute` query predicates are not used — Yuclid rejects them outright. Instead
this stage does what `acompute` does internally and then hands the result back to the engine
for proof:

1. **Measure** the candidate quantity on the reference diagram (`quantities.goal_extractor`).
2. **Snap** it to an exact value, which doubles as the nice-value filter.
3. **Verify symbolically** — the engine must derive the explicit `aconst` from the premises.

Numerics propose; only symbolic derivation accepts (docs/02 invariant 4). A proposal that
survives step 2 but fails step 3 is the common and correct outcome: it means the diagram
happens to show a round number that the premises do not actually force. Phase 0 saw exactly
that on the tangent-chord and circumcentre figures, and both remain regression fixtures.

Verification runs through `solve_facts`, holding the coordinates fixed. Re-parsing the
construction with the goal attached (the Phase 0 spike's approach) makes the engine's problem
builder resample until the goal happens to hold numerically, which turns an under-determined
candidate into a hang instead of a rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoforge.config import EXTRACTION, GENERATION
from geoforge.generator.quantities import Proposal, QuantityType, enabled_types
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import (
    Fact,
    PremiseSpec,
    RealizedFigure,
    SolveOptions,
    SolveResult,
    distinct_rules,
)


@dataclass(frozen=True, slots=True)
class ExtractedGoal:
    """A candidate goal the engine has proved from the figure's premises."""

    proposal: Proposal
    fact: Fact
    """The engine's canonical form of the goal. Prefer this over `proposal.fact`: the two are
    the same fact, but only this one is guaranteed to match the ids used in the proof DAG."""
    result: SolveResult
    """The goal-mode solve, carrying the traced proof DAG that Stage 6 minimizes."""

    @property
    def quantity_type(self) -> str:
        return self.proposal.quantity_type

    @property
    def subject(self) -> tuple[str, ...]:
        return self.proposal.subject

    @property
    def depth(self) -> int:
        return self.result.proof_dag.depth()

    @property
    def distinct_rules(self) -> int:
        """Distinct justifications across the **whole solve**, not the minimal derivation.

        A cheap proxy, used only to reject a goal before Stage 6 pays for traceback. The number
        that ships is `Derivation.distinct_rules`, because docs/05 §5.1 scores the minimal
        translated sub-DAG.

        **It is not a bound on that number in either direction**, which is easy to assume and
        wrong. Stage 6 re-derives the goal from the *surviving* premises after minimization, so
        the sub-DAG is a fresh derivation over a restricted premise set rather than a subgraph
        of this one — and a proof with fewer givens to lean on often takes a longer, more varied
        route. Measured over 42 goals at seed 42: 32 agree, 2 come out lower, and 8 come out
        *higher*, every one of the 8 having dropped at least one premise.

        So this floor can in principle reject a goal whose published count would have passed.
        At the configured floor against observed counts it does not bind, but that is a fact
        about the threshold, not a property of the design — which is why docs/05's filter is
        re-asserted against the sub-DAG downstream rather than trusted from here.
        """
        return distinct_rules(self.result.proof_dag.steps)


class ExtractionReason(StrEnum):
    """Why a proposal did not become a goal. Counted in the attrition report (docs/04)."""

    NOT_VERIFIED = "not_verified"
    """The premises do not force the value the diagram showed — the intended rejection."""
    ALREADY_GIVEN = "already_given"
    """The goal is one of the construction's own stated givens."""
    TOO_SHALLOW = "too_shallow"
    """Below `GENERATION.min_proof_depth` or `min_distinct_rules`: not a puzzle."""
    UNRENDERABLE = "unrenderable"
    """The backend could not express the candidate as a predicate."""
    SURPLUS = "surplus"
    """Verified and interesting, but ranked below `max_goals_per_construction`. Not a defect —
    counted separately so the attrition report never confuses "no good goal" with "too many"."""
    ENGINE_ERROR = "engine_error"
    """The engine failed to answer at all. Counted, never confused with a rejection: "the
    engine crashed" and "the premises do not force this value" are different facts."""


@dataclass(frozen=True, slots=True)
class ExtractionReport:
    """What one construction yielded, and what it lost where."""

    goals: tuple[ExtractedGoal, ...]
    proposed: int
    rejected: tuple[tuple[str, ExtractionReason], ...]
    """(proposal key, reason) per discarded candidate, for the attrition report."""

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {"proposed": self.proposed, "accepted": len(self.goals)}
        for _, reason in self.rejected:
            out[str(reason)] = out.get(str(reason), 0) + 1
        return out


def propose(
    figure: RealizedFigure, types: tuple[QuantityType, ...] | None = None
) -> tuple[Proposal, ...]:
    """Run every enabled quantity type's `goal_extractor` over the reference coordinates."""
    coords = figure.coords()
    out: list[Proposal] = []
    for quantity_type in types or enabled_types():
        out.extend(quantity_type.goal_extractor(coords))
    return tuple(sorted(out))


def extract_goals(
    backend: SolverBackend,
    figure: RealizedFigure,
    opts: SolveOptions | None = None,
    *,
    types: tuple[QuantityType, ...] | None = None,
    max_goals: int | None = None,
    require_interesting: bool = True,
) -> ExtractionReport:
    """Propose, verify, and filter goals for one realized figure.

    `require_interesting` applies the shared depth and distinct-rule floors from `config`
    (`docs/04` Stage 5 uses the same thresholds as `docs/05`'s filters — one source). Turn it
    off to inspect what the engine proves before difficulty filtering, never to ship.
    """
    from geoforge.solvers.newclid_backend import UnsupportedFactKind

    opts = opts or SolveOptions()
    limit = GENERATION.max_goals_per_construction if max_goals is None else max_goals
    given = {fact.fact_id for fact in figure.declared}

    proposals = propose(figure, types)[: EXTRACTION.max_candidates_per_construction]
    verified: list[ExtractedGoal] = []
    rejected: list[tuple[str, ExtractionReason]] = []

    for proposal in proposals:
        # Cheap pre-check. It only catches the case where our spelling already matches the
        # engine's canonical one, so it saves an engine call but cannot be relied on; the
        # authoritative check is on the canonical fact after verification, below.
        if EXTRACTION.exclude_given_goals and proposal.fact.fact_id in given:
            rejected.append((proposal.key, ExtractionReason.ALREADY_GIVEN))
            continue

        spec = PremiseSpec(points=figure.points, premises=figure.declared, goals=(proposal.fact,))
        try:
            result = backend.solve_facts(spec, opts)
        except UnsupportedFactKind:
            rejected.append((proposal.key, ExtractionReason.UNRENDERABLE))
            continue
        except Exception:
            rejected.append((proposal.key, ExtractionReason.ENGINE_ERROR))
            continue

        if not result.solved or not result.proof_dag.proved_goals:
            rejected.append((proposal.key, ExtractionReason.NOT_VERIFIED))
            continue

        canonical = result.proof_dag.index()[result.proof_dag.proved_goals[0]]
        if EXTRACTION.exclude_given_goals and canonical.fact_id in given:
            # "Find angle ABC" where ABC = 50 degrees is a stated given is not a puzzle. This
            # is where it gets caught: only now is the fact in the same spelling as the givens.
            rejected.append((proposal.key, ExtractionReason.ALREADY_GIVEN))
            continue

        goal = ExtractedGoal(proposal=proposal, fact=canonical, result=result)
        if require_interesting and not _is_interesting(goal):
            rejected.append((proposal.key, ExtractionReason.TOO_SHALLOW))
            continue
        verified.append(goal)

    # Every candidate is verified before any is chosen, then the best `limit` are kept. Taking
    # the first N as they verify would select on the extractor's enumeration order — for angles,
    # alphabetically by vertex name — rather than on the puzzle being any good.
    ranked = sorted(verified, key=_preference)
    goals, surplus = ranked[:limit], ranked[limit:]
    rejected.extend((g.proposal.key, ExtractionReason.SURPLUS) for g in surplus)

    return ExtractionReport(goals=tuple(goals), proposed=len(proposals), rejected=tuple(rejected))


def _preference(goal: ExtractedGoal) -> tuple[int, int, str]:
    """Ranking key, best first (docs/04 Stage 5's "prefer" list).

    Deeper proofs using more distinct rules make better puzzles. The proposal key breaks ties so
    the choice is deterministic — required, since the whole batch must be reproducible from its
    seed (docs/02 invariant 2). The full multi-feature scorer is Phase 2's job (docs/05); this
    only has to pick sensibly among a handful of verified candidates.
    """
    return (-goal.depth, -goal.distinct_rules, goal.proposal.key)


def _is_interesting(goal: ExtractedGoal) -> bool:
    """Depth and rule-variety floors below which a puzzle is a restatement, not a puzzle."""
    return (
        goal.depth >= GENERATION.min_proof_depth
        and goal.distinct_rules >= GENERATION.min_distinct_rules
    )
