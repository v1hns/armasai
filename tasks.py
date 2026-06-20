from __future__ import annotations

from prosthesis_rl.hud.gateway import evaluate_clip


ADL_TASKS = [
    {"id": "reach_1_1", "name": "Reach target"},
    {"id": "grasp_1_1", "name": "Grasp object"},
    {"id": "feeding_1_1", "name": "Feeding motion"},
]


def claude() -> float:
    """HUD eval entrypoint target: hud eval tasks.py claude."""

    return evaluate_clip("examples/adl/reach_1_1.mp4")


def list_tasks() -> list[dict[str, str]]:
    return ADL_TASKS


if __name__ == "__main__":
    print(claude())

