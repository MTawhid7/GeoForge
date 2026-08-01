"""S1 — solve spike.

Runs the spike problem set through Newclid and reports solve rate plus a per-stage time
split (problem build / solver build / deduction run). Optionally repeats with the Yuclid
C++ backend to price the Decision-3b performance question.

Usage:
    uv run python spikes/p0/s1_solve.py                # pure-Python backend
    uv run python spikes/p0/s1_solve.py --compare-yuclid
"""

from __future__ import annotations

import argparse
import json

from common import OUT_DIR, SolveOutcome, iter_problems, solve_one


def fmt_table(rows: list[SolveOutcome]) -> str:
    head = f"{'problem':32s} {'ok':>3s} {'build':>7s} {'solver':>7s} {'run':>8s} {'total':>8s} {'steps':>6s} {'goals':>7s}"
    lines = [head, "-" * len(head)]
    for r in rows:
        goals = f"{r.goals_proved}/{r.goals_total}" if r.goals_total else "-"
        lines.append(
            f"{r.name[:32]:32s} {('Y' if r.solved else 'n'):>3s} "
            f"{r.t_build:7.3f} {r.t_solver_build:7.3f} {r.t_run:8.3f} {r.t_total:8.3f} "
            f"{(r.steps if r.steps is not None else -1):6d} {goals:>7s}"
            + (f"  ERR {r.error[:60]}" if r.error else "")
        )
    return "\n".join(lines)


def summarize(rows: list[SolveOutcome], label: str) -> dict:
    solved = [r for r in rows if r.solved]
    errored = [r for r in rows if r.error]
    t_build = sum(r.t_build for r in rows)
    t_solver = sum(r.t_solver_build for r in rows)
    t_run = sum(r.t_run for r in rows)
    total = t_build + t_solver + t_run
    return {
        "backend": label,
        "n_problems": len(rows),
        "n_solved": len(solved),
        "solve_rate": round(len(solved) / len(rows), 3) if rows else 0.0,
        "n_errored": len(errored),
        "wall_total_s": round(total, 3),
        "wall_median_s": round(sorted(r.t_total for r in rows)[len(rows) // 2], 4)
        if rows
        else 0.0,
        "wall_max_s": round(max((r.t_total for r in rows), default=0.0), 3),
        "time_split_pct": {
            "problem_build": round(100 * t_build / total, 1) if total else 0,
            "solver_build": round(100 * t_solver / total, 1) if total else 0,
            "deduction_run": round(100 * t_run / total, 1) if total else 0,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--compare-yuclid", action="store_true")
    ap.add_argument("--only", type=str, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    problems = list(iter_problems(args.only))
    print(f"S1 solve spike — {len(problems)} problems, seed={args.seed}\n")

    report: dict = {"seed": args.seed, "runs": {}}

    py_rows = [solve_one(n, t, seed=args.seed, backend="python") for n, t in problems]
    print("=== backend: pure-Python (DDARN + SympyAR) ===")
    print(fmt_table(py_rows))
    py_sum = summarize(py_rows, "python")
    print("\n" + json.dumps(py_sum, indent=2))
    report["runs"]["python"] = {"summary": py_sum, "rows": [r.row() for r in py_rows]}

    if args.compare_yuclid:
        yu_rows = [solve_one(n, t, seed=args.seed, backend="yuclid") for n, t in problems]
        print("\n\n=== backend: Yuclid (C++) ===")
        print(fmt_table(yu_rows))
        yu_sum = summarize(yu_rows, "yuclid")
        print("\n" + json.dumps(yu_sum, indent=2))
        report["runs"]["yuclid"] = {"summary": yu_sum, "rows": [r.row() for r in yu_rows]}

        print("\n=== per-problem comparison (python vs yuclid) ===")
        by_name = {r.name: r for r in yu_rows}
        print(f"{'problem':32s} {'py_ok':>6s} {'yu_ok':>6s} {'py_s':>8s} {'yu_s':>8s} {'speedup':>8s}")
        for r in py_rows:
            y = by_name[r.name]
            sp = (r.t_run / y.t_run) if y.t_run > 0 else float("nan")
            print(
                f"{r.name[:32]:32s} {('Y' if r.solved else 'n'):>6s} {('Y' if y.solved else 'n'):>6s} "
                f"{r.t_run:8.3f} {y.t_run:8.3f} {sp:8.2f}x"
            )

    out_file = OUT_DIR / "s1_results.json"
    out_file.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out_file}")


if __name__ == "__main__":
    main()
