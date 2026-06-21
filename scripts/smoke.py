from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prosthesis_rl.agents import ProsthesisLoop
from tasks import claude, list_tasks


def main() -> None:
    result = ProsthesisLoop().run("examples/adl/reach_1_1.mp4")
    assert isinstance(result.reward, float)
    assert result.attempts
    assert isinstance(claude(), float)
    assert len(list_tasks()) >= 3
    print("smoke ok")


if __name__ == "__main__":
    main()
