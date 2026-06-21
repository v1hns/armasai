"""Bench: which (model x prompt) reads the SPECIFIC action correctly.

Side detection is already solved; this targets primary_action. Runs each combo
on both labeled clips via Vertex, temp=0, prints predicted action + side.
"""
from __future__ import annotations
import json, re, sys, time
import prosthesis_rl  # noqa: F401  -> loads .env (Vertex config)
from google import genai
from google.genai import types
from google.genai.types import HttpOptions
from prosthesis_rl.cv.frames import extract_frames

CLIPS = {
    "v1_bottlecap": ("test_vids/IMG_9847 (1) (1).mov", "opening a bottle cap one-handed then picking it up"),
    "v2_tearpaper": ("test_vids/IMG_9848.MOV", "tearing a piece of paper, bracing it against a sill"),
}
MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.5-flash-lite"]

BASE = """You analyze egocentric frames of a person with ONE functional hand (the
other upper limb is absent) attempting an everyday task. Identify the single
SPECIFIC action: the concrete object + the precise verb."""

PROMPTS = {
    "direct": BASE + """
Return ONLY JSON: {"primary_action": "<specific object+verb>", "affected_side": "<left|right>"}""",
    "cot": BASE + """
Think step by step (briefly): (1) what object is in the hand? (2) what is the
hand DOING to it (twisting, tearing, lifting, wiping)? (3) is a surface (table,
sill, body) being used to brace the object in place of the missing hand?
Then return ONLY a final JSON line:
{"primary_action": "<specific object+verb>", "affected_side": "<left|right>"}""",
    "compensation": BASE + """
IMPORTANT: with only one hand, the person often BRACES an object against a
surface (sill, table, lap) to substitute for the missing second hand — so a
hand pressing paper to a sill is likely TEARING or FOLDING it, not wiping.
Name the underlying intended task, not just the surface contact.
Return ONLY JSON: {"primary_action": "<specific object+verb>", "affected_side": "<left|right>"}""",
}

def extract_json(t):
    m = re.findall(r"\{[^{}]*\}", t or "", re.DOTALL)
    for cand in reversed(m):
        try: return json.loads(cand)
        except Exception: pass
    return {}

def run(model, prompt, frames):
    client = genai.Client(http_options=HttpOptions(api_version="v1"))
    parts = [prompt] + [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg") for p in frames]
    cfg = types.GenerateContentConfig(temperature=0.0)
    r = client.models.generate_content(model=model, contents=parts, config=cfg)
    return extract_json(r.text)

def main():
    nframes = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    frames = {k: extract_frames(v[0], n_frames=nframes) for k, v in CLIPS.items()}
    for k, fs in frames.items():
        print(f"[{k}] {len(fs)} frames  | GT: {CLIPS[k][1]}")
    print("=" * 78)
    for model in MODELS:
        for pname, prompt in PROMPTS.items():
            row = f"{model:24} {pname:13}"
            for k, (clip, gt) in CLIPS.items():
                try:
                    t0 = time.time()
                    det = run(model, prompt, frames[k])
                    dt = time.time() - t0
                    act = det.get("primary_action", "?")
                    side = det.get("affected_side", "?")
                    print(f"{row} | {k:12} {dt:4.1f}s side={side:5} | {act}")
                    row = " " * 38
                except Exception as e:
                    print(f"{row} | {k:12} ERROR {type(e).__name__}: {str(e)[:60]}")
                    row = " " * 38
        print("-" * 78)

if __name__ == "__main__":
    main()
