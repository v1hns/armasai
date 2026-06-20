from __future__ import annotations

from prosthesis_rl.contracts import RewardBreakdown


def shaped_reward(
    success: float,
    energy: float,
    rom_violation: float,
    collision: float,
) -> RewardBreakdown:
    return RewardBreakdown(
        success=success,
        energy_penalty=energy,
        rom_penalty=rom_violation,
        collision_penalty=collision,
    )

