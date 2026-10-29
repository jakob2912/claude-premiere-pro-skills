#!/usr/bin/env python3
"""Builds the remaining parts of a brand film (no dialog) from edit.json + shots.json.
Usage:  .venv/bin/python <skill-dir>/scripts/build_imagefilm.py graphics/<film>/A/edit.json js|audio|master|xml
  js      -> <dir>/edit.js (window.EDIT) for the HyperFrames compositions (transitions, texts)
  audio   -> <dir>/audio/mix.wav (master audio, -14 LUFS, limited) + music.wav/sfx.wav (stems, same gain)
  master  -> exports/<film>/<name>.mp4: shots (V1) + transitions.mov (V2) + texts.mov (V3) + mix.wav
  xml     -> <dir>/<name>.xml (FCP7) for the Premiere import, same tracks as the master
Composition renders: <dir>/renders/transitions.mov and texts.mov (ProRes 4444 with alpha).
"""
import sys, json, pathlib, subprocess, urllib.parse
import numpy as np
from xml.sax.saxutils import escape

ROOT = pathlib.Path.cwd()  # run from the project folder
edit_path = ROOT / sys.argv[1]
cmd = sys.argv[2]
D = edit_path.parent
E = json.loads(edit_path.read_text())
M = json.loads((D / "shots.json").read_text())
FPS, W, H = E["fps"], E["width"], E["height"]
SR = 48000
fr = lambda s: int(round(s * FPS))
shots = M["shots"]
shots_end = sum(fr(s["dur"]) for s in shots) / FPS
total = round(shots_end + E.get("endcard_dur", 0), 4)
name = E["name"]


def starts():
    t = 0
    for s in shots:
        s["f0"], s["f1"] = t, t + fr(s["dur"])
        t = s["f1"]


starts()


def write_js():
    tr = []
    for x in E.get("transitions", []):
        i = x["cut"] - 1
        a = shots[i]
        b = shots[i + 1] if i + 1 < len(shots) else None
        tr.append({"type": x["type"], "dur": x["dur"], "cut": a["f1"] / FPS,
                   "a": {"file": a["file"], "media": a["head"] + a["dur"]},
                   "b": ({"file": b["file"], "media": b["head"]} if b else None)})
    data = {"name": name, "fps": FPS, "total": total, "shots_end": shots_end, "beat": E.get("beat"),
            "shots": [{"id": s["id"], "file": s["file"], "start": s["f0"] / FPS, "end": s["f1"] / FPS,
                       "head": s["head"], "tail": s["tail"]} for s in shots],
            "transitions": tr,
            "extras": {x["id"]: {"file": x["file"], "head": x["head"]} for x in M.get("extras", [])},
            "scenes": E.get("scenes", [])}
    (D / "edit.js").write_text("window.EDIT = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"edit.js: {len(shots)} shots, {len(tr)} transitions, total {total:.2f}s")


def decode(path, start=0.0, dur=None):
    a = ["ffmpeg", "-v", "error", "-ss", str(start)]
    if dur:
        a += ["-t", str(dur)]
    a += ["-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, np.float32).reshape(-1, 2).copy()


def peak_time(x):
    hop = 256
    r = np.sqrt(np.convolve((x ** 2).mean(1), np.ones(hop) / hop, "same"))
    return float(np.argmax(r)) / SR


def write_wav(path, x):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_s24le", str(path)],
                   input=x.astype(np.float32).tobytes(), check=True)


def build_audio():
    n = int(round(total * SR))
    mu = E["music"]
    if "segments" in mu:  # music edit: song sections [from, to] back to back, 10 ms crossfade at the bar lines
        parts, xf = [decode(ROOT / mu["file"], a, b - a) for a, b in mu["segments"]], int(0.01 * SR)
        music = parts[0]
        for p in parts[1:]:
            ramp = np.linspace(0, 1, xf)[:, None]
            music = np.concatenate([music[:-xf], music[-xf:] * (1 - ramp) + p[:xf] * ramp, p[xf:]])
        music = music[:n]
    else:
        music = decode(ROOT / mu["file"], mu["offset"], total + 1)[:n]
    music = np.pad(music, ((0, n - len(music)), (0, 0)))
    t = np.arange(n) / SR
    env = np.ones(n)
    fi, fo = mu.get("fade_in", 0.0), mu.get("fade_out", 2.0)
    if fi:
        env *= np.clip(t / fi, 0, 1)
    if "stop" in mu:  # hard music stop (e.g. on the last beat), afterwards only the effects ring out
        env *= np.clip((mu["stop"] - t) / 0.03, 0, 1)
    else:
        env *= np.clip((total - t) / fo, 0, 1) ** 1.5
    if "envelope_db" in mu:  # optional volume curve [[t, dB], ...]
        p = np.array(mu["envelope_db"], float)
        env *= 10 ** (np.interp(t, p[:, 0], p[:, 1]) / 20)
    if "lowpass_until" in mu:  # music muffled (low-pass) until the drop, opens up during the last second before it
        from scipy.signal import butter, sosfilt
        tu = mu["lowpass_until"]
        wet = sosfilt(butter(4, mu.get("lowpass_hz", 600), "low", fs=SR, output="sos"), music, axis=0)
        w = np.clip((tu - t) / mu.get("lowpass_open", 1.0), 0, 1)[:, None]
        music = (wet * w + music * (1 - w)).astype(np.float32)
    music *= (env * 10 ** (mu.get("gain_db", 0) / 20))[:, None]
    sfx = np.zeros((n, 2), np.float32)
    for e in E.get("sfx", []):
        f = ROOT / "sfx" / e["file"]
        x = decode(f if f.suffix else f.with_suffix(".mp3"))
        if "len" in e:
            x = x[: int(e["len"] * SR)]
            x[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))[:, None]
        pk = e.get("peak", peak_time(x))
        s0 = int(round((e["t"] - pk) * SR))
        if s0 < 0:
            x, s0 = x[-s0:], 0
        x = x[: n - s0] * 10 ** (e["gain_db"] / 20)
        sfx[s0:s0 + len(x)] += x
    (D / "audio").mkdir(exist_ok=True)
    mix = music + sfx
    write_wav(D / "audio" / "mix-raw.wav", mix)
    # measure the mix loudness, apply the same gain to both stems (Premiere tracks = master)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(D / "audio" / "mix-raw.wav"), "-af", "loudnorm=I=-14:TP=-1:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    gain = -14 - float(js["input_i"])
    g = 10 ** (gain / 20)
    peak = 20 * np.log10(np.abs(mix).max() * g + 1e-9)
    write_wav(D / "audio" / "music.wav", music * g)
    write_wav(D / "audio" / "sfx.wav", sfx * g)
    # master audio: sum soft-limited to -2 dBFS (true peak after AAC <= -1 dBTP); stems stay unlimited for remixing
    write_wav(D / "audio" / "mix-gain.wav", mix * g)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(D / "audio" / "mix-gain.wav"), "-af",
                    "alimiter=limit=0.74:attack=3:release=80:level=false", "-c:a", "pcm_s24le", str(D / "audio" / "mix.wav")], check=True)
    print(f"Audio: mix {js['input_i']} LUFS -> gain {gain:+.1f} dB, peak before limiter {peak:.1f} dBFS")


def master():
    ins, fc = [], []
    for i, s in enumerate(shots):
        ins += ["-i", str(D / s["file"])]
        a = s["head"]
        fc.append(f"[{i}:v]trim=start_frame={fr(a)}:end_frame={fr(a) + s['f1'] - s['f0']},setpts=PTS-STARTPTS,format=yuv422p10le[s{i}]")
    k = len(shots)
    fc.append("".join(f"[s{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0,tpad=stop_mode=add:stop_duration={total - shots_end + 0.1},"
              f"trim=end_frame={fr(total)},format=yuva444p10le[base]")
    cur = "base"
    for lay in ("transitions", "texts"):
        p = D / "renders" / f"{lay}.mov"
        if p.exists():
            ins += ["-i", str(p)]
            fc.append(f"[{cur}][{k}:v]overlay=0:0:format=auto:eof_action=pass[{lay}]")
            cur, k = lay, k + 1
    ins += ["-i", str(D / "audio" / "mix.wav")]
    fc.append(f"[{k}:a]anull[a]")
    fc.append(f"[{cur}]format=yuv420p[v]")
    out = ROOT / "exports" / D.parent.name / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-b:v", "16M", "-maxrate", "24M", "-bufsize", "32M",
                    "-r", str(FPS), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-c:a", "aac", "-b:a", "320k", "-ar", str(SR), "-movflags", "+faststart", "-t", str(total), str(out)], check=True)
    print(f"Master: {out.relative_to(ROOT)} ({total:.2f}s)")


def xml():
    url = lambda p: "file://" + urllib.parse.quote(str(p))
    files, n = {}, [0]

    def fel(path, kind, dur_f):
        path = pathlib.Path(path)
        if path in files:
            return f'<file id="{files[path]}"/>'
        n[0] += 1
        fid = files[path] = f"file-{n[0]}"
        if kind == "video":
            media = f"<video><samplecharacteristics><width>{W}</width><height>{H}</height></samplecharacteristics></video>"
        else:
            media = f"<audio><samplecharacteristics><samplerate>{SR}</samplerate><depth>24</depth></samplecharacteristics><channelcount>2</channelcount></audio>"
        return (f'<file id="{fid}"><name>{escape(path.name)}</name><pathurl>{url(path)}</pathurl>'
                f"<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><duration>{dur_f}</duration><media>{media}</media></file>")

    def clip(cid, nm, f0, f1, src_in, fe, audio=False, on=True):
        src = "<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>" if audio else ""
        return (f'<clipitem id="{cid}"><name>{escape(nm)}</name><enabled>{"TRUE" if on else "FALSE"}</enabled><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>'
                f"<start>{f0}</start><end>{f1}</end><in>{src_in}</in><out>{src_in + f1 - f0}</out>{fe}{src}</clipitem>")

    tf = fr(total)
    v1 = [clip(f"v1-{s['nr']}", f"{s['nr']:02d} {s['id']}", s["f0"], s["f1"], fr(s["head"]),
               fel(D / s["file"], "video", fr(s["head"] + s["dur"] + s["tail"]))) for s in shots]
    lay = lambda f, nm: [clip(f"{nm}-1", nm, 0, tf, 0, fel(D / "renders" / f, "video", tf))] if (D / "renders" / f).exists() else []
    v2, v3 = lay("transitions.mov", "Transitions + end card"), lay("texts.mov", "Texts")
    a1 = [clip("a1", "Mix (master audio)", 0, tf, 0, fel(D / "audio" / "mix.wav", "audio", tf), True)]
    a2 = [clip("a2", "Music (stem, muted)", 0, tf, 0, fel(D / "audio" / "music.wav", "audio", tf), True, on=False)]
    a3 = [clip("a3", "Sound effects (stem, muted)", 0, tf, 0, fel(D / "audio" / "sfx.wav", "audio", tf), True, on=False)]
    tr = lambda items: "<track>" + "".join(items) + "</track>"
    out = D / f"{name}.xml"
    out.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-1"><name>{escape(E.get('title', E.get('titel', name)))}</name><duration>{tf}</duration>
<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>
<media>
<video><format><samplecharacteristics><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><width>{W}</width><height>{H}</height>
<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>
{tr(v1)}{tr(v2)}{tr(v3)}</video>
<audio><numOutputChannels>2</numOutputChannels>{tr(a1)}{tr(a2)}{tr(a3)}</audio>
</media></sequence></xmeml>
""")
    print(f"XML: {out.relative_to(ROOT)} – {len(v1)} shots, V2 {'yes' if v2 else 'missing'}, V3 {'yes' if v3 else 'missing'}")


{"js": write_js, "audio": build_audio, "master": master, "xml": xml}[cmd]()
