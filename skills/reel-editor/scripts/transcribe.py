#!/usr/bin/env python3
"""Transcribes a video or voice memo with word timestamps (mlx-whisper, Apple Silicon).
Usage:  .venv/bin/python <skill-dir>/scripts/transcribe.py raw/clip.mov [--lang en|de|...]
Output: transcripts/<name>.json (segments + words), .srt, .txt (readable, with pause markers)
"""
import sys, json, argparse, pathlib
import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo"

def ts(t, srt=False):
    h, m = int(t // 3600), int(t % 3600 // 60); s = t % 60
    return f"{h:02}:{m:02}:{s:06.3f}".replace(".", ",") if srt else f"{m:02}:{s:05.2f}"

ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--lang", default=None, help="e.g. en, de (default: auto-detect)")
a = ap.parse_args()
src = pathlib.Path(a.video).resolve()
out = pathlib.Path.cwd() / "transcripts"; out.mkdir(exist_ok=True)
print(f"Transcribing {src.name} … (the first run downloads the model, ~1.6 GB)")
# condition_on_previous_text=False: with several takes of the same sentence Whisper otherwise drifts
# (skips whole takes, shuffles the order)
r = mlx_whisper.transcribe(str(src), path_or_hf_repo=MODEL, language=a.lang, word_timestamps=True,
                           condition_on_previous_text=False,
                           # a short prompt with fillers keeps "um"/"ähm" in the transcript so they can be cut;
                           # append your own names and jargon so Whisper spells them right
                           initial_prompt={"de": "Ähm, also, ja.", "en": "Um, so, yeah."}.get(a.lang))
segs = [{"id": i, "start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip(),
         "words": [{"w": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3),
                    "p": round(w.get("probability", 1), 2)} for w in s.get("words", [])]}
        for i, s in enumerate(r["segments"])]
stem = src.stem
(out / f"{stem}.json").write_text(json.dumps({"source": str(src), "segments": segs}, ensure_ascii=False, indent=1))
with open(out / f"{stem}.srt", "w") as f:
    for i, s in enumerate(segs, 1):
        f.write(f"{i}\n{ts(s['start'],True)} --> {ts(s['end'],True)}\n{s['text']}\n\n")
with open(out / f"{stem}.txt", "w") as f:
    prev = 0.0
    for s in segs:
        gap = s["start"] - prev
        if gap > 0.7: f.write(f"   … pause {gap:.1f}s\n")
        f.write(f"[{ts(s['start'])}–{ts(s['end'])}] #{s['id']} {s['text']}\n"); prev = s["end"]
print(f"Done: transcripts/{stem}.json / .srt / .txt  ({len(segs)} segments, duration {segs[-1]['end']:.0f}s)")
