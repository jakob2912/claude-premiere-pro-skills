#!/usr/bin/env python3
"""Final mix of a faceless reel: voice per cut list, music bed, sound effects, scenes + captions -> MP4.

Usage:  .venv/bin/python <skill-dir>/scripts/build_voice_reel.py graphics/<reel>/reel.json [audio|video|xml|all]
Inputs (reel.json):
  timeline     graphics/<reel>/timeline.json (from build_reel_timeline.py: aroll clips with src_in/src_out, gaps)
  dialog_src   raw/<name>.m4a
  renders      folder with <scene>.mp4 (opaque) and overlay.mov (ProRes 4444, alpha)
  scenes       scene names in order; their durations add up to the timeline length
  music        optional {song, offset, envelope_db: [[t, dB], ...], pause_boost_db?, min_pause?, quiet_db?}
               envelope as in build_music_bed.py; pause_boost_db lifts the music automatically in speech pauses
  sfx          [{file, at, gain_db, align: "start"|"peak"}]  files from sfx/
  output       exports/<reel>/<name>.mp4
Output: <reel>/audio/{dialog,music,sfx,mix}.wav and the master MP4 (-14 LUFS, true peak -1 dBTP).
  xml: <reel>/<reel>.xml for Premiere (V1 scenes, V2 overlay, A1 mix, A2-A4 voice/music/SFX as muted stems)
"""
import sys, json, pathlib, subprocess, re, urllib.parse
from xml.sax.saxutils import escape
import numpy as np

ROOT = pathlib.Path.cwd()  # run from the project folder
CFG_PATH = ROOT / sys.argv[1]
cfg = json.loads(CFG_PATH.read_text())
STEP = sys.argv[2] if len(sys.argv) > 2 else "all"
tl = json.loads((ROOT / cfg["timeline"]).read_text())
SR = 48000
DUR = tl["duration"]
N = int(round(DUR * SR))
AUD = CFG_PATH.parent / "audio"
AUD.mkdir(exist_ok=True)


def decode(path, start=0.0, dur=None, ch=2):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}"] + (["-t", f"{dur:.3f}"] if dur else []) + \
          ["-i", str(path), "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).reshape(-1, ch)


def write_wav(path, x):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", str(x.shape[1]), "-i", "-",
                    "-c:a", "pcm_s24le", str(path)], input=np.ascontiguousarray(x, np.float32).tobytes(), check=True)


def dialog():
    """Clips back to back per timeline (10 ms fades against clicks), then the voice processing chain."""
    raw = decode(ROOT / cfg["dialog_src"], ch=1)[:, 0]
    out = np.zeros(N, np.float32)
    # if a clip butts against the previous one (cut mid-sentence), crossfade 30 ms of pre-roll from the source instead of
    # a hard butt joint; otherwise only 10 ms fades against clicks
    xf, fade = int(0.03 * SR), int(0.01 * SR)
    prev_end = None
    for c in tl["clips"]:
        if c["type"] != "aroll":
            prev_end = None
            if c.get("room_from") is not None:  # fill the gap with room tone from the raw recording instead of digital silence
                n = int(round((c["end"] - c["start"]) * SR)) + 2 * fade
                rt = raw[int(c["room_from"] * SR):int(c["room_from"] * SR) + n].copy()
                rt[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
                rt[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
                s0 = int(round(c["start"] * SR)) - fade
                out[s0:s0 + len(rt)] += rt[: N - s0]
            continue
        joined = prev_end is not None and abs(c["start"] - prev_end) < 1e-3
        pre = xf if joined else 0
        seg = raw[max(0, int(c["src_in"] * SR) - pre):int(c["src_out"] * SR)].copy()
        seg *= 10 ** (c.get("gain_db", 0) / 20)  # level per clip, e.g. lower a stressed word before a splice
        n_in, n_out = (xf if joined else fade), int(c.get("fade_out", 0.01) * SR)
        seg[:n_in] *= np.linspace(0, 1, n_in, dtype=np.float32)
        seg[-n_out:] *= np.linspace(1, 0, n_out, dtype=np.float32)
        if joined:  # fade out the end of the previous clip over the same 30 ms
            e0 = int(round(c["start"] * SR))
            out[e0 - xf:e0] *= np.linspace(1, 0, xf, dtype=np.float32)
        prev_end = c["end"]
        s0 = int(round(c["start"] * SR)) - pre
        n = min(len(seg), N - s0)
        out[s0:s0 + n] += seg[:n]
    write_wav(AUD / "dialog-raw.wav", out[:, None])
    chain = ("highpass=f=80,afftdn=nf=-30,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3500:t=q:w=1:g=2.5,"
             "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,loudnorm=I=-16:TP=-2:LRA=9")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(AUD / "dialog-raw.wav"), "-af", chain, "-ar", str(SR),
                    "-ac", "2", "-c:a", "pcm_s24le", str(AUD / "dialog.wav")], check=True)
    d = decode(AUD / "dialog.wav")
    return np.pad(d, ((0, max(0, N - len(d))), (0, 0)))[:N]


def music(dialog_voice=None):
    m = cfg.get("music")
    if not m:  # music is optional
        return np.zeros((N, 2), np.float32)
    x = decode(ROOT / m["song"], m.get("offset", 0.0), DUR)
    x = np.pad(x, ((0, max(0, N - len(x))), (0, 0)))[:N]
    pts = np.array(m["envelope_db"], float)
    t = np.arange(N) / SR
    db = np.interp(t, pts[:, 0], pts[:, 1])
    if m.get("pause_boost_db") and dialog_voice is not None:
        # music breathes in speech pauses: where the voice is silent for >= min_pause, lift by pause_boost_db (soft 120 ms ramps)
        hop = SR // 100
        rms = 20 * np.log10(np.sqrt((dialog_voice[: N // hop * hop].reshape(-1, hop) ** 2).mean(1)) + 1e-9)
        quiet = rms < m.get("quiet_db", -45)
        boost = np.zeros(len(quiet))
        i, min_len = 0, int(m.get("min_pause", 0.3) * 100)
        while i < len(quiet):
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if j - i >= min_len:
                boost[i:j] = m["pause_boost_db"]
            i = max(j, i + 1)
        boost = np.convolve(boost, np.ones(12) / 12, "same")
        db = db + np.interp(t, np.arange(len(boost)) / 100, boost)
    return x * (10 ** (db / 20))[:, None]


def sfx():
    y = np.zeros((N, 2), np.float32)
    for e in cfg.get("sfx", []):
        p = ROOT / "sfx" / e["file"]
        x = decode(p if p.suffix else p.with_suffix(".mp3")) * 10 ** (e.get("gain_db", 0) / 20)
        off = 0
        if e.get("align") == "peak":  # put the loudest point (50 ms window) on "at", e.g. the end of a riser
            env = np.convolve(np.abs(x).mean(1), np.ones(2400) / 2400, "same")
            off = int(np.argmax(env))
        s0 = int(round(e["at"] * SR)) - off
        if s0 < 0:
            x, s0 = x[-s0:], 0
        n = min(len(x), N - s0)
        if n > 0:
            y[s0:s0 + n] += x[:n]
    return y


def audio():
    d = dialog()
    m, s = music(d.mean(1)), sfx()
    write_wav(AUD / "mix-raw.wav", d + m + s)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(AUD / "mix-raw.wav"), "-af", "loudnorm=I=-14:TP=-1:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    lin = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
           f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(AUD / "mix-raw.wav"), "-af", lin + ",alimiter=limit=0.89:level=false",
                    "-ar", str(SR), "-c:a", "pcm_s24le", str(AUD / "mix.wav")], check=True)
    g = 10 ** ((-14 - float(js["input_i"])) / 20)  # stems with the same gain for Premiere
    write_wav(AUD / "voice.wav", d * g)
    write_wav(AUD / "music.wav", m * g)
    write_wav(AUD / "sfx.wav", s * g)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(AUD / "mix.wav"), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    print("Mix:", " ".join(r.stderr[r.stderr.rindex("Summary:"):].split())[:220])


def scene_frames():
    """HyperFrames rounds every scene up to whole frames -> frame-exact boundaries from data-duration without drift: [(name, f0, f1)]"""
    rd = ROOT / cfg["renders"]
    out, t, prev = [], 0.0, 0
    for s in cfg["scenes"]:
        html = (rd.parent / "scenes" / s / "index.html").read_text()
        t += float(re.search(r'data-composition-id="[^"]+"[^>]*data-duration="([\d.]+)"', html).group(1))
        b = round(t * 30)
        out.append((s, prev, b))
        prev = b
    return out


def video():
    rd = ROOT / cfg["renders"]
    lines = [f"file '{rd / (s + '.mp4')}'\ninpoint 0\noutpoint {(f1 - f0) / 30:.6f}\n" for s, f0, f1 in scene_frames()]
    lst = rd / "concat.txt"
    lst.write_text("".join(lines))
    out = ROOT / cfg["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    fc = ("[0:v]setpts=PTS-STARTPTS,fps=30[base];[1:v]setpts=PTS-STARTPTS,fps=30,format=yuva444p10le[ov];"
          "[base][ov]overlay=0:0:eof_action=pass,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(rd / cfg.get("overlay", "overlay.mov")),
                    "-i", str(AUD / "mix.wav"), "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", f"{DUR:.3f}", "-movflags", "+faststart", str(out)], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                       capture_output=True, text=True).stdout.strip()
    print(f"{out.relative_to(ROOT)}: {float(d):.2f}s (Timeline {DUR:.2f}s)")


def xml():
    """Premiere sequence as FCP7 XML: scenes one by one on V1, overlay on V2, master mix on A1, muted stems below."""
    rd, FPS, tf = ROOT / cfg["renders"], 30, int(round(DUR * 30))
    url = lambda p: "file://" + urllib.parse.quote(str(p))
    files = {}

    def fel(path, audio=False):
        if path in files:
            return f'<file id="{files[path]}"/>'
        fid = files[path] = f"file-{len(files) + 1}"
        dur = int(round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                                              str(path)], capture_output=True, text=True).stdout) * FPS))
        media = ("<audio><samplecharacteristics><samplerate>48000</samplerate><depth>24</depth></samplecharacteristics><channelcount>2</channelcount></audio>"
                 if audio else "<video><samplecharacteristics><width>1080</width><height>1920</height></samplecharacteristics></video>")
        return (f'<file id="{fid}"><name>{escape(path.name)}</name><pathurl>{url(path)}</pathurl>'
                f"<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><duration>{dur}</duration><media>{media}</media></file>")

    def clip(cid, nm, f0, f1, path, audio=False, on=True):
        src = "<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>" if audio else ""
        return (f'<clipitem id="{cid}"><name>{escape(nm)}</name><enabled>{"TRUE" if on else "FALSE"}</enabled><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>'
                f"<start>{f0}</start><end>{f1}</end><in>0</in><out>{f1 - f0}</out>{fel(path, audio)}{src}</clipitem>")

    tr = lambda items: "<track>" + "".join(items) + "</track>"
    v1 = [clip(f"v1-{s}", s, f0, f1, rd / f"{s}.mp4") for s, f0, f1 in scene_frames()]
    v2 = [clip("v2", "Overlay (captions + texts)", 0, tf, rd / cfg.get("overlay", "overlay.mov"))]
    aud = [("Mix (master audio)", "mix.wav", True), ("Voice (stem, muted)", "voice.wav", False),
           ("Music (stem, muted)", "music.wav", False), ("Sound effects (stem, muted)", "sfx.wav", False)]
    at = [tr([clip(f"a{i}", nm, 0, tf, AUD / fn, True, on)]) for i, (nm, fn, on) in enumerate(aud, 1)]
    out = CFG_PATH.parent / f"{CFG_PATH.parent.name}.xml"
    out.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-1"><name>{escape(cfg.get('title', cfg.get('titel', CFG_PATH.parent.name)))}</name><duration>{tf}</duration>
<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>
<media>
<video><format><samplecharacteristics><rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate><width>1080</width><height>1920</height>
<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>
{tr(v1)}{tr(v2)}</video>
<audio><numOutputChannels>2</numOutputChannels>{"".join(at)}</audio>
</media></sequence></xmeml>
""")
    print(f"XML: {out.relative_to(ROOT)} – {len(v1)} scenes, {tf} frames")


if STEP in ("audio", "all"):
    audio()
if STEP in ("video", "all"):
    video()
if STEP in ("xml", "all"):
    xml()
