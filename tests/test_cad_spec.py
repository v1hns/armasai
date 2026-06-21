"""Design layer: ProblemSpec -> CadGPT instruction JSON (fallback path)."""

from __future__ import annotations

from prosthesis_rl.agents.cad_spec import DesignSpecLayer, SCHEMA
from prosthesis_rl.agents.requirements import RequirementsAgent
from prosthesis_rl.contracts import Constraints, ProblemSpec


def _spec() -> ProblemSpec:
    return ProblemSpec(
        tasks=[{"id": "grasp_1_1", "name": "Grasp object", "pain_points": ["one-handed"]}],
        constraints=Constraints(rom={"elbow_flexion": 130.0}, grip_capacity=0.4),
        primary_action="unscrewing a bottle cap",
        affected_side="left",
        residual_side="right",
        residual_anthropometrics={"upper_arm_len": 0.33, "forearm_len": 0.29, "hand_length": 0.20, "grip_span": 0.09},
    )


def _offline_layer() -> DesignSpecLayer:
    # Force the deterministic requirements fallback (no network).
    class _Offline(RequirementsAgent):
        @property
        def available(self) -> bool:  # type: ignore[override]
            return False

    return DesignSpecLayer(requirements=_Offline())


def test_instruction_set_is_complete():
    out = _offline_layer().build(_spec())
    assert out["schema"] == SCHEMA
    assert out["mount_frame"] == "torso_left"
    assert out["kinematics"]["dof"] >= 3
    assert out["kinematics"]["links"]
    assert out["rom_metrics"]
    assert out["cad_instructions"]
    assert out["end_effector"]["grip_force_target_n"] > 0


def test_dimensions_mirror_residual_arm():
    out = _offline_layer().build(_spec())
    link_by_name = {l["name"]: l for l in out["kinematics"]["links"]}
    # upper_arm / forearm lengths mirror the intact-arm measurements
    assert abs(link_by_name["upper_arm"]["length_m"] - 0.33) < 1e-6
    assert abs(link_by_name["forearm"]["length_m"] - 0.29) < 1e-6
    assert out["anthropometrics"]["mirrored_from_residual"]["grip_span"] == 0.09


def test_grip_width_capped_by_hand_span():
    out = _offline_layer().build(_spec())
    assert out["end_effector"]["grip_width_m"] <= 0.09  # intact hand grip_span
