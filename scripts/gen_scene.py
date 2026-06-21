#!/usr/bin/env python3
"""Generate a scenario spec (and optionally a Gizmo scene) for a given action.

Reads JSON from stdin:  {"action": "tie a shoe", "bake_gizmo": false}
Emits JSON lines to stdout, one event per line:
  {"type": "status", "stage": "scenario", "task_id": ..., ...}
  {"type": "status", "stage": "gizmo", "cached": true/false, "scene_url": ...}
  {"type": "done", "scenario": {...}, "scene": {...} or null}
  {"type": "error", "message": ...}
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


def main() -> None:
    try:
        raw = sys.stdin.read().strip()
        req = json.loads(raw) if raw else {}
    except Exception as e:
        emit({"type": "error", "message": f"bad stdin JSON: {e}"})
        sys.exit(1)

    action: str = req.get("action", "reach for an object")
    bake_gizmo: bool = bool(req.get("bake_gizmo", False))

    # ── Build a ProblemSpec from the action string ────────────────────────────
    try:
        from prosthesis_rl.contracts import ProblemSpec
        problem = ProblemSpec(primary_action=action)
    except Exception as e:
        emit({"type": "error", "message": f"ProblemSpec error: {e}"})
        sys.exit(1)

    # ── Derive scenario ───────────────────────────────────────────────────────
    try:
        from prosthesis_rl.agents.scenario import ScenarioAgent
        scenario = ScenarioAgent().derive(problem)
        emit({
            "type": "status",
            "stage": "scenario",
            "task_id": scenario.task_id,
            "posture": scenario.posture,
            "source": scenario.source,
            "description": scenario.description,
            "success_condition": scenario.success_condition,
            "waypoints": [
                {"name": w.name, "pos": list(w.pos), "weight": w.weight, "tolerance_m": w.tolerance_m}
                for w in scenario.waypoints
            ],
            "objects": [
                {"name": o.name, "pos": list(o.pos), "prompt": o.prompt,
                 "rgba": list(o.rgba), "fallback_half": list(o.fallback_half)}
                for o in scenario.objects
            ],
        })
    except Exception as e:
        emit({"type": "error", "message": f"ScenarioAgent error: {e}"})
        sys.exit(1)

    # ── Optional Gizmo bake ───────────────────────────────────────────────────
    scene_info = None
    if bake_gizmo:
        try:
            from prosthesis_rl.agents.scenario import scene_prompt
            from prosthesis_rl.sim import gizmo_scene as gs

            prompt = scene_prompt(scenario)
            emit({"type": "status", "stage": "gizmo", "stage_name": "submitting", "prompt": prompt})

            def _status_cb(stage_name: str) -> None:
                emit({"type": "status", "stage": "gizmo", "stage_name": stage_name})

            result = gs.bake_scene(prompt, status_cb=_status_cb)
            scene_info = {
                "cached": result.cached,
                "mjcf": str(result.mjcf),
                "files": [str(f) for f in result.files],
            }
            emit({"type": "status", "stage": "gizmo", "stage_name": "ready",
                  "cached": result.cached, "mjcf": str(result.mjcf)})
        except Exception as e:
            emit({"type": "status", "stage": "gizmo", "stage_name": "error",
                  "message": str(e)})

    # ── Done ──────────────────────────────────────────────────────────────────
    emit({
        "type": "done",
        "scenario": {
            "task_id": scenario.task_id,
            "posture": scenario.posture,
            "source": scenario.source,
            "description": scenario.description,
            "success_condition": scenario.success_condition,
            "waypoints": [
                {"name": w.name, "pos": list(w.pos), "weight": w.weight}
                for w in scenario.waypoints
            ],
            "objects": [
                {"name": o.name, "pos": list(o.pos), "prompt": o.prompt,
                 "rgba": list(o.rgba), "fallback_half": list(o.fallback_half)}
                for o in scenario.objects
            ],
        },
        "scene": scene_info,
    })


if __name__ == "__main__":
    main()
