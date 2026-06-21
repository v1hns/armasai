"""End-to-end morphology candidate comparison — Benji's Phase 2/3 evaluation.

Pipeline:
  perception → RequirementsAgent brief → N candidate DesignParams
  → multi-seed MuJoCo evaluation (10 seeds × 4 targets each)
  → compare() picks winner → rationale_report() printed + saved

Usage:
    python scripts/compare_candidates.py
    python scripts/compare_candidates.py test_vids/clip.mov
    python scripts/compare_candidates.py --n-candidates 3 --n-seeds 10

Output:
    Prints rationale report to stdout.
    Saves JSON evidence to runs/candidates/<timestamp>/report.json
    Saves rationale text to runs/candidates/<timestamp>/rationale.txt
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from prosthesis_rl.agents.design import DesignAgent, EvalResult
from prosthesis_rl.agents.perception import PerceptionAgent
from prosthesis_rl.agents.requirements import RequirementsAgent, problem_deliverables
from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import DesignParams
from prosthesis_rl.sim.verifier import Verifier


def _params_summary(p: DesignParams) -> dict:
    return {
        "upper_arm_len": p.upper_arm_len,
        "forearm_len": p.forearm_len,
        "grip_width": p.grip_width,
        "joint_stiffness": p.joint_stiffness,
        "mount_frame": p.mount_frame,
        "dof": p.dof,
        "joint_names": p.joint_names,
        "elbow_range_deg": list(next(
            (j.range_deg for l in p.links for j in l.joints if j.name == "elbow"),
            (0, 130),
        )),
        "wrist_range_deg": list(next(
            (j.range_deg for l in p.links for j in l.joints if j.name == "wrist"),
            (-60, 60),
        )),
    }


def run_comparison(
    clip: str,
    n_candidates: int = 3,
    n_seeds: int = 10,
    n_targets: int = 4,
    seconds: float = 3.0,
    out_dir: Path | None = None,
) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_dir or Path("runs/candidates") / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Perception ─────────────────────────────────────────────────────────
    print(f"\n[1/5] Perception: {clip}")
    perception = PerceptionAgent()
    problem = perception.infer_problem(clip)
    deliverables = problem_deliverables(problem)
    print(f"      action={problem.primary_action!r}  side={problem.affected_side}")

    # ── 2. Requirements brief ─────────────────────────────────────────────────
    print("[2/5] Requirements agent ...")
    req_agent = RequirementsAgent()
    brief = req_agent.derive(problem)
    print(f"      source={brief.get('source', '?')}  rationale={brief.get('rationale', '')[:60]}")

    # ── 3. Candidate generation ───────────────────────────────────────────────
    print(f"[3/5] Generating {n_candidates} candidates ...")
    design_agent = DesignAgent()
    candidates = design_agent.propose_candidates(problem, brief=brief, n=n_candidates)
    for i, (params, _) in enumerate(candidates):
        reach = sum(l.length for l in params.links)
        elbow_hi = next(
            (j.range_deg[1] for l in params.links for j in l.joints if j.name == "elbow"), 0.0
        )
        print(
            f"      [{i}] upper={params.upper_arm_len:.2f}m  "
            f"fore={params.forearm_len:.2f}m  "
            f"reach={reach:.2f}m  elbow_hi={elbow_hi:.0f}°  "
            f"DoF={params.dof}"
        )

    # ── 4. Validation gates ───────────────────────────────────────────────────
    print("[4/5] Validation gates ...")
    for i, (params, _) in enumerate(candidates):
        errors = design_agent.validate(params, task_reach_m=0.5)
        if errors:
            print(f"      ✗ Candidate {i}: {errors}")
            sys.exit(1)
        print(f"      ✓ Candidate {i} passes all gates")

    # ── 5. Multi-seed evaluation ──────────────────────────────────────────────
    print(f"[5/5] Evaluating {n_candidates} candidates × {n_seeds} seeds × {n_targets} targets ...")
    verifier = Verifier()
    cad = CadBridge()
    eval_results = design_agent.evaluate_candidates(
        candidates, problem, verifier, cad,
        n_seeds=n_seeds, n_targets=n_targets, seconds=seconds,
        task_id=brief.get("task", {}).get("task_id", "reach_v1"),
    )
    for i, er in enumerate(eval_results):
        print(f"      {er.summary_line(str(i))}")

    # ── 6. Compare + rationale ────────────────────────────────────────────────
    params_list = [p for p, _ in candidates]
    best_i, compare_rationale = design_agent.compare(params_list, eval_results)
    report_text = design_agent.rationale_report(
        params_list, eval_results, best_i, compare_rationale,
        action=problem.primary_action,
    )
    print("\n" + report_text)

    # ── 7. Save evidence ──────────────────────────────────────────────────────
    evidence = {
        "timestamp": timestamp,
        "clip": clip,
        "perception": deliverables,
        "requirements_brief": brief,
        "candidates": [_params_summary(p) for p in params_list],
        "eval_results": [dataclasses.asdict(er) for er in eval_results],
        "best_index": best_i,
        "rationale": compare_rationale,
        "n_seeds": n_seeds,
        "n_targets": n_targets,
        "seconds_per_rollout": seconds,
    }
    (out_dir / "report.json").write_text(json.dumps(evidence, indent=2))
    (out_dir / "rationale.txt").write_text(report_text)
    print(f"\nEvidence saved → {out_dir}/")
    return evidence


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare morphology candidates")
    ap.add_argument("clip", nargs="?",
                    default="test_vids/IMG_9847 (1) (1).mov",
                    help="Path to ADL video clip")
    ap.add_argument("--n-candidates", type=int, default=3)
    ap.add_argument("--n-seeds", type=int, default=10)
    ap.add_argument("--n-targets", type=int, default=4)
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    run_comparison(
        args.clip,
        n_candidates=args.n_candidates,
        n_seeds=args.n_seeds,
        n_targets=args.n_targets,
        seconds=args.seconds,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
