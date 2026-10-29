# Demo project

Renders a 17-second faceless reel end to end without any footage of your own, and doubles as a smoke test for the pipeline:

```bash
zsh examples/demo/make_demo.sh
```

1. `say` (macOS) speaks `script.txt` into `raw/voice.aiff`.
2. `transcribe.py` writes word timestamps, a tiny inline step writes the cut list.
3. `build_reel_timeline.py` turns it into `graphics/demo/timeline.json` with caption blocks.
4. HyperFrames renders the phone scene (`graphics/demo/scenes/main`), the end card (`scenes/end`) and the karaoke caption overlay (from `templates/scenes/captions-overlay`).
5. `build_voice_reel.py` mixes the voice to −14 LUFS, cuts the scenes frame-accurately, burns in the overlay and writes `exports/demo/demo.mp4` plus `graphics/demo/demo.xml` for Premiere.

Import the XML into Premiere (File → Import, or ask Claude to run `import_fcp_xml`) to get the sequence with scene, overlay, mix and muted stems on separate tracks.

The first run creates `.venv` from `skills/reel-editor/requirements.txt` and downloads the ~1.6 GB Whisper model (set `PY=` to use an existing Python instead). Needs macOS (for `say`), ffmpeg, Node.js and an internet connection for the first HyperFrames and GSAP download.
