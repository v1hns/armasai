from prosthesis_rl.agents import ProsthesisLoop
from prosthesis_rl.contracts import OrchestrationResult
from tasks import claude, list_tasks


def test_loop_returns_inspectable_result() -> None:
    result = ProsthesisLoop().run("examples/adl/reach_1_1.mp4")
    assert isinstance(result, OrchestrationResult)
    assert len(result.attempts) == 3
    assert isinstance(result.reward, float)
    assert result.best_attempt in result.attempts
    assert result.stop_reason == "max_attempts"
    assert '"attempts"' in result.to_json()


def test_hud_entrypoint_returns_number() -> None:
    assert isinstance(claude(), float)


def test_task_registry_has_adl_tasks() -> None:
    assert {task["id"] for task in list_tasks()} >= {
        "reach_1_1",
        "grasp_1_1",
        "feeding_1_1",
    }
