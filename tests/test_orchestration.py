from __future__ import annotations

from pathlib import Path

import pytest

from prosthesis_rl.agents import ProsthesisLoop
from prosthesis_rl.contracts import (
    Constraints,
    DesignParams,
    OrchestrationResult,
    ProblemSpec,
    SimFeedback,
)


class FakePerception:
    def infer_problem(self, clip_path: str | Path) -> ProblemSpec:
        return ProblemSpec(
            tasks=[{"id": "reach_1_1"}],
            constraints=Constraints(grip_capacity=0.4),
        )


class RecordingDesign:
    def __init__(self) -> None:
        self.feedback_seen: list[SimFeedback | None] = []

    def propose(
        self,
        problem: ProblemSpec,
        feedback: SimFeedback | None = None,
        brief=None,
    ) -> tuple[DesignParams, dict[str, float]]:
        del problem, brief
        self.feedback_seen.append(feedback)
        stiffness = 1.0 + 0.1 * (len(self.feedback_seen) - 1)
        return DesignParams(joint_stiffness=stiffness), {"attempt": stiffness}


class FakeCad:
    def export_arm(self, params: DesignParams, name: str = "candidate") -> Path:
        del params
        return Path(f"/tmp/{name}.stl")


class SequencedVerifier:
    def __init__(self, rewards: list[float]) -> None:
        self.rewards = iter(rewards)
        self.feedback: list[SimFeedback] = []

    def evaluate(self, *args, **kwargs) -> SimFeedback:
        result = SimFeedback(reward=next(self.rewards))
        self.feedback.append(result)
        return result


def test_cycle_feeds_feedback_forward_and_selects_best_attempt() -> None:
    design = RecordingDesign()
    verifier = SequencedVerifier([0.2, 0.7, 0.5])
    loop = ProsthesisLoop(
        perception=FakePerception(),
        design=design,
        cad=FakeCad(),
        verifier=verifier,
        max_attempts=3,
    )

    result = loop.run("clip.mp4")

    assert isinstance(result, OrchestrationResult)
    assert [attempt.feedback.reward for attempt in result.attempts] == [0.2, 0.7, 0.5]
    assert design.feedback_seen == [None, verifier.feedback[0], verifier.feedback[1]]
    assert [attempt.design.joint_stiffness for attempt in result.attempts] == pytest.approx(
        [1.0, 1.1, 1.2]
    )
    assert result.best_attempt_index == 1
    assert result.reward == 0.7
    assert result.best_attempt.artifact_path.endswith("candidate_2.stl")


def test_cycle_stops_when_target_reward_is_reached() -> None:
    verifier = SequencedVerifier([0.3, 0.8, 0.9])
    loop = ProsthesisLoop(
        perception=FakePerception(),
        design=RecordingDesign(),
        cad=FakeCad(),
        verifier=verifier,
        max_attempts=3,
        target_reward=0.75,
    )

    result = loop.run("clip.mp4")

    assert len(result.attempts) == 2
    assert result.stop_reason == "target_reward"
    assert result.best_attempt_index == 1


def test_cycle_rejects_invalid_attempt_limit() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        ProsthesisLoop(max_attempts=0)
