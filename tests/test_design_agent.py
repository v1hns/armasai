"""Tests for DesignAgent: validation gates, propose logic, candidate comparison, MJCF output."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from prosthesis_rl.agents.design import (
    ActuatorSpec,
    DesignAgent,
    EvalResult,
    JointSpec,
    LinkSpec,
    MorphologySpec,
)
from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import Constraints, ProblemSpec, RewardBreakdown, SimFeedback


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _good_spec(upper_m: float = 0.30, forearm_m: float = 0.26) -> MorphologySpec:
    return MorphologySpec(
        mount_frame="torso_right",
        links=[
            LinkSpec("upper", upper_m, 0.8),
            LinkSpec("forearm", forearm_m, 0.6),
        ],
        joints=[
            JointSpec("shoulder_flexion", "hinge", (0.0, math.radians(180))),
            JointSpec("elbow_flexion", "hinge", (0.0, math.radians(145))),
        ],
        actuators=[
            ActuatorSpec("shoulder_flexion", 20.0),
            ActuatorSpec("elbow_flexion", 15.0),
        ],
    )


def _problem(reach_m: float = 0.5) -> ProblemSpec:
    return ProblemSpec(constraints=Constraints(rom={"reach_m": reach_m}))


def _low_reward_feedback() -> SimFeedback:
    return SimFeedback(
        reward=0.10,
        breakdown=RewardBreakdown(success=0.1, energy_penalty=0.0, rom_penalty=0.0, collision_penalty=0.0),
    )


def _rom_feedback() -> SimFeedback:
    return SimFeedback(
        reward=0.40,
        breakdown=RewardBreakdown(success=0.5, energy_penalty=0.0, rom_penalty=0.2, collision_penalty=0.0),
    )


# ── validate() ────────────────────────────────────────────────────────────────

def test_validate_rejects_zero_mass():
    agent = DesignAgent()
    spec = _good_spec()
    spec.links[0].mass_kg = 0.0
    errors = agent.validate(spec)
    assert any("non-positive mass" in e for e in errors)


def test_validate_rejects_negative_length():
    agent = DesignAgent()
    spec = _good_spec()
    spec.links[1].length_m = -0.05
    errors = agent.validate(spec)
    assert any("non-positive length" in e for e in errors)


def test_validate_rejects_inverted_joint_limits():
    agent = DesignAgent()
    spec = _good_spec()
    spec.joints[0].limits_rad = (2.0, 1.0)  # lower > upper
    errors = agent.validate(spec)
    assert any("invalid (lower >= upper)" in e for e in errors)


def test_validate_rejects_equal_joint_limits():
    agent = DesignAgent()
    spec = _good_spec()
    spec.joints[1].limits_rad = (1.0, 1.0)
    errors = agent.validate(spec)
    assert any("invalid (lower >= upper)" in e for e in errors)


def test_validate_rejects_invalid_joint_type():
    agent = DesignAgent()
    spec = _good_spec()
    spec.joints[0].type = "slide"
    errors = agent.validate(spec)
    assert any("invalid type" in e for e in errors)


def test_validate_rejects_missing_actuator():
    agent = DesignAgent()
    spec = _good_spec()
    spec.actuators = [ActuatorSpec("shoulder_flexion", 20.0)]  # elbow has no actuator
    errors = agent.validate(spec)
    assert any("no actuator" in e for e in errors)


def test_validate_rejects_unknown_actuator_joint():
    agent = DesignAgent()
    spec = _good_spec()
    spec.actuators.append(ActuatorSpec("phantom_joint", 10.0))
    errors = agent.validate(spec)
    assert any("unknown joint" in e for e in errors)


def test_validate_rejects_zero_torque():
    agent = DesignAgent()
    spec = _good_spec()
    spec.actuators[0].torque_limit_nm = 0.0
    errors = agent.validate(spec)
    assert any("non-positive torque" in e for e in errors)


def test_validate_rejects_insufficient_reach():
    agent = DesignAgent()
    spec = _good_spec(upper_m=0.10, forearm_m=0.10)  # total 0.20 m
    errors = agent.validate(spec, task_reach_m=0.5)
    assert any("< required" in e for e in errors)


def test_validate_passes_good_spec():
    agent = DesignAgent()
    errors = agent.validate(_good_spec(), task_reach_m=0.5)
    assert errors == []


# ── propose() ─────────────────────────────────────────────────────────────────

def test_propose_returns_valid_spec():
    agent = DesignAgent()
    spec, hints = agent.propose(_problem())
    assert agent.validate(spec, task_reach_m=0.5) == []
    assert "ik_weight" in hints


def test_propose_adjusts_forearm_on_low_reward():
    agent = DesignAgent()
    default_spec, _ = agent.propose(_problem())
    low_spec, _ = agent.propose(_problem(), feedback=_low_reward_feedback())
    assert low_spec.links[1].length_m > default_spec.links[1].length_m


def test_propose_widens_joints_on_rom_penalty():
    agent = DesignAgent()
    default_spec, _ = agent.propose(_problem())
    rom_spec, _ = agent.propose(_problem(), feedback=_rom_feedback())
    _, hi_default = default_spec.joints[0].limits_rad
    _, hi_rom = rom_spec.joints[0].limits_rad
    assert hi_rom > hi_default


def test_propose_raises_on_impossible_reach():
    """If the problem requires more reach than any valid limb can provide, raise."""
    agent = DesignAgent()
    # Default limb is ~0.56 m; require 1.5 m — should fail validation
    with pytest.raises(ValueError, match="failed validation"):
        agent.propose(_problem(reach_m=1.5))


# ── propose_candidates() ─────────────────────────────────────────────────────

def test_propose_candidates_returns_n():
    agent = DesignAgent()
    candidates = agent.propose_candidates(_problem(), n=2)
    assert len(candidates) == 2


def test_propose_candidates_all_valid():
    agent = DesignAgent()
    for spec, _ in agent.propose_candidates(_problem(), n=2):
        assert agent.validate(spec, task_reach_m=0.5) == []


# ── compare() ─────────────────────────────────────────────────────────────────

def test_compare_picks_higher_mean_reward():
    agent = DesignAgent()
    candidates = [_good_spec(), _good_spec()]
    results = [
        EvalResult(mean_reward=0.3, success_rate=0.5, collision_rate=0.1),
        EvalResult(mean_reward=0.7, success_rate=0.8, collision_rate=0.05),
    ]
    idx, rationale = agent.compare(candidates, results)
    assert idx == 1
    assert "Candidate 1" in rationale


def test_compare_breaks_tie_on_collision_rate():
    agent = DesignAgent()
    candidates = [_good_spec(), _good_spec()]
    results = [
        EvalResult(mean_reward=0.5, success_rate=0.7, collision_rate=0.2),
        EvalResult(mean_reward=0.5, success_rate=0.7, collision_rate=0.05),
    ]
    idx, _ = agent.compare(candidates, results)
    assert idx == 1


def test_compare_raises_on_length_mismatch():
    agent = DesignAgent()
    with pytest.raises(ValueError):
        agent.compare([_good_spec()], [EvalResult(), EvalResult()])


# ── export_mjcf() ─────────────────────────────────────────────────────────────

def test_export_mjcf_produces_valid_xml(tmp_path: Path):
    spec = _good_spec()
    bridge = CadBridge(output_dir=tmp_path / "stl")
    mjcf_path = bridge.export_mjcf(spec, name="test_arm")
    assert mjcf_path.exists()
    root = ET.parse(str(mjcf_path)).getroot()
    assert root.tag == "mujoco"


def test_export_mjcf_contains_joint_names(tmp_path: Path):
    spec = _good_spec()
    bridge = CadBridge(output_dir=tmp_path / "stl")
    mjcf_path = bridge.export_mjcf(spec, name="test_arm")
    content = mjcf_path.read_text()
    assert "shoulder_flexion" in content
    assert "elbow_flexion" in content


def test_export_mjcf_contains_actuators(tmp_path: Path):
    spec = _good_spec()
    bridge = CadBridge(output_dir=tmp_path / "stl")
    mjcf_path = bridge.export_mjcf(spec, name="test_arm")
    root = ET.parse(str(mjcf_path)).getroot()
    actuator_el = root.find("actuator")
    assert actuator_el is not None
    motors = actuator_el.findall("motor")
    assert len(motors) == 2
