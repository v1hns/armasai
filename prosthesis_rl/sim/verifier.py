from __future__ import annotations

from pathlib import Path

from prosthesis_rl.contracts import DesignParams, ProblemSpec, RewardBreakdown, SimFeedback
from prosthesis_rl.sim.mujoco_env import ProsthesisMujocoEnv


class Verifier:
    """Deterministic grading entrypoint called by the design loop."""

    def evaluate(
        self,
        problem: ProblemSpec,
        design: DesignParams,
        control_hints: dict[str, float],
        stl_path: Path | None = None,
    ) -> SimFeedback:
        del stl_path
        env = ProsthesisMujocoEnv(problem, design)
        env.reset()
        metrics = env.rollout(control_hints)

        breakdown = RewardBreakdown(
            success=metrics["reach_success"],
            energy_penalty=metrics["energy"],
            rom_penalty=metrics["rom_violation"],
            collision_penalty=metrics["self_collision"],
        )
        return SimFeedback(
            reward=breakdown.scalar,
            breakdown=breakdown,
            metrics=metrics,
            notes=["stub verifier; replace rollout with MuJoCo task scenes"],
        )

