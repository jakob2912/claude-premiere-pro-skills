#!/bin/zsh
# Setup check for the reel editor. Run it from your video project folder:
#   zsh <skill-dir>/scripts/doctor.sh
# Prints one line per requirement and exits with the number of failures.
fail=0
ok()   { print -P "%F{green}✓%f $1" }
bad()  { print -P "%F{red}✗%f $1"; (( fail++ )) }
warn() { print -P "%F{yellow}!%f $1" }

[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] && ok "macOS on Apple Silicon" \
  || warn "not macOS/Apple Silicon: transcribe.py uses mlx-whisper, swap in another Whisper for other platforms"

for t in ffmpeg ffprobe; do
  command -v $t >/dev/null && ok "$t $($t -version 2>/dev/null | head -1 | awk '{print $3}')" || bad "$t missing (brew install ffmpeg)"
done
if command -v ffmpeg >/dev/null; then
  enc=$(ffmpeg -hide_banner -encoders 2>/dev/null)
  for e in libx264 prores_ks aac; do [[ "$enc" == *" $e "* ]] && ok "ffmpeg encoder $e" || bad "ffmpeg encoder $e missing"; done
fi

if command -v node >/dev/null; then
  v=$(node -p 'process.versions.node.split(".")[0]')
  (( v >= 20 )) && ok "node $(node -v)" || bad "node $(node -v) is too old, need 20+"
else
  bad "node missing (https://nodejs.org)"
fi

mods=(numpy scipy librosa)
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] && mods=(mlx_whisper $mods)
if [[ -x .venv/bin/python ]]; then
  for m in $mods; do
    .venv/bin/python -c "import $m" 2>/dev/null && ok "python: $m" || bad "python: $m missing (.venv/bin/pip install -r <skill-dir>/requirements.txt)"
  done
else
  bad "no .venv in $(pwd) (python3 -m venv .venv && .venv/bin/pip install -r <skill-dir>/requirements.txt)"
fi

if command -v premiere-pro-mcp >/dev/null; then
  ok "premiere-pro-mcp installed"
  premiere-pro-mcp --doctor >/dev/null 2>&1 && ok "premiere-pro-mcp --doctor passed" \
    || bad "premiere-pro-mcp --doctor failed, run it directly for details"
else
  bad "premiere-pro-mcp missing (npm install -g adobe-premiere-pro-mcp && premiere-pro-mcp --install-cep)"
fi

hf=0
for d in .claude/skills/hyperframes .agents/skills/hyperframes ~/.claude/skills/hyperframes ~/.agents/skills/hyperframes; do
  [[ -f $d/SKILL.md ]] && hf=1
done
(( hf )) && ok "HyperFrames skills installed" || bad "HyperFrames skills missing (npx skills add heygen-com/hyperframes --all)"

missing=()
for s in whoosh whoosh-short whoosh-cinematic impact-bass-1 impact-bass-2 pop click click-soft ping riser chime sparkle typing; do
  [[ -f sfx/$s.mp3 ]] || missing+=$s
done
[[ -f sfx/sub-hit.wav ]] || missing+=sub-hit.wav
(( ${#missing} == 0 )) && ok "sound effects in sfx/" || warn "sfx/ is missing: ${missing[*]} (see sfx/README.md)"

for d in raw transcripts graphics exports; do [[ -d $d ]] || warn "folder $d/ does not exist yet"; done

(( fail == 0 )) && print -P "%F{green}All set.%f" || print -P "%F{red}$fail problem(s) to fix.%f"
exit $fail
