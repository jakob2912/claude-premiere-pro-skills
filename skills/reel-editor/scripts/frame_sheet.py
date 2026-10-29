#!/usr/bin/env python3
"""Contact sheet from a video: frames in a grid, for checking cuts, text and transitions by eye.
Usage:  python3 <skill-dir>/scripts/frame_sheet.py <video> <out.jpg> [--every 1.0 | --at 1.5,3.2,...] [--from 0] [--to END] [--cols 9] [--w 200]
Order is row by row from top left; the timestamps are written to <out>.txt.
"""
import argparse, subprocess, tempfile, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("out")
ap.add_argument("--every", type=float, default=1.0); ap.add_argument("--at", default="")
ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=None)
ap.add_argument("--cols", type=int, default=9); ap.add_argument("--w", type=int, default=200)
a = ap.parse_args()
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video],
                           capture_output=True, text=True, check=True).stdout)
t1 = min(a.t1 if a.t1 is not None else dur, dur - 0.04)
times = [float(x) for x in a.at.split(",") if x] if a.at else []
if not times:
    t = a.t0
    while t <= t1 + 1e-6:
        times.append(round(t, 3)); t += a.every
h = int(a.w * 16 / 9)
with tempfile.TemporaryDirectory() as d:
    for i, t in enumerate(times):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(t, dur - 0.04):.3f}", "-i", a.video, "-frames:v", "1",
                        "-vf", f"scale={a.w}:{h}", f"{d}/{i:04d}.png"], check=True)
    rows = (len(times) + a.cols - 1) // a.cols
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", f"{d}/%04d.png", "-vf",
                    f"tile={a.cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", a.out], check=True)
pathlib.Path(a.out).with_suffix(".txt").write_text("\n".join(f"{i + 1}: {t:.2f}s" for i, t in enumerate(times)) + "\n")
print(a.out, len(times), "frames")
