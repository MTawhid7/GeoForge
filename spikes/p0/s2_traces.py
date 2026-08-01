"""S2 — readability spike (THE PHASE 0 GATE).

Dumps structured proof traces for every solvable spike problem and measures how much of each
proof could become player-facing solution text (docs/03 §3.5).

Metrics
  step_mix              steps by JustificationType
  rule_histogram        which engine rules actually fire (sizes the translation whitelist)
  ar_premise_counts     premises per AR deduction vs. our max_ar_chain budget (default 3)
  self_similar_steps    the "isosceles proved via triangle-similar-to-itself" idiom, which is
                        machine-correct but unreadable and must be pattern-collapsed
  translatable_fraction steps that are a rule application (whitelistable) or an in-budget AR step
  vertex_angle_convert  aconst/eqangle facts stated as directed line-angles that need converting
                        to human vertex angles (∠ABC) — the risk found in planning

Usage: uv run python spikes/p0/s2_traces.py [--backend yuclid|python] [--max-ar-chain 3]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from common import OUT_DIR, iter_problems, solve_one

RULE_RE = re.compile(r"^(r\d+)\s+(.*)$")


def classify(pd, max_ar_chain: int) -> dict:
    """Classify each proof step of one ProofData."""
    step_mix: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    ar_premise_counts: list[int] = []
    self_similar = 0
    translatable = 0
    per_step = []

    for i, step in enumerate(pd.proof_steps):
        just = step.justification
        jtype = getattr(just, "dependency_type", None) or getattr(
            just, "justification_type", None
        )
        jtype = str(getattr(jtype, "value", jtype))
        step_mix[jtype] += 1
        n_prem = len(step.applied_on_predicates)
        concl = str(step.proven_predicate.predicate)

        is_translatable = False
        note = ""

        if jtype == "Rule Application":
            rule = getattr(just, "rule", None)
            rname = getattr(rule, "fullname", None) or str(rule)
            rules[rname] += 1
            is_translatable = True  # a rule step is whitelistable by construction
            # Detect the degenerate self-similarity idiom: X ≅ X-reversed
            m = re.search(r"▲(\w+) ≅ ▲(\w+)", concl)
            if m and sorted(m.group(1)) == sorted(m.group(2)):
                self_similar += 1
                note = "self-similar-idiom (needs collapsing)"
        elif jtype == "AR Deduction":
            ar_premise_counts.append(n_prem)
            is_translatable = n_prem <= max_ar_chain
            note = "" if is_translatable else f"AR over budget ({n_prem} > {max_ar_chain})"
        elif jtype in ("Reflexivity", "Line Merge", "Circle Merge", "Direct Consequence"):
            is_translatable = True  # structural/invisible in player text
            note = "structural"

        translatable += int(is_translatable)
        per_step.append(
            {
                "i": i,
                "type": jtype,
                "n_premises": n_prem,
                "conclusion": concl,
                "translatable": is_translatable,
                "note": note,
            }
        )

    n = len(pd.proof_steps)
    return {
        "n_steps": n,
        "step_mix": dict(step_mix),
        "rules": dict(rules),
        "ar_premise_counts": ar_premise_counts,
        "self_similar_steps": self_similar,
        "n_translatable": translatable,
        "translatable_fraction": round(translatable / n, 3) if n else 1.0,
        "fully_translatable": translatable == n,
        "per_step": per_step,
    }


def count_directed_angles(pd) -> dict:
    """Count facts expressed as directed line-to-line angles ∠(XY,ZW).

    These are NOT human vertex angles: ∠(BA,BC)=40° may render as ∠ABC=40° or 140°
    depending on configuration. Every one needs conversion in the translator.
    """
    directed = 0
    total_angle_facts = 0
    for step in pd.proof_steps:
        s = str(step.proven_predicate.predicate)
        if "∠" in s:
            total_angle_facts += 1
            if "∠(" in s:
                directed += 1
    return {"angle_facts": total_angle_facts, "directed_line_angles": directed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="yuclid", choices=["yuclid", "python"])
    ap.add_argument("--max-ar-chain", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trace_dir = OUT_DIR / "traces"
    trace_dir.mkdir(exist_ok=True)

    all_rules: Counter[str] = Counter()
    all_mix: Counter[str] = Counter()
    ar_counts: list[int] = []
    per_problem = []
    self_similar_total = 0
    angle_totals = {"angle_facts": 0, "directed_line_angles": 0}

    print(f"S2 readability spike — backend={args.backend}, max_ar_chain={args.max_ar_chain}\n")
    head = f"{'problem':30s} {'steps':>6s} {'transl':>7s} {'frac':>6s} {'AR>bud':>7s} {'selfsim':>8s}"
    print(head)
    print("-" * len(head))

    for name, txt in iter_problems():
        out = solve_one(name, txt, seed=args.seed, backend=args.backend, collect_proof=True)
        if not out.solved or out.proof_data is None:
            continue
        c = classify(out.proof_data, args.max_ar_chain)
        ang = count_directed_angles(out.proof_data)
        all_rules.update(c["rules"])
        all_mix.update(c["step_mix"])
        ar_counts.extend(c["ar_premise_counts"])
        self_similar_total += c["self_similar_steps"]
        for k in angle_totals:
            angle_totals[k] += ang[k]

        over = sum(1 for x in c["ar_premise_counts"] if x > args.max_ar_chain)
        print(
            f"{name[:30]:30s} {c['n_steps']:6d} {c['n_translatable']:7d} "
            f"{c['translatable_fraction']:6.2f} {over:7d} {c['self_similar_steps']:8d}"
        )

        (trace_dir / f"{name}.json").write_text(out.proof_data.model_dump_json(indent=2))
        (trace_dir / f"{name}.proof.txt").write_text(out.proof_text or "")
        per_problem.append({"name": name, **{k: v for k, v in c.items() if k != "per_step"}, **ang})

    n_probs = len(per_problem)
    fully = sum(1 for p in per_problem if p["fully_translatable"])
    total_steps = sum(p["n_steps"] for p in per_problem)
    total_transl = sum(p["n_translatable"] for p in per_problem)

    summary = {
        "backend": args.backend,
        "max_ar_chain": args.max_ar_chain,
        "n_problems_with_proofs": n_probs,
        "n_fully_translatable": fully,
        "fully_translatable_rate": round(fully / n_probs, 3) if n_probs else 0.0,
        "total_steps": total_steps,
        "total_translatable_steps": total_transl,
        "step_translatable_rate": round(total_transl / total_steps, 3) if total_steps else 0.0,
        "step_mix": dict(all_mix),
        "distinct_rules_fired": len(all_rules),
        "rule_histogram": dict(all_rules.most_common()),
        "ar_premise_distribution": dict(Counter(ar_counts)),
        "ar_steps_over_budget": sum(1 for x in ar_counts if x > args.max_ar_chain),
        "ar_steps_total": len(ar_counts),
        "self_similar_idiom_steps": self_similar_total,
        "angle_facts": angle_totals,
    }

    print("\n" + json.dumps(summary, indent=2))
    (OUT_DIR / "s2_summary.json").write_text(
        json.dumps({"summary": summary, "per_problem": per_problem}, indent=2)
    )
    print(f"\nwrote {OUT_DIR / 's2_summary.json'} and {n_probs} traces to {trace_dir}")

    print("\n=== GATE ===")
    print(f"puzzles whose every step is translatable: {fully}/{n_probs}"
          f" = {summary['fully_translatable_rate']:.0%}  (target >= 80%)")
    print(f"step-level translatable rate: {summary['step_translatable_rate']:.0%}")


if __name__ == "__main__":
    main()
