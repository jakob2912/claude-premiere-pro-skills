#!/usr/bin/env python3
"""Builds the reel timeline (output times, captions) from transcript + cut list.
Usage:  python3 <skill-dir>/scripts/build_reel_timeline.py transcripts/<reel>-cuts.json
Output: graphics/<reel>/timeline.json  (read by the HyperFrames compositions and the XML builder)
"""
import sys, json, pathlib, re

ROOT = pathlib.Path.cwd()  # run from the project folder
cfg = json.loads((ROOT / sys.argv[1]).read_text())
words = [w for s in json.loads((ROOT / cfg["transcript"]).read_text())["segments"] for w in s["words"]]

# Whisper splits hyphenated compounds ("Online", "-Warteschlange") -> join them
merged = []
for w in words:
    if merged and w["w"].startswith("-"):
        merged[-1] = {**merged[-1], "w": merged[-1]["w"] + w["w"], "end": w["end"]}
    else:
        merged.append(dict(w))
fixes = cfg.get("word_fixes", {})  # {"<word start>": "text"} or {"<word start>": {"text", "start", "end"}}
for w in merged:
    f = fixes.get(f'{w["start"]:.2f}')
    if isinstance(f, dict): w.update({k: v for k, v in f.items() if k != "text"}); f = f.get("text", w["w"])
    if f: w["w"] = f

def owner(w):  # Whisper stretches words over pauses -> each word belongs to the clip it overlaps most
    ov = [(min(w["end"], i["out"]) - max(w["start"], i["in"]), i["name"]) for i in cfg["timeline"] if i["type"] == "aroll"]
    best = max(ov)
    return best[1] if best[0] > 0.03 else None

t, clips, caps = 0.0, [], []
for item in cfg["timeline"]:
    if item["type"] == "gap":  # graphics beat without dialog (payoff, end card)
        clips.append({"type": "gap", "name": item["name"], "start": round(t, 3), "end": round(t + item["dur"], 3), "room_from": item.get("room_from")})
        t += item["dur"]; continue
    a, b = item["in"], item["out"]
    clips.append({"type": "aroll", "name": item["name"], "src_in": a, "src_out": b, "gain_db": item.get("gain_db", 0), "fade_out": item.get("fade_out", 0.01),
                  "start": round(t, 3), "end": round(t + b - a, 3), "reason": item.get("reason", item.get("grund", ""))})
    for w in merged:
        if owner(w) == item["name"]:
            s = max(w["start"], a); e = min(w["end"], b)
            # caption_offset: Whisper puts word starts too early -> delay the karaoke by a few frames
            off = cfg.get("caption_offset", 0.0)
            caps.append({"text": w["w"], "start": round(t + s - a + off, 3), "end": round(t + e - a + off, 3), "clip": item["name"]})
    t += b - a

# words to caption blocks (max. 3 words / 22 characters, break at punctuation and pauses)
chunks, cur = [], []
def flush():
    if cur: chunks.append({"start": cur[0]["start"], "end": cur[-1]["end"], "words": list(cur)}); cur.clear()
for w in caps:
    if cur and (len(cur) >= 3 or len(" ".join(x["text"] for x in cur + [w])) > 22 or w["start"] - cur[-1]["end"] > 0.45):
        flush()
    cur.append(w)
    if re.search(r"[.,!?:]$", w["text"]): flush()
flush()
# a block stays caption_hold seconds after its last word (default 0.6), at most until the next block
# and never past the end of its speech clip (otherwise it lands on scene changes/empty frames)
hold = cfg.get("caption_hold", 0.6)
clip_end = {c["name"]: c["end"] for c in clips if c["type"] == "aroll"}
for i, c in enumerate(chunks):
    nxt = chunks[i + 1]["start"] if i + 1 < len(chunks) else c["end"] + 0.4
    lim = max(clip_end[c["words"][-1]["clip"]], c["end"]) if "caption_hold" in cfg else float("inf")
    c["end"] = round(min(nxt, c["end"] + hold, lim), 3)

out = {"fps": 30, "width": 1080, "height": 1920, "duration": round(t, 3), "clips": clips, "captions": chunks}
dst = ROOT / cfg["output"]; dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
dst.with_suffix(".js").write_text("window.REEL = " + json.dumps(out, ensure_ascii=False) + ";\n")  # for HyperFrames (no fetch)
print(f"{dst.relative_to(ROOT)}: {t:.2f}s, {len(clips)} clips, {len(caps)} words, {len(chunks)} caption blocks")
for c in clips: print(f'  {c["start"]:6.2f}-{c["end"]:6.2f}  {c["name"]}')
