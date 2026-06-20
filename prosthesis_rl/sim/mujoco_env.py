from __future__ import annotations

from prosthesis_rl.contracts import DesignParams, ProblemSpec


class ProsthesisMujocoEnv:
    """MuJoCo env placeholder for deterministic ADL grading."""

    def __init__(self, problem: ProblemSpec, design: DesignParams) -> None:
        self.problem = problem
        self.design = design

    def reset(self) -> dict[str, float]:
        return {"time": 0.0}

    def rollout(self, control_hints: dict[str, float]) -> dict[str, float]:
        del control_hints
        return {
            "reach_success": 0.35,
            "energy": 0.08,
            "rom_violation": 0.02,
            "self_collision": 0.0,
        }

