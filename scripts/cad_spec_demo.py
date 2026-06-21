"""Full design layer: clip -> perception -> requirements -> design -> CadGPT JSON.

Usage:
    python scripts/cad_spec_demo.py [path/to/clip]
"""

from __future__ import annotations

import json
import sys

from prosthesis_rl.agents.cad_spec import DesignSpecLayer
from prosthesis_rl.agents.perception import PerceptionAgent


def main() -> None:
    clip = sys.argv[1] if len(sys.argv) > 1 else "test_vids/od_video-1352_singular_display.MOV"
    spec = PerceptionAgent().infer_problem(clip)
    instructions = DesignSpecLayer().build(spec)
    print(json.dumps(instructions, indent=2))


if __name__ == "__main__":
    main()
