"""Isolated CAD AI pipeline test — shows the full output of the CAD agent.

Tests ONLY the CAD stack in isolation:
  perception stub → requirements (fallback) → design → DesignSpecLayer →
  CadAgent.generate() → CadOutput (build sheet + STL + MJCF)

No MuJoCo, no verifier, no multi-seed evaluation — just the CAD generation.

Usage:
    PYTHONPATH=. python scripts/cad_agent_test.py
    PYTHONPATH=. python scripts/cad_agent_test.py test_vids/IMG_9848.MOV
    PYTHONPATH=. python scripts/cad_agent_test.py --all-clips
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from prosthesis_rl.agents.cad_agent import CadAgent
from prosthesis_rl.agents.cad_spec import DesignSpecLayer
from prosthesis_rl.agents.perception import PerceptionAgent
from prosthesis_rl.agents.requirements import RequirementsAgent
from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import DesignParams


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stl_triangle_count(path: Path) -> int:
    """Read triangle count from binary STL header."""
    try:
        data = path.read_bytes()
        if len(data) < 84:
            return 0
        return struct.unpack_from("<I", data, 80)[0]
    except Exception:
        return -1


def _stl_stats(path: Path) -> str:
    count = _stl_triangle_count(path)
    size_kb = path.stat().st_size / 1024
    return f"{count} triangles, {size_kb:.1f} KB"


def _separator(title: str = "", width: int = 64) -> str:
    if title:
        pad = (width - len(title) - 2) // 2
        return "─" * pad + f" {title} " + "─" * (width - pad - len(title) - 2)
    return "─" * width


# ── Core test function ────────────────────────────────────────────────────────

def run_cad_test(clip: str, *, verbose: bool = True) -> dict:
    t0 = time.perf_counter()
    print(f"\n{'='*64}")
    print(f"  CAD AI PIPELINE TEST")
    print(f"  Clip: {clip}")
    print(f"{'='*64}")

    # ── Step 1: Perception ────────────────────────────────────────────────────
    print(f"\n{_separator('1 · PERCEPTION')}")
    perception = PerceptionAgent()
    problem = perception.infer_problem(clip)
    print(f"  Action         : {problem.primary_action}")
    print(f"  Affected side  : {problem.affected_side}")
    print(f"  Residual side  : {problem.residual_side}")
    print(f"  ADL tasks      : {[t.get('id') for t in problem.tasks]}")
    print(f"  Grip capacity  : {problem.constraints.grip_capacity:.2f}")
    print(f"  ROM (deg)      : {dict(problem.constraints.rom)}")
    print(f"  Anthropometrics:")
    for k, v in (problem.residual_anthropometrics or {}).items():
        print(f"      {k:<20}: {v}")

    # ── Step 2: Requirements brief ────────────────────────────────────────────
    print(f"\n{_separator('2 · REQUIREMENTS BRIEF')}")
    req_agent = RequirementsAgent()
    brief = req_agent.derive(problem)
    print(f"  Source         : {brief.get('source')}")
    print(f"  Mount side     : {brief.get('mount_side')}")
    print(f"  Rationale      : {brief.get('rationale')}")
    print(f"  ROM targets (deg):")
    for joint, (lo, hi) in brief.get("rom_targets_deg", {}).items():
        print(f"      {joint:<22}: [{lo:.0f}°, {hi:.0f}°]")
    print(f"  Design params  :")
    for k, v in brief.get("design_params", {}).items():
        print(f"      {k:<22}: {v}")
    print(f"  Actuator torques:")
    for j, t in brief.get("actuator_torque_nm", {}).items():
        print(f"      {j:<22}: {t:.0f} N·m")

    # ── Step 3: DesignSpecLayer (CadGPT instruction JSON) ─────────────────────
    print(f"\n{_separator('3 · CADGPT INSTRUCTION JSON')}")
    spec_layer = DesignSpecLayer()
    instruction = spec_layer.build(problem)
    print(f"  Schema         : {instruction['schema']}")
    print(f"  Mount frame    : {instruction['mount_frame']}")
    print(f"  DoF            : {instruction['kinematics']['dof']}")
    print(f"  Joint order    : {instruction['kinematics']['joint_order']}")
    print(f"  Reach envelope : {instruction['reach_envelope_m']*1000:.0f} mm")
    print(f"  End-effector   : grip_width={instruction['end_effector']['grip_width_m']*1000:.0f}mm  "
          f"force={instruction['end_effector']['grip_force_target_n']:.0f}N")
    print(f"  Links:")
    for lk in instruction["kinematics"]["links"]:
        joints = ", ".join(f"{j['name']}({j['range_deg'][0]:.0f}..{j['range_deg'][1]:.0f}°)" for j in lk["joints"])
        print(f"      {lk['name']:<12}: L={lk['length_m']*1000:.0f}mm  r={lk['radius_m']*1000:.0f}mm  joints=[{joints}]")
    print(f"  ROM metrics:")
    for jname, m in instruction["rom_metrics"].items():
        print(f"      {jname:<22}: span={m['span_deg']:.0f}°  idx={m['dof_index']}")
    print(f"\n  CAD build instructions:")
    for i, step in enumerate(instruction["cad_instructions"], 1):
        print(f"    {i}. {step}")

    if verbose:
        print(f"\n  Full instruction JSON ({len(json.dumps(instruction))} bytes):")
        # Print abbreviated JSON — just top-level keys
        abbrev = {k: ("..." if isinstance(v, (dict, list)) else v) for k, v in instruction.items()}
        print("  " + json.dumps(abbrev, indent=4).replace("\n", "\n  "))

    # ── Step 4: CadAgent.generate() ──────────────────────────────────────────
    print(f"\n{_separator('4 · CAD AGENT GENERATION')}")
    cad_agent = CadAgent()
    print(f"  LLM available  : {cad_agent.available}")

    # Extract DesignParams from the spec layer's internal design call
    from prosthesis_rl.agents.design import DesignAgent
    from prosthesis_rl.agents.requirements import RequirementsAgent as RA
    _ra = RA()
    _brief = _ra.derive(problem)
    _da = DesignAgent()
    params, _ = _da.propose(problem, brief=_brief)

    output = cad_agent.generate(instruction, params, name="cad_test")

    print(f"  Source         : {output.source}")
    print(f"  Material       : {output.material}")
    print(f"  Rationale      :")
    for line in output.rationale.split(". "):
        if line.strip():
            print(f"    • {line.strip().rstrip('.')}.")

    # ── Step 5: Full CadOutput summary ───────────────────────────────────────
    print(f"\n{_separator('5 · CAD OUTPUT')}")
    print(output.summary())

    # ── Step 6: Artifact inspection ───────────────────────────────────────────
    print(f"\n{_separator('6 · ARTIFACT INSPECTION')}")
    mesh_dir = Path(output.mesh_dir)
    mjcf_path = Path(output.mjcf_path)

    print(f"  Mesh directory : {mesh_dir}")
    if mesh_dir.exists():
        stl_files = sorted(mesh_dir.glob("*.stl"))
        print(f"  STL files      : {len(stl_files)} files")
        for stl in stl_files:
            print(f"    ✓ {stl.name:<20} {_stl_stats(stl)}")
    else:
        print(f"  ✗ mesh_dir does not exist: {mesh_dir}")

    print(f"\n  MJCF file      : {mjcf_path}")
    if mjcf_path.exists():
        mjcf_text = mjcf_path.read_text()
        print(f"  ✓ MJCF exists  : {len(mjcf_text)} bytes, {mjcf_text.count('<body')} bodies, "
              f"{mjcf_text.count('<joint')} joints, {mjcf_text.count('<motor')} motors")
        print(f"\n  MJCF content:")
        for line in mjcf_text.splitlines():
            print(f"    {line}")
    else:
        print(f"  ✗ MJCF does not exist: {mjcf_path}")

    # ── Step 7: Build sheet ───────────────────────────────────────────────────
    print(f"\n{_separator('7 · BUILD SHEET')}")
    bs = output.build_sheet
    print(f"  Schema         : {bs.get('schema')}")
    print(f"  Total mass     : {bs.get('total_mass_g'):.1f} g  ({bs.get('total_mass_g', 0)/1000:.3f} kg)")
    print(f"  Printability   : {'✓ OK' if bs.get('printability_ok') else '✗ ISSUES'}")
    print(f"  Reach envelope : {bs.get('reach_envelope_mm'):.0f} mm")
    print(f"  DoF            : {bs.get('kinematics_summary', {}).get('dof')}")
    if bs.get("design_concerns"):
        print(f"  Concerns ({len(bs['design_concerns'])}):")
        for c in bs["design_concerns"]:
            print(f"    ✗ {c}")
    else:
        print(f"  Concerns       : none")
    print(f"\n  Full build sheet JSON ({len(json.dumps(bs))} bytes)")

    # ── Timing ────────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t0
    print(f"\n{'='*64}")
    print(f"  DONE in {elapsed:.2f}s")
    print(f"  Artifacts: {output.mesh_dir}  |  {output.mjcf_path}")
    print(f"{'='*64}\n")

    return {"output": output, "instruction": instruction, "params": params}


# ── Assertions for automated verification ─────────────────────────────────────

def assert_cad_output(result: dict) -> None:
    output = result["output"]
    instruction = result["instruction"]
    params = result["params"]

    # Build sheet completeness
    bs = output.build_sheet
    assert bs["schema"] == "cad-build-sheet/v1", "bad schema"
    assert bs["material"] in {"PA12-CF", "PETG", "PLA"}, f"unknown material: {bs['material']}"
    assert len(bs["links"]) == len(params.links), "link count mismatch"
    assert bs["total_mass_g"] > 0, "zero mass"
    assert bs["reach_envelope_mm"] > 0, "zero reach"

    # Per-link specs
    for lk in output.links:
        assert lk.wall_thickness_mm >= 1.0, f"{lk.name}: wall < 1 mm"
        assert 20 <= lk.infill_pct <= 100, f"{lk.name}: infill out of range"
        assert lk.mass_g > 0, f"{lk.name}: zero mass"

    # STL files
    mesh_dir = Path(output.mesh_dir)
    assert mesh_dir.exists(), f"mesh_dir missing: {mesh_dir}"
    for link in params.links:
        stl = mesh_dir / f"{link.name}.stl"
        assert stl.exists(), f"missing STL: {stl}"
        assert stl.stat().st_size > 200, f"empty STL: {stl}"

    # MJCF
    mjcf = Path(output.mjcf_path)
    assert mjcf.exists(), f"MJCF missing: {mjcf}"
    mjcf_text = mjcf.read_text()
    assert "<mujoco" in mjcf_text, "MJCF missing root element"
    for jname in params.joint_names:
        assert jname in mjcf_text, f"joint {jname!r} missing from MJCF"

    # Instruction JSON roundtrip
    assert instruction["schema"] == "cadgpt-instruction/v1"
    assert instruction["kinematics"]["dof"] == params.dof
    assert instruction["mount_frame"] == params.mount_frame

    print("  ✓ All assertions passed")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Isolated CAD AI pipeline test")
    ap.add_argument("clip", nargs="?",
                    default="test_vids/IMG_9847 (1) (1).mov",
                    help="ADL video clip path")
    ap.add_argument("--all-clips", action="store_true",
                    help="Run against all test_vids clips")
    ap.add_argument("--no-verbose", action="store_true",
                    help="Skip full JSON dump")
    args = ap.parse_args()

    clips = []
    if args.all_clips:
        clips = sorted(Path("test_vids").glob("*"))
        clips = [str(c) for c in clips if c.is_file()]
    else:
        clips = [args.clip]

    all_pass = True
    for clip in clips:
        try:
            result = run_cad_test(clip, verbose=not args.no_verbose)
            print(f"\n{_separator('ASSERTIONS')}")
            assert_cad_output(result)
        except Exception as exc:
            print(f"\n✗ FAILED: {exc}")
            all_pass = False

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
