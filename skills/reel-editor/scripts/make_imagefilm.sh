#!/bin/zsh
# Builds a whole brand film: timing -> transitions/end card + texts (HyperFrames, alpha) -> audio -> master -> Premiere XML
# Usage (from the project folder): <skill-dir>/scripts/make_imagefilm.sh graphics/<film>/A [--no-render]
set -e
S=${0:A:h}  # folder of this script
D=$1
PY=.venv/bin/python
hf() { npx -y hyperframes@0.8.114 "$@" }
export NODE_OPTIONS=--max-old-space-size=12288
$PY $S/build_imagefilm.py $D/edit.json js
$PY $S/gen_transitions.py $D
T=$(python3 -c "import json;s=open('$D/edit.js').read();print(json.loads(s[s.index('=')+1:s.rindex(';')])['total'])")
sed -i '' -E "s/(data-composition-id=\"texts\"[^>]*data-duration=\")[0-9.]+/\1$T/" $D/comp-texts/index.html
if [[ "$2" != "--no-render" ]]; then
  mkdir -p $D/renders
  (cd $D/comp-transitions && hf render --format mov --quality delivery --output ../renders/transitions.mov > ../renders/transitions.log 2>&1)
  (cd $D/comp-texts && hf render --format mov --quality delivery --output ../renders/texts.mov > ../renders/texts.log 2>&1)
fi
$PY $S/build_imagefilm.py $D/edit.json audio
$PY $S/build_imagefilm.py $D/edit.json master
$PY $S/build_imagefilm.py $D/edit.json xml
