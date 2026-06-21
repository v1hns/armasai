"""Evaluate the perception agent against the labeled ADL dataset.

Runs the Gemma pipeline on every clip in datasets/adl_labels.json and scores it
against ground truth: affected-side accuracy (the load-bearing prediction) and a
side-by-side of predicted vs. ground-truth action (action match is judged by a
human — the model phrasing rarely matches verbatim).

Usage:
    python scripts/eval_dataset.py [path/to/labels.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from prosthesis_rl.cv.frames import extract_frames
from prosthesis_rl.cv.gemma import GemmaVideoAnalyzer


def main() -> None:
    labels_path = Path(sys.argv[1] if len(sys.argv) > 1 else "datasets/adl_labels.json")
    data = json.loads(labels_path.read_text())
    analyzer = GemmaVideoAnalyzer()
    print(f"dataset: {data['name']}  |  gemma available: {analyzer.available}\n")

    side_correct = 0
    total = 0
    for v in data["videos"]:
        clip = v["file"]
        frames = extract_frames(clip, n_frames=8)
        det = analyzer.analyze(frames)
        total += 1
        side_ok = det.get("affected_side") == v["affected_side"]
        side_correct += int(side_ok)

        print(f"── {Path(clip).name}  ({len(frames)} frames)")
        print(f"   affected_side : pred={det.get('affected_side')!r:8} gt={v['affected_side']!r:8} {'✓' if side_ok else '✗'}")
        print(f"   action  pred  : {det.get('primary_action')!r}")
        print(f"   action  gt    : {v['primary_action']!r}")
        print(f"   tasks   pred  : {det.get('tasks')}")
        print(f"   tasks   gt    : {v['tasks']}")
        print()

    print(f"affected_side accuracy: {side_correct}/{total} = {side_correct / total:.0%}")


if __name__ == "__main__":
    main()
