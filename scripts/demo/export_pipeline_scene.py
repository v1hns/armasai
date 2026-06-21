"""Pre-bake default arm STLs + MJCF so the pipeline viewer has an initial scene.

Run once (or whenever the default DesignParams changes):
    PYTHONPATH=. python3 scripts/demo/export_pipeline_scene.py

Writes:
    assets/stl/default/{upper_arm,forearm,gripper}.stl
    assets/mjcf/default.xml
    webdemo/assets/scenes/arm_pipeline.xml    (copy for WASM FS)
    webdemo/assets/scenes/arm_links/          (existing dir, also used by pipeline.html)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from prosthesis_rl.cad.bridge import CadBridge
from prosthesis_rl.contracts import DesignParams
from prosthesis_rl.sim.mjcf_builder import build_mjcf


def main() -> None:
    params = DesignParams()
    bridge = CadBridge()

    print("[export] Exporting default arm STLs…")
    mesh_dir = bridge.export_arm(params, name="default")
    print(f"  → {mesh_dir}")

    print("[export] Exporting default MJCF…")
    mjcf_path = bridge.export_mjcf(params, name="default")
    print(f"  → {mjcf_path}")

    # Also write pipeline-named MJCF for WASM scene selector
    pipeline_xml = REPO / "assets" / "mjcf" / "default_pipeline.xml"
    pipeline_xml.write_text(mjcf_path.read_text())
    print(f"  → {pipeline_xml}")

    # Copy STLs to webdemo/assets/scenes/arm_links/ for WASM FS compatibility
    arm_links_dir = REPO / "webdemo" / "assets" / "scenes" / "arm_links"
    arm_links_dir.mkdir(parents=True, exist_ok=True)
    for stl in Path(mesh_dir).glob("*.stl"):
        dst = arm_links_dir / stl.name
        shutil.copy2(stl, dst)
        print(f"  copied {stl.name} → {dst}")

    # Copy MJCF as arm_pipeline.xml for fallback scene
    pipeline_scene = REPO / "webdemo" / "assets" / "scenes" / "arm_pipeline.xml"
    shutil.copy2(mjcf_path, pipeline_scene)
    print(f"  copied MJCF → {pipeline_scene}")

    print("[export] Done.")


if __name__ == "__main__":
    main()
