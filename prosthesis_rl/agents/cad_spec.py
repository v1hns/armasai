"""Design layer: ProblemSpec -> precise CadGPT instruction JSON.

This is the stage between perception/requirements and Benji's CadGPT model. It
runs the requirements agent (action -> spec brief) and the design agent (brief
-> DesignParams kinematic chain), then serializes the result into a single,
very specific instruction set CadGPT can build geometry from: per-link
dimensions, per-joint ROM metrics + axes, the end-effector/grip spec, actuator
torques, the mount frame, the reach envelope, and explicit build instructions.

The design agent IS the engine here; this layer just turns its structured
output into the JSON CadGPT consumes.
"""

from __future__ import annotations

import math
from typing import Any

from prosthesis_rl.agents.design import DesignAgent
from prosthesis_rl.agents.requirements import RequirementsAgent, problem_deliverables
from prosthesis_rl.contracts import DesignParams, ProblemSpec

SCHEMA = "cadgpt-instruction/v1"


def _rad(deg: float) -> float:
    return round(math.radians(deg), 4)


def _serialize_links(params: DesignParams) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for link in params.links:
        links.append(
            {
                "name": link.name,
                "length_m": round(float(link.length), 4),
                "radius_m": round(float(link.radius), 4),
                "mesh": link.mesh,
                "color_rgba": list(link.rgba),
                "joints": [
                    {
                        "name": j.name,
                        "type": j.type,
                        "axis": list(j.axis),
                        "range_deg": [round(j.range_deg[0], 1), round(j.range_deg[1], 1)],
                        "range_rad": [_rad(j.range_deg[0]), _rad(j.range_deg[1])],
                    }
                    for j in link.joints
                ],
            }
        )
    return links


def _rom_metrics(params: DesignParams) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for idx, (link, joint) in enumerate(
        (link, j) for link in params.links for j in link.joints
    ):
        lo, hi = joint.range_deg
        metrics[joint.name] = {
            "link": link.name,
            "range_deg": [round(lo, 1), round(hi, 1)],
            "range_rad": [_rad(lo), _rad(hi)],
            "span_deg": round(hi - lo, 1),
            "dof_index": idx,
        }
    return metrics


def _cad_instructions(
    params: DesignParams, brief: dict[str, Any], action: str
) -> list[str]:
    """Explicit, ordered natural-language build steps for CadGPT."""
    steps: list[str] = []
    steps.append(
        f"Mount the prosthesis on frame '{params.mount_frame}' "
        f"({'left' if 'left' in params.mount_frame else 'right'}-side limb)."
    )
    anthro = brief.get("design_params", {}).get("sizing_basis")
    if anthro:
        steps.append(
            "Size all segment lengths and the hand to MIRROR the intact "
            "(contralateral) arm — the prosthesis must match the patient's other side."
        )
    steps.append(
        f"Build a {params.dof}-DoF serial chain of {len(params.links)} links, proximal to distal:"
    )
    for link in params.links:
        jdesc = ", ".join(
            f"{j.name} ({j.type}) {j.range_deg[0]:.0f}..{j.range_deg[1]:.0f}deg about axis {tuple(j.axis)}"
            for j in link.joints
        ) or "fixed"
        steps.append(
            f"  - {link.name}: length {link.length*1000:.0f}mm, radius {link.radius*1000:.0f}mm; "
            f"DoF: {jdesc}."
        )
    dp = brief.get("design_params", {})
    grip_w = dp.get("grip_width", params.grip_width)
    grip_f = dp.get("grip_force_target_n", 15.0)
    steps.append(
        f"Size the end-effector opening to {float(grip_w)*1000:.0f}mm with a target grip "
        f"force of {float(grip_f):.0f} N — tuned to '{action}'."
    )
    torques = brief.get("actuator_torque_nm", {})
    if torques:
        tdesc = ", ".join(f"{j}={t:.0f}N·m" for j, t in torques.items())
        steps.append(f"Provision actuators: {tdesc}.")
    steps.append(
        f"Total reach envelope must be at least {sum(l.length for l in params.links)*1000:.0f}mm."
    )
    return steps


class DesignSpecLayer:
    """Runs requirements + design, emits the CadGPT instruction JSON."""

    def __init__(
        self,
        requirements: RequirementsAgent | None = None,
        design: DesignAgent | None = None,
    ) -> None:
        self.requirements = requirements or RequirementsAgent()
        self.design = design or DesignAgent()

    def build(self, problem: ProblemSpec) -> dict[str, Any]:
        """Return the full CadGPT instruction set as a JSON-serializable dict."""
        brief = self.requirements.derive(problem)
        params, control_hints = self.design.propose(problem, brief=brief)

        action = problem.primary_action or brief.get("task", {}).get("primary_action", "")
        dp = brief.get("design_params", {})

        return {
            "schema": SCHEMA,
            "task": brief.get("task", {}),
            "primary_action": action,
            "mount_frame": params.mount_frame,
            "kinematics": {
                "dof": params.dof,
                "joint_order": params.joint_names,
                "links": _serialize_links(params),
            },
            "rom_metrics": _rom_metrics(params),
            "end_effector": {
                "type": "gripper",
                "grip_width_m": round(float(dp.get("grip_width", params.grip_width)), 4),
                "grip_force_target_n": round(float(dp.get("grip_force_target_n", 15.0)), 1),
                "control_grip_force": round(control_hints.get("grip_force_target", 0.35), 3),
            },
            "actuators": [
                {"joint": j, "torque_nm": round(float(t), 1)}
                for j, t in brief.get("actuator_torque_nm", {}).items()
            ],
            "reach_envelope_m": round(sum(l.length for l in params.links), 4),
            "anthropometrics": {
                "basis": dp.get("sizing_basis", "default"),
                "mirrored_from_residual": problem.residual_anthropometrics,
                "hand_length_m": dp.get("hand_length"),
            },
            "joint_stiffness": round(float(params.joint_stiffness), 3),
            "cad_instructions": _cad_instructions(params, brief, action),
            "rationale": brief.get("rationale", ""),
            "provenance": {
                "deliverables": problem_deliverables(problem),
                "requirements_source": brief.get("source", ""),
            },
        }
