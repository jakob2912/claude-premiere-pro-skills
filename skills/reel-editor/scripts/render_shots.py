#!/usr/bin/env python3
"""Renders the shots of a brand film from a cut list (edit.json) as individual clips.
Usage:  .venv/bin/python <skill-dir>/scripts/render_shots.py graphics/<film>/A/edit.json [shot-id ...]
Per shot: excerpt from the iPhone original (HLG) -> speed (slow motion/time-lapse) -> push-in on the 4K plane
-> 1080x1920 -> HDR->SDR LUT with grade -> fine grain -> ProRes 422 HQ with handles before and after the cut.
Output: <edit-folder>/shots/<nr>-<id>.mov and shots.json (handles, start times in the film) for overlay, master and Premiere.
"""
import sys, json, pathlib, subprocess, os
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path.cwd()  # run from the project folder
edit_path = ROOT / sys.argv[1]
only = set(sys.argv[2:])
E = json.loads(edit_path.read_text())
base = edit_path.parent
FPS, W, H = E["fps"], E["width"], E["height"]
HANDLE = E.get("handle", 0.5)
footage = pathlib.Path(os.path.expanduser(E["footage_dir"]))
lut = ROOT / E["lut"]
(base / "shots").mkdir(exist_ok=True)


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout)


def plan():
    t, out = 0.0, []
    for i, s in enumerate(E["shots"]):
        src = footage / f'{s["src"]}.MOV'
        sp = s.get("speed", 1.0)
        src_len = duration(src)
        head = min(HANDLE, s["in"] / sp)
        tail = max(0.0, min(HANDLE, (src_len - 0.05 - (s["in"] + s["dur"] * sp)) / sp))
        out.append({**s, "nr": i + 1, "file": f'shots/{i + 1:02d}-{s["id"]}.mov', "start": round(t, 4),
                    "end": round(t + s["dur"], 4), "head": round(head, 4), "tail": round(tail, 4), "src_path": str(src)})
        t += s["dur"]
    # extra shots: rendered but not placed on V1 (e.g. the second half of a split screen)
    for j, s in enumerate(E.get("extras", [])):
        src = footage / f'{s["src"]}.MOV'
        sp = s.get("speed", 1.0)
        head = min(HANDLE, s["in"] / sp)
        tail = max(0.0, min(HANDLE, (duration(src) - 0.05 - (s["in"] + s["dur"] * sp)) / sp))
        out.append({**s, "nr": 100 + j, "extra": True, "file": f'shots/x{j + 1:02d}-{s["id"]}.mov', "start": None, "end": None,
                    "head": round(head, 4), "tail": round(tail, 4), "src_path": str(src)})
    return out, t


def render(s):
    sp = s.get("speed", 1.0)
    z0, z1 = s.get("zoom", [1.0, 1.0])
    fx, fy = s.get("anchor", [0.5, 0.5])
    head, tail, dur = s["head"], s["tail"], s["dur"]
    s0 = s["in"] - head * sp
    length = (head + dur + tail) * sp
    zexpr = f"max(1,{z0}+({z1}-{z0})*((on/{FPS})-{head})/{dur})"
    vf = [f"setpts=(PTS-STARTPTS)/{sp}"]
    if s.get("blur"):  # motion blur for time-lapse
        vf.append("tmix=frames=3")
    vf += [f"fps={FPS}",
           f"zoompan=z='{zexpr}':x='{fx}*(iw-iw/zoom)':y='{fy}*(ih-ih/zoom)':d=1:s={W}x{H}:fps={FPS}",
           "scale=in_color_matrix=bt2020:in_range=tv,format=gbrpf32le",
           f"lut3d={ROOT / s['lut'] if s.get('lut') else lut}:interp=tetrahedral"]  # custom LUT per shot (e.g. brighter)
    g = s.get("eq")  # fine correction per shot, e.g. {"gamma": 0.95, "saturation": 1.05}
    if g:
        vf.append("eq=" + ":".join(f"{k}={v}" for k, v in g.items()))
    vf += ["scale=out_color_matrix=bt709:out_range=tv,format=yuv422p10le", "noise=alls=3:allf=t"]
    out = base / s["file"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.4f}", "-t", f"{length + 0.1:.4f}", "-i", s["src_path"],
           "-an", "-vf", ",".join(vf), "-frames:v", str(round((head + dur + tail) * FPS)),
           "-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(out)]
    subprocess.run(cmd, check=True)
    return s["file"]


shots, total = plan()
todo = [s for s in shots if not only or s["id"] in only]
with ThreadPoolExecutor(max_workers=4) as ex:
    for f in ex.map(render, todo):
        print("done:", f, flush=True)
keys = ("nr", "id", "file", "start", "end", "head", "tail", "dur", "src", "in")
manifest = {"fps": FPS, "width": W, "height": H, "shots_end": round(total, 4),
            "shots": [{k: s[k] for k in keys} | {"speed": s.get("speed", 1.0)} for s in shots if not s.get("extra")],
            "extras": [{k: s[k] for k in keys} | {"speed": s.get("speed", 1.0)} for s in shots if s.get("extra")]}
(base / "shots.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
print(f"{len(todo)} shots rendered, picture part {total:.2f}s -> {(base / 'shots.json').relative_to(ROOT)}")
