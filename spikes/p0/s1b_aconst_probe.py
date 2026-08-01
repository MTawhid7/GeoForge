"""S1b — the goal-extraction mechanism test (Decision 3b).

Hypothesis: GeoForge never needs the `acompute` predicate (which Yuclid rejects). Our goal
extractor can instead do what `acompute` does internally — read the value off the diagram
numerically — and then ask the engine to *symbolically* verify the corresponding `aconst`.
Soundness stays symbolic; the numeric step only proposes a candidate.

If this holds on the Yuclid backend, we get the fast C++ engine AND numeric quantity goals.
"""

from __future__ import annotations

import json
from fractions import Fraction

import numpy as np
from common import OUT_DIR, solve_one

import newclid_patches  # noqa: F401  (applies upstream bug patches on import)
from newclid.api import GeometricSolverBuilder, PythonDefault
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.tools import get_quotient

# Problems whose goal we want as a *value*, expressed with an acompute-style query.
# (name, construction part, the 4 points of the angle we want to compute)
CASES = [
    ("acompute_eq_triangle", "a = free a; b = lconst b a 3; c = eq_triangle c a b", "a b b c"),
    ("central_angle_60", "o = free o; a = lconst a o 1; b = s_angle a o b 60o, on_circle b o a", "o a a b"),
    ("tangent_chord", "o a = segment o a; b = on_circle b o a; x = lc_tangent x a o", "x a a b"),
    ("circum_isosceles_bridge", "a b c = triangle a b c; o = circle o a b c; d = on_circum d a b c", "a o o b"),
    ("thales_semicircle", "a b = segment a b; o = midpoint o a b; c = on_circle c o a", "a c c b"),
    ("inscribed_same_arc", "a b = segment a b; c = s_angle a b c 50o; o = circle o a b c; d = on_circum d a b c", "a d d c"),
]


def angle_between_4_points(a, b, c, d) -> float:
    """Directed line-to-line angle mod pi, matching newclid's convention."""
    v1 = b - a
    v2 = d - c
    return (np.arctan2(v2[1], v2[0]) - np.arctan2(v1[1], v1[0])) % np.pi


def measure(construction: str, pts: str, seed: int = 42) -> tuple[Fraction | None, str]:
    """Read the angle off the reference diagram and snap it to a rational multiple of pi."""
    # Build goal-free: JGEXProblemBuilder.build() retries until every stated goal holds
    # numerically, so passing a placeholder goal would make it spin and fail. Goal-free is
    # also the saturation setup S3 needs.
    rng = np.random.default_rng(seed)
    setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(construction).build()
    coords = {p.name: np.array([float(p.num.x), float(p.num.y)]) for p in setup.points}
    names = pts.split()
    a, b, c, d = (coords[n] for n in names)
    ang = angle_between_4_points(a, b, c, d)
    if abs(ang - np.pi) < 1e-9:
        ang = 0.0
    try:
        frac = get_quotient(ang / np.pi)
    except Exception as exc:
        return None, f"not a nice rational: {type(exc).__name__}"
    return frac, f"{float(ang) * 180 / np.pi:.4f} deg"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    print("S1b — numeric-propose / symbolic-verify probe\n")
    header = f"{'case':28s} {'measured':>12s} {'as fraction':>12s} {'py':>4s} {'yu':>4s}"
    print(header)
    print("-" * len(header))

    for name, construction, pts in CASES:
        frac, note = measure(construction, pts)
        if frac is None:
            print(f"{name[:28]:28s} {note:>12s} {'-':>12s} {'-':>4s} {'-':>4s}")
            results.append({"name": name, "measured": None, "note": note})
            continue

        deg = f"{float(frac) * 180:.1f}o"
        goal = f"aconst {pts} {frac.numerator}pi/{frac.denominator}"
        problem = f"{construction} ? {goal}"

        py = solve_one(name, problem, backend="python")
        yu = solve_one(name, problem, backend="yuclid")
        print(
            f"{name[:28]:28s} {note:>12s} {str(frac):>12s} "
            f"{('Y' if py.solved else 'n'):>4s} {('Y' if yu.solved else 'n'):>4s}"
            + ("" if not yu.error else f"  yuERR {yu.error[:40]}")
        )
        results.append(
            {
                "name": name,
                "goal": goal,
                "measured_deg": deg,
                "fraction_of_pi": str(frac),
                "python_solved": py.solved,
                "python_error": py.error,
                "yuclid_solved": yu.solved,
                "yuclid_error": yu.error,
                "yuclid_run_s": round(yu.t_run, 4),
                "python_run_s": round(py.t_run, 4),
            }
        )

    n_yu = sum(1 for r in results if r.get("yuclid_solved"))
    n_py = sum(1 for r in results if r.get("python_solved"))
    print(f"\nverified by yuclid: {n_yu}/{len(results)} | by pure-python: {n_py}/{len(results)}")
    (OUT_DIR / "s1b_aconst_probe.json").write_text(json.dumps(results, indent=2))
    print(f"wrote {OUT_DIR / 's1b_aconst_probe.json'}")


if __name__ == "__main__":
    main()
