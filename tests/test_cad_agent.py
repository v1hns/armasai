"""Unit tests for CadAgent — isolated CAD AI generation."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from prosthesis_rl.agents.cad_agent import (
    CadAgent,
    CadOutput,
    LinkSpec,
    _MATERIALS,
    _SAFETY_FACTOR,
    _link_mass_g,
    _print_orientation,
    _printability_check,
    _select_material,
    _wall_thickness_mm,
)
from prosthesis_rl.agents.cad_spec import DesignSpecLayer
from prosthesis_rl.agents.design import DesignAgent
from prosthesis_rl.agents.requirements import RequirementsAgent
from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import Constraints, DesignParams, ProblemSpec


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _spec(action: str = "unscrewing a bottle cap", side: str = "left") -> ProblemSpec:
    return ProblemSpec(
        primary_action=action,
        affected_side=side,
        residual_side="right" if side == "left" else "left",
        tasks=[{"id": "grasp_1_1", "name": "Grasp", "pain_points": ["one-handed"]}],
        constraints=Constraints(
            rom={"shoulder_flexion": 110.0, "elbow_flexion": 130.0, "wrist_rotation": 60.0},
            grip_capacity=0.4,
        ),
        residual_anthropometrics={
            "upper_arm_len": 0.32, "forearm_len": 0.28, "hand_length": 0.19, "grip_span": 0.09,
        },
    )


class _OfflineRA(RequirementsAgent):
    """Force the deterministic fallback (no network)."""
    @property
    def available(self) -> bool:
        return False


def _offline_layer() -> DesignSpecLayer:
    return DesignSpecLayer(requirements=_OfflineRA())


def _instruction(action: str = "unscrewing a bottle cap", side: str = "left") -> tuple[dict, DesignParams]:
    prob = _spec(action, side)
    layer = _offline_layer()
    instr = layer.build(prob)
    brief = _OfflineRA().derive(prob)
    params, _ = DesignAgent().propose(prob, brief=brief)
    return instr, params


# ── Engineering formula tests ─────────────────────────────────────────────────

def test_wall_thickness_positive_for_nonzero_torque():
    mat = _MATERIALS["PA12-CF"]
    t = _wall_thickness_mm(15.0, 0.022, mat)
    assert t > 0
    assert t >= mat.min_wall_mm


def test_wall_thickness_clamped_to_material_minimum():
    mat = _MATERIALS["PLA"]
    # Very low torque → still gets the material floor
    t = _wall_thickness_mm(0.001, 0.025, mat)
    assert t == mat.min_wall_mm


def test_wall_thickness_increases_with_torque():
    mat = _MATERIALS["PETG"]
    t_low = _wall_thickness_mm(5.0, 0.025, mat)
    t_high = _wall_thickness_mm(30.0, 0.025, mat)
    assert t_high >= t_low


def test_mass_estimate_positive():
    m = _link_mass_g(0.30, 0.025, 0.002, 0.70, 1020)
    assert m > 0


def test_mass_increases_with_length():
    m1 = _link_mass_g(0.20, 0.025, 0.002, 0.70, 1020)
    m2 = _link_mass_g(0.40, 0.025, 0.002, 0.70, 1020)
    assert m2 > m1


def test_print_orientation_long_link_is_vertical():
    assert _print_orientation("upper_arm", 300.0, 25.0) == "vertical"


def test_print_orientation_gripper_is_horizontal():
    assert _print_orientation("gripper", 60.0, 40.0) == "horizontal"


# ── Material selection tests ──────────────────────────────────────────────────

def test_select_material_high_torque_gives_pa12cf():
    instr = {
        "actuators": [{"joint": "shoulder_flexion", "torque_nm": 25.0}],
        "end_effector": {"grip_force_target_n": 10.0},
    }
    mat = _select_material(instr)
    assert mat.name == "PA12-CF"


def test_select_material_low_load_gives_petg_or_pla():
    instr = {
        "actuators": [{"joint": "wrist", "torque_nm": 3.0}],
        "end_effector": {"grip_force_target_n": 5.0},
    }
    mat = _select_material(instr)
    assert mat.name in {"PLA", "PETG"}


def test_select_material_high_grip_force_gives_pa12cf():
    instr = {
        "actuators": [{"joint": "elbow", "torque_nm": 5.0}],
        "end_effector": {"grip_force_target_n": 20.0},
    }
    mat = _select_material(instr)
    assert mat.name == "PA12-CF"


# ── Printability check tests ──────────────────────────────────────────────────

def test_printability_flags_thin_wall():
    bad_link = LinkSpec("test", 300.0, 25.0, 0.5, 60, "PA12-CF", "vertical", 100.0)
    concerns = _printability_check([bad_link])
    assert any("wall" in c.lower() for c in concerns)


def test_printability_passes_good_link():
    good_link = LinkSpec("upper_arm", 300.0, 25.0, 1.5, 60, "PA12-CF", "vertical", 100.0)
    concerns = _printability_check([good_link])
    assert not any("wall" in c.lower() for c in concerns)


# ── CadAgent.generate() tests ─────────────────────────────────────────────────

def test_generate_returns_cad_output(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert isinstance(out, CadOutput)


def test_generate_material_is_valid(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert out.material in {"PA12-CF", "PETG", "PLA"}


def test_generate_link_count_matches_params(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert len(out.links) == len(params.links)


def test_generate_walls_above_minimum(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    mat = _MATERIALS.get(out.material, _MATERIALS["PA12-CF"])
    for lk in out.links:
        assert lk.wall_thickness_mm >= mat.min_wall_mm - 1e-6, (
            f"{lk.name}: wall {lk.wall_thickness_mm} mm < material floor {mat.min_wall_mm} mm"
        )


def test_generate_mass_is_positive(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert all(lk.mass_g > 0 for lk in out.links)
    assert out.build_sheet["total_mass_g"] > 0


def test_generate_creates_stl_files(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    mesh_dir = Path(out.mesh_dir)
    assert mesh_dir.is_dir()
    for link in params.links:
        stl = mesh_dir / f"{link.name}.stl"
        assert stl.exists(), f"missing STL: {stl}"
        assert stl.stat().st_size > 200, f"empty STL: {stl}"


def test_generate_stl_triangle_count(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    for link in params.links:
        stl_path = Path(out.mesh_dir) / f"{link.name}.stl"
        count = struct.unpack_from("<I", stl_path.read_bytes(), 80)[0]
        assert count > 100, f"{link.name}.stl has only {count} triangles"


def test_generate_creates_valid_mjcf(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    mjcf_text = Path(out.mjcf_path).read_text()
    assert "<mujoco" in mjcf_text
    for jname in params.joint_names:
        assert jname in mjcf_text, f"joint {jname!r} missing from MJCF"


def test_generate_mjcf_joint_count(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    mjcf_text = Path(out.mjcf_path).read_text()
    assert mjcf_text.count("<joint") == params.dof


def test_generate_build_sheet_schema(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    bs = out.build_sheet
    assert bs["schema"] == "cad-build-sheet/v1"
    assert len(bs["links"]) == len(params.links)
    assert bs["reach_envelope_mm"] > 0


def test_generate_build_sheet_is_json_serializable(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    # Must not raise
    serialized = json.dumps(out.build_sheet)
    assert len(serialized) > 100


def test_generate_pa12cf_for_high_torque_action(tmp_path):
    """Shoulder torque 20 N·m should force PA12-CF selection."""
    instr, params = _instruction(action="lifting a heavy pot")
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert out.material == "PA12-CF"


def test_generate_printability_ok_for_standard_design(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert out.printability_ok, f"concerns: {out.design_concerns}"


def test_generate_manufacturing_notes_nonempty(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert len(out.manufacturing_notes) >= 4


def test_generate_left_mount_note_present(tmp_path):
    """Left-side mount should trigger mirror geometry note."""
    instr, params = _instruction(action="unscrewing a bottle cap", side="left")
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    assert any("mirror" in n.lower() or "left" in n.lower() for n in out.manufacturing_notes)


def test_summary_contains_material(tmp_path):
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    out = agent.generate(instr, params, name="test")
    summary = out.summary()
    assert out.material in summary
    assert "BEST" not in summary   # rationale_report marker shouldn't appear here


def test_generate_source_is_rules_without_key(tmp_path):
    """With no API key the source must be 'rules'."""
    instr, params = _instruction()
    agent = CadAgent(cad=CadBridge(output_dir=tmp_path / "stl"))
    assert not agent.available
    out = agent.generate(instr, params, name="test")
    assert out.source == "rules"
