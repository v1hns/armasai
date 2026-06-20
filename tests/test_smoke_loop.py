from prosthesis_rl.agents import ProsthesisLoop
from tasks import claude, list_tasks


def test_loop_returns_reward() -> None:
    feedback = ProsthesisLoop().run_once("examples/adl/reach_1_1.mp4")
    assert isinstance(feedback.reward, float)


def test_hud_entrypoint_returns_number() -> None:
    assert isinstance(claude(), float)


def test_task_registry_has_adl_tasks() -> None:
    assert {task["id"] for task in list_tasks()} >= {
        "reach_1_1",
        "grasp_1_1",
        "feeding_1_1",
    }

