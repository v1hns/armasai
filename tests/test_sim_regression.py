from __future__ import annotations

from prosthesis_rl.contracts import DesignParams, ProblemSpec
from prosthesis_rl.sim.mujoco_env import ProsthesisMujocoEnv


EXPECTED_METRICS = {
    "reach_success": 0.35,
    "energy": 0.08,
    "rom_violation": 0.02,
    "self_collision": 0.0,
}


def test_simulator_placeholder_behavior_is_stable() -> None:
    env = ProsthesisMujocoEnv(ProblemSpec(), DesignParams())

    assert env.reset() == {"time": 0.0}
    assert env.rollout({"ik_weight": 1.0}) == EXPECTED_METRICS
