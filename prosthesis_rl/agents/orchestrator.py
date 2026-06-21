from __future__ import annotations

from pathlib import Path
from typing import Any

from prosthesis_rl.agents.design import DesignAgent
from prosthesis_rl.agents.perception import PerceptionAgent
from prosthesis_rl.agents.spec_sheet import format_spec_sheet
from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import OrchestrationAttempt, OrchestrationResult, SimFeedback
from prosthesis_rl.sim.verifier import Verifier


class ProsthesisLoop:
    """Owns the end-to-end loop across perception, design, CAD, and sim."""

    def __init__(
        self,
        perception: PerceptionAgent | None = None,
        design: DesignAgent | None = None,
        cad: CadBridge | None = None,
        verifier: Verifier | None = None,
        emit_spec_sheet: bool = True,
        max_attempts: int = 3,
        target_reward: float | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.perception = perception or PerceptionAgent()
        self.design = design or DesignAgent()
        self.cad = cad or CadBridge()
        self.verifier = verifier or Verifier()
        self.emit_spec_sheet = emit_spec_sheet
        self.max_attempts = max_attempts
        self.target_reward = target_reward

    def run(self, clip_path: str | Path) -> OrchestrationResult:
        problem = self.perception.infer_problem(clip_path)
        spec_sheet = format_spec_sheet(problem)
        if self.emit_spec_sheet:
            print(spec_sheet)

        attempts: list[OrchestrationAttempt] = []
        feedback: SimFeedback | None = None
        stop_reason = "max_attempts"
        for index in range(self.max_attempts):
            params, control_hints = self.design.propose(problem, feedback=feedback)
            mesh_dir = self.cad.export_arm(params, name=f"candidate_{index + 1}")
            feedback = self.verifier.evaluate(
                problem,
                params,
                control_hints,
                mesh_dir=mesh_dir,
            )
            attempts.append(
                OrchestrationAttempt(
                    index=index,
                    design=params,
                    control_hints=dict(control_hints),
                    artifact_path=str(mesh_dir),
                    feedback=feedback,
                )
            )
            if self.target_reward is not None and feedback.reward >= self.target_reward:
                stop_reason = "target_reward"
                break

        best_index = max(
            range(len(attempts)),
            key=lambda attempt_index: attempts[attempt_index].feedback.reward,
        )
        return OrchestrationResult(
            problem=problem,
            attempts=attempts,
            best_attempt_index=best_index,
            stop_reason=stop_reason,
        )

    def run_once(self, clip_path: str | Path) -> OrchestrationResult:
        """Backward-compatible name for a complete orchestration run."""

        return self.run(clip_path)

    def run_optimized(
        self,
        clip_path: str | Path,
        emit=None,
        quick_mode: bool = False,
    ) -> dict[str, Any]:
        """Full iterative CAD↔sim RL feedback loop with SSE streaming.

        Args:
            clip_path: path to ADL video clip
            emit: Emitter instance for SSE streaming (created if None)
            quick_mode: reduce seeds/timesteps for fast demo

        Returns result dict with best_params, stats, trajectory, rl_result.
        """
        from prosthesis_rl.pipeline.events import Emitter
        from prosthesis_rl.pipeline.loop import DesignOptimizationLoop

        emitter = emit or Emitter()
        loop = DesignOptimizationLoop(quick_mode=quick_mode)
        return loop.run(clip_path, emitter)
