"""Sample frames from an ADL clip for downstream vision analysis.

Uses ffmpeg (available on most machines) to grab N evenly-spaced frames. Falls
back gracefully: if the clip is missing or ffmpeg is unavailable, returns an
empty list so callers can degrade to a stub rather than crash the loop.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _duration_s(clip_path: Path) -> float | None:
    """Clip duration in seconds via ffprobe, or None if unavailable."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path),
            ],
            check=True, capture_output=True, timeout=30, text=True,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
        return None


def extract_frames(clip_path: str | Path, n_frames: int = 6, out_dir: str | Path | None = None) -> list[Path]:
    """Return up to ``n_frames`` evenly-spaced frame images from ``clip_path``.

    If ``clip_path`` is itself an image, it is returned as a single frame. If the
    clip cannot be read (missing file, no ffmpeg, decode error), returns ``[]``.
    """

    clip_path = Path(clip_path)
    if not clip_path.exists():
        return []

    if clip_path.suffix.lower() in _IMAGE_SUFFIXES:
        return [clip_path]

    if not _has_ffmpeg():
        return []

    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="adl_frames_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%03d.jpg"

    # Sample n_frames evenly across the WHOLE clip: fps = n_frames / duration so
    # short clips still yield the full budget. Fall back to a fixed rate if we
    # can't read the duration.
    duration = _duration_s(clip_path)
    if duration and duration > 0:
        fps = max(n_frames / duration, 0.1)
        vf = f"fps={fps:.4f}"
    else:
        vf = "thumbnail,fps=1/2"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(clip_path),
        "-vf",
        vf,
        "-frames:v",
        str(n_frames),
        "-y",
        str(pattern),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []

    frames = sorted(p for p in out_dir.glob("frame_*.jpg"))
    return frames[:n_frames]
