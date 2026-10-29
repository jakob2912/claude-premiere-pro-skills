#!/usr/bin/env python3
"""Builds an FCP7 XML sequence for Premiere from timeline.json (a new sequence, nothing is overwritten).
Usage:  python3 <skill-dir>/scripts/build_premiere_xml.py graphics/<reel>/timeline.json graphics/<reel>/sfx-plan.json
"""
import sys, json, pathlib, urllib.parse
from xml.sax.saxutils import escape

ROOT = pathlib.Path.cwd()  # run from the project folder
tl = json.loads((ROOT / sys.argv[1]).read_text())
plan = json.loads((ROOT / sys.argv[2]).read_text())
FPS = tl["fps"]
f = lambda s: int(round(s * FPS))
url = lambda p: "file://" + urllib.parse.quote(str(p))
files, n = {}, [0]

def file_el(path, kind, dur_s, w=None, h=None):
    """Define <file> in full once, then reference it by id."""
    path = pathlib.Path(path)
    if path in files:
        return f'<file id="{files[path]}"/>'
    n[0] += 1; fid = files[path] = f"file-{n[0]}"
    media = ""
    if kind in ("video", "av"):
        media += f"<video><samplecharacteristics><width>{w}</width><height>{h}</height></samplecharacteristics></video>"
    if kind in ("audio", "av"):
        media += "<audio><samplecharacteristics><samplerate>48000</samplerate><depth>16</depth></samplecharacteristics><channelcount>2</channelcount></audio>"
    return (f'<file id="{fid}"><name>{escape(path.name)}</name><pathurl>{url(path)}</pathurl>'
            f"<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><duration>{f(dur_s)}</duration><media>{media}</media></file>")

def clip(cid, name, start, end, src_in, fel, kind="video", gain_db=None):
    lvl = ""
    if gain_db is not None:
        lvl = ("<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid><effectcategory>audiolevels</effectcategory>"
               "<effecttype>audiolevels</effecttype><mediatype>audio</mediatype><parameter><parameterid>level</parameterid>"
               f"<name>Level</name><valuemin>0</valuemin><valuemax>3.98109</valuemax><value>{10 ** (gain_db / 20):.5f}</value></parameter></effect></filter>")
    src = "<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>" if kind == "audio" else ""
    return (f'<clipitem id="{cid}"><name>{escape(name)}</name><enabled>TRUE</enabled><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>'
            f"<start>{f(start)}</start><end>{f(end)}</end><in>{f(src_in)}</in><out>{f(src_in) + f(end) - f(start)}</out>{fel}{src}{lvl}</clipitem>")

track = lambda items: "<track>" + "".join(items) + "</track>"
A = plan.get("aroll"); D = plan["dialog"]; G = ROOT / plan["graphics_dir"]  # without "aroll" = faceless reel (audio only)
v1, a1, v2, v3, sfx, busy = [], [], [], [], [], []
for c in tl["clips"]:
    if c["type"] != "aroll": continue
    if A:
        v1.append(clip(f'v1-{c["name"]}', c["name"], c["start"], c["end"], c["src_in"], file_el(ROOT / A["path"], "video", A["duration"], 1080, 1920)))
    a1.append(clip(f'a1-{c["name"]}', c["name"], c["start"], c["end"], c["src_in"], file_el(ROOT / D["path"], "audio", D["duration"]), "audio", D.get("gain_db", 0)))
for s in plan["scenes"]:
    p = G / s["file"]
    (v3 if s.get("track") == 3 else v2).append(
        clip(f'gfx-{s["name"]}', s["name"], s["start"], s["start"] + s["dur"], 0, file_el(p, "video", s["dur"], 1080, 1920)))
for i, e in enumerate(sorted(plan["sfx"], key=lambda e: e["t"])):  # first free track (effects overlap)
    p = ROOT / "sfx" / e["file"]
    p = p if p.suffix else p.with_suffix(".mp3")  # "whoosh" and "whoosh.mp3" both work
    full = plan["sfx_lengths"][p.stem]  # lengths are keyed by name without extension
    d = e.get("dur", full - e.get("in", 0))
    k = next((j for j, b in enumerate(busy) if b <= e["t"]), len(busy))
    if k == len(busy): busy.append(0); sfx.append([])
    busy[k] = e["t"] + d
    sfx[k].append(clip(f'sfx-{i}', e["file"], e["t"], e["t"] + d, e.get("in", 0), file_el(p, "audio", full), "audio", e["gain_db"]))

beds = [clip(f'bed-{i}', pathlib.Path(b["path"]).name, 0, b["duration"], 0, file_el(ROOT / b["path"], "audio", b["duration"]), "audio", b.get("gain_db", 0))
        for i, b in enumerate(plan.get("beds", []))]  # music bed (ducking is baked into the file)
W, H, dur = tl["width"], tl["height"], tl["duration"]
xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-1"><name>{escape(plan["sequence_name"])}</name><duration>{f(dur)}</duration>
<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>
<media>
<video><format><samplecharacteristics><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><width>{W}</width><height>{H}</height>
<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>
{track(v1)}{track(v2)}{track(v3)}</video>
<audio><numOutputChannels>2</numOutputChannels>{track(a1)}{"".join(track(t) for t in sfx)}{"".join(track([b]) for b in beds)}</audio>
</media></sequence></xmeml>
"""
out = ROOT / plan["output"]
out.write_text(xml)
print(f"{out.relative_to(ROOT)}: {len(v1)} A-roll, {len(v2) + len(v3)} graphics, {len(plan['sfx'])} sound effects, {dur:.2f}s")
