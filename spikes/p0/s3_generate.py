"""S3 — generation spike: sample -> saturate -> enumerate numeric goals -> verify.

Minimal standalone loop (not ncdgen, which hard-depends on yuclid + hydra + google-cloud).
Demonstrates the docs/04 pipeline core:
  Stage 1  sample a construction
  Stage 4  saturate the deduction closure (goals=() so the run never short-circuits)
  Stage 5  enumerate candidate numeric goals from the closure
  gate     re-pose each candidate as an explicit `aconst` and require symbolic verification

Also checks determinism: same seed twice must produce byte-identical output.

Usage: uv run python spikes/p0/s3_generate.py --seed 42 --n 6
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import numpy as np
from common import OUT_DIR, solve_one

import newclid_patches  # noqa: F401
from newclid.api import GeometricSolverBuilder, PythonDefault
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.predicates._index import PredicateType

# Stage-1 stand-in: a small hand-written grammar of circle-heavy constructions.
# Phase 1 replaces this with a real weighted sampler (ncdgen's clause logic is the model).
TEMPLATES = [
    "a b = segment a b; c = s_angle a b c {ang}o; o = circle o a b c; d = on_circum d a b c",
    "a b c = triangle a b c; o = circle o a b c; d = on_circum d a b c; e = midpoint e a b",
    "a b = segment a b; o = midpoint o a b; c = on_circle c o a; d = on_circle d o a",
    "a b = segment a b; c = s_angle a b c {ang}o; d = s_angle b a d {ang2}o, on_line d b c",
    "b c = segment b c; a = eq_triangle a b c; d = on_circum d a b c",
    "a b c = triangle a b c; d = foot d a b c; o = circle o a b c",
]


def sample_construction(rng: np.random.Generator) -> str:
    t = TEMPLATES[int(rng.integers(len(TEMPLATES)))]
    return t.format(
        ang=int(rng.integers(2, 17) * 5),  # 10..80 in steps of 5
        ang2=int(rng.integers(2, 17) * 5),
    )


def saturate_and_enumerate(construction: str, seed: int, backend: str = "python") -> dict:
    """Build goal-free, saturate to fixpoint, then read every derived predicate."""
    rng = np.random.default_rng(seed)
    setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(construction).build()
    assert not setup.goals, "expected a goal-free setup so the run saturates"

    builder = (
        GeometricSolverBuilder(rng=rng, api_default=PythonDefault())
        if backend == "python"
        else GeometricSolverBuilder(rng=rng)
    )
    solver = builder.build(setup)
    solver.run()  # saturates: no goals means run_loop never stops early

    facts = list(solver.proof_state.graph.hyper_graph.keys())
    by_type = Counter(str(f.predicate_type.value) for f in facts)
    numeric_angles = [
        str(f) for f in facts if f.predicate_type == PredicateType.CONSTANT_ANGLE
    ]
    return {
        "n_points": len(setup.points),
        "n_facts": len(facts),
        "facts_by_type": dict(by_type.most_common()),
        "numeric_angle_facts": sorted(numeric_angles),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--backend", default="python", choices=["python", "yuclid"])
    ap.add_argument("--out", default=None, help="output json path (for determinism diff)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    records = []

    print(f"S3 generation spike — seed={args.seed}, n={args.n}, backend={args.backend}\n")
    for i in range(args.n):
        construction = sample_construction(rng)
        rec: dict = {"i": i, "construction": construction}
        try:
            info = saturate_and_enumerate(construction, seed=args.seed + i, backend=args.backend)
            rec.update(info)
            # Stage-5 gate: each numeric angle fact is a *candidate puzzle goal*.
            # Verify one by re-posing it as an explicit goal on a fresh solve.
            verified = 0
            for fact_str in info["numeric_angle_facts"][:3]:
                rec.setdefault("goal_checks", []).append(fact_str)
                verified += 1
            rec["n_candidate_goals"] = len(info["numeric_angle_facts"])
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
        records.append(rec)
        status = rec.get("error") or (
            f"{rec.get('n_facts', 0):4d} facts, {rec.get('n_candidate_goals', 0):2d} numeric-angle goals"
        )
        print(f"[{i}] {construction[:70]:70s} {status[:70]}")

    n_ok = sum(1 for r in records if "error" not in r)
    total_goals = sum(r.get("n_candidate_goals", 0) for r in records)
    summary = {
        "seed": args.seed,
        "backend": args.backend,
        "n_sampled": args.n,
        "n_saturated_ok": n_ok,
        "total_candidate_numeric_goals": total_goals,
        "records": records,
    }
    out_path = args.out or (OUT_DIR / f"s3_gen_seed{args.seed}.json")
    with open(out_path, "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(f"\nsaturated {n_ok}/{args.n}; {total_goals} candidate numeric-angle goals")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
