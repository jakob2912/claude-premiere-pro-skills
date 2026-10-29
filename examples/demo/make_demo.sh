#!/bin/zsh
# Renders the demo reel end to end without any footage of your own:
# synthetic voice (macOS `say`) -> transcript -> cut list -> timeline -> HyperFrames scenes -> mix -> MP4 + Premiere XML.
# Usage: zsh examples/demo/make_demo.sh      (PY=/path/to/python overrides the interpreter)
set -e
cd "${0:A:h}"
S=../../skills/reel-editor
[[ "$(uname -s)" == Darwin ]] || { print "The demo needs macOS (say + mlx-whisper). Put your own raw/voice.aiff here to skip say."; [[ -f raw/voice.aiff ]] || exit 1 }
if [[ -z "$PY" ]]; then
  [[ -x .venv/bin/python ]] || { print "Creating .venv (first run: Python packages, then ~1.6 GB Whisper model)"; python3 -m venv .venv && .venv/bin/pip install -q -r $S/requirements.txt }
  PY=.venv/bin/python
fi
hf() { npx -y hyperframes@0.8.114 "$@" }
G=graphics/demo
mkdir -p raw transcripts exports $G/renders $G/assets $G/scenes/overlay

[[ -f raw/voice.aiff ]] || say -v Samantha -o raw/voice.aiff -f script.txt 2>/dev/null || say -o raw/voice.aiff -f script.txt
$PY $S/scripts/transcribe.py raw/voice.aiff --lang en

# one clip from the first to the last word, 80 ms of air on both sides
python3 - <<'PY'
import json
segs = json.load(open("transcripts/voice.json"))["segments"]
w = [x for s in segs for x in s["words"]]
fixes = {f"{x['start']:.2f}": "Premiere" for x in w if x["w"].lower().strip(".,") == "premiere"}
json.dump({"source": "raw/voice.aiff", "transcript": "transcripts/voice.json", "output": "graphics/demo/timeline.json",
           "caption_offset": 0.05, "caption_hold": 0.15, "word_fixes": fixes,
           "timeline": [{"name": "voice", "type": "aroll", "in": max(0, w[0]["start"] - 0.08), "out": w[-1]["end"] + 0.08,
                         "reason": "single synthetic take"},
                        {"name": "endcard", "type": "gap", "dur": 2.0, "reason": "end card"}]},
          open("transcripts/demo-cuts.json", "w"), indent=1)
PY
python3 $S/scripts/build_reel_timeline.py transcripts/demo-cuts.json

cp $S/templates/assets/brand.css $S/templates/assets/phone.js $G/assets/
[[ -f $G/assets/gsap.min.js ]] || curl -sSL -o $G/assets/gsap.min.js https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js
cp $S/templates/scenes/captions-overlay/index.html $G/scenes/overlay/index.html
for sc in main end overlay; do
  ln -sfn ../../assets $G/scenes/$sc/assets
  ln -sfn ../../timeline.js $G/scenes/$sc/timeline.js
done
T=$(python3 -c "import json;print(json.load(open('$G/timeline.json'))['duration'])")
for sc in overlay; do
  sed -i '' -E "s/(data-composition-id=\"$sc\"[^>]*data-duration=\")[0-9.]+/\1$T/" $G/scenes/$sc/index.html
done
M=$(python3 -c "print(round($T - 2.0, 3))")
sed -i '' -E "s/(data-composition-id=\"main\"[^>]*data-duration=\")[0-9.]+/\1$M/" $G/scenes/main/index.html
sed -i '' 's/const KEYS = \[\];/const KEYS = ["pipeline", "Premiere", "critic"];/' $G/scenes/overlay/index.html
# the first sentence is on screen as the headline, so it is not captioned twice
H=$(python3 -c "import json;w=[x for s in json.load(open('transcripts/voice.json'))['segments'] for x in s['words']];print(next(x['end'] for x in w if 'pipeline' in x['w'].lower()))")
sed -i '' "s/const HIDE = (c) => false;/const HIDE = (c) => c.start < $H;/" $G/scenes/overlay/index.html

for sc in main end; do
  (cd $G/scenes/$sc && hf render --quality standard --output ../../renders/$sc.mp4 > ../../renders/$sc.log 2>&1)
done
(cd $G/scenes/overlay && hf render --format mov --quality standard --output ../../renders/overlay.mov > ../../renders/overlay.log 2>&1)
$PY $S/scripts/build_voice_reel.py $G/reel.json all
print "Done: examples/demo/exports/demo/demo.mp4 and examples/demo/$G/demo.xml (import into Premiere as a new sequence)"
