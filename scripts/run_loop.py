from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prosthesis_rl.agents import ProsthesisLoop


if __name__ == "__main__":
    result = ProsthesisLoop().run("examples/adl/reach_1_1.mp4")
    print(result.to_json(indent=2))
