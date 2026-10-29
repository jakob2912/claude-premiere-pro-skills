#!/usr/bin/env python3
"""Renders a pre-ducked music bed: song from an offset, volume envelope (dB, linearly interpolated).
Usage:  .venv/bin/python <skill-dir>/scripts/build_music_bed.py graphics/<reel>/music-plan.json
Envelope: loud only where nobody speaks (edit/end card), ~20 dB quieter under the voice.
"""
import sys, json, pathlib, subprocess
import numpy as np

ROOT = pathlib.Path.cwd()  # run from the project folder
plan = json.loads((ROOT / sys.argv[1]).read_text())
SR = 48000
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(plan["song_offset"]), "-t", str(plan["duration"]), "-i", str(ROOT / plan["song"]),
                      "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2)
t = np.arange(len(x)) / SR
pts = np.array(plan["envelope_db"], dtype=float)
gain = 10 ** (np.interp(t, pts[:, 0], pts[:, 1]) / 20)
y = (x * gain[:, None]).astype(np.float32)
out = ROOT / plan["output"]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_s24le", str(out)],
               input=y.tobytes(), check=True)
print(f"{out.relative_to(ROOT)}: {len(y) / SR:.2f}s, peak {20 * np.log10(np.abs(y).max() + 1e-9):.1f} dBFS")
