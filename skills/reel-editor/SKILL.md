---
name: reel-editor
description: Edits Instagram Reels, TikToks, YouTube Shorts and short brand films (9:16, 30–60 s) at agency level – from talking-head A-roll plus screen-recording B-roll, from a voice memo plus phone screens (faceless reel), or as a brand film without dialog from raw iPhone footage with music and text. Hook with a promise, payoff, punch-in zooms, transitions, captions inside the safe zone, sound design, and a new Premiere Pro sequence via FCP XML. Every video goes through the critique loop (skill `critique-loop`, agent `critic`) and is only handed over at 8/10 or better. Use whenever someone wants a Reel, Short, TikTok or brand film cut from raw material, or asks to edit video in Premiere Pro with Claude.
---

# Reel Editor

**Scripts** live in `scripts/` next to this file (the skill's base directory is shown when it loads). Below, `$S` means that folder. Run every script **from the project folder**: all paths in configs are relative to it.

**Project layout** (create what is missing):

```
raw/          source footage and voice memos – never modify or delete
transcripts/  Whisper output (.json with word timestamps, .srt, .txt) and cut lists
graphics/     one folder per video: HyperFrames scenes, timeline.json, reel.json, STATUS.md
exports/      one folder per video: final file + cover on top, older versions in versions/
sfx/          sound effects (see the repo's sfx/README.md)
```

Keep a `STATUS.md` in each `graphics/<project>/`: clip inventory, decisions, critique rounds. Brand colours, fonts and tone come from the project's `CLAUDE.md` (template: `templates/CLAUDE.md`).

## Project setup (when asked to set up a folder, or when the folders above are missing)

1. Create `raw/ transcripts/ graphics/ exports/ sfx/` in the current folder.
2. Copy `templates/CLAUDE.md` to the project root if none exists and ask the user for brand colours, fonts, tone, form of address and end-card handle to fill it in.
3. `python3 -m venv .venv && .venv/bin/pip install -r <skill-dir>/requirements.txt`.
4. Run `zsh $S/doctor.sh` and fix or report every ✗ (sound effects: point to the repo's `sfx/README.md`).
5. For each new video: copy `templates/assets/` (brand.css, phone.js, transitions.js) to `graphics/<project>/assets/`, add GSAP there (`curl -L -o graphics/<project>/assets/gsap.min.js https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js`), and start scenes from `templates/scenes/` and `templates/endcard.html`.

## Quality loop (mandatory for every video)

Process, scale and rules are in the skill **`critique-loop`** (agent `critic`): render → check yourself → critic → below 8, apply the feedback and let the same agent re-score → at 8/10 hand over → then write the lessons back into this file. Video-specific:
1. Check yourself before the critic sees it: `$S/frame_sheet.py` (whole film every 1 s, hook every 0.1 s), loudness, picture/sound sync (frame count = timeline × 30).
2. Also give the critic: funnel stage (top/middle/bottom), script, cut list/`timeline.json`, scene HTML, raw audio, the path to `$S/frame_sheet.py`; with several versions the other one for comparison. Work on the other version in parallel.
3. Typical rounds: brand film A 5 → 7 → 8 (3 rounds), B 5 → 6 → 7 → 8 (4 rounds). One round ≈ 5–10 min of changes, 4–7 min rendering, 6–18 min critique. From 8 upwards the critic mostly names limits of the footage (handheld camera, blown-out white walls, only one take) → 9/10 comes from a better shoot, not from more editing rounds.

## Pipeline (in this order)

1. **Inspect the material:** `ffprobe` (resolution, fps, rotation, HDR?). iPhone A-roll is usually HLG HDR (`arib-std-b67`) → tone-map to Rec.709 in Premiere (sequence "Direct Rec.709 (SDR)", clip detected as Rec.2100 HLG, tone mapping on). No extra HLG LUT on top (double conversion). Exception: the brand-film pipeline below, where `$S/hlg_lut.py` converts while rendering the shots and Premiere gets SDR.
2. **Transcribe:** `$S/transcribe.py <file> --lang <code>` (mlx-whisper large-v3-turbo). Never an English-only model such as `small.en` for other languages: it silently translates into English.
3. **Measure real speech onsets:** Whisper often puts word starts 0.3–0.7 s too early. `ffmpeg -af silencedetect=noise=-46dB:d=0.25` on the dialog → cut points on level edges, 80 ms of air. Remove pauses > 0.4 s, filler words, slips and repetitions.
4. **Choose takes:** the last clean take, unless an earlier take is clearly better in content (note the reason in the cut list).
5. **Cut list** `transcripts/<name>-cuts.json` → `python3 $S/build_reel_timeline.py transcripts/<name>-cuts.json` → `timeline.json` + `timeline.js` (output times + word-accurate caption blocks). `word_fixes` for Whisper errors (names, swallowed short words) and for re-timing words Whisper stretches across cuts. Example: `templates/examples/cuts.json`.
6. **Graphics** in HyperFrames, one scene per folder `scenes/<name>/index.html` with symlinks `assets -> ../../assets` and `timeline.js`. Scenes opaque as MP4 (`-q delivery --video-frame-format png`), overlay (captions + texts) transparent as ProRes 4444 (`--format mov`).
7. **Dialog audio** processed separately (`audio/<name>-dialog.wav`): highpass 80 Hz, afftdn, EQ (−2 dB @250 Hz, +2.5 dB @3.5 kHz), compressor 3:1, loudnorm −16 LUFS. Camera audio typically arrives around −31 LUFS.
8. **Premiere:** save the project → `python3 $S/build_premiere_xml.py <timeline.json> <premiere-xml.json>` (example `templates/examples/premiere-xml.json`) → `import_fcp_xml` = a new sequence (V1 A-roll, V2 scenes, V3 overlay, A1 dialog, A2+ SFX spread over free tracks). Then zooms as Scale/Position keyframes through the MCP.
9. **Export** H.264 High, 1080×1920, constant 30 fps, VBR 2-pass ~16 Mbit/s, AAC 320 kbit/s 48 kHz. Master at **−14 LUFS integrated, true peak ≤ −1 dBTP**.
10. **Check frames** (hook frame 0, every scene change, payoff, end card) before the user sees it.

## Story structure (45 s)

- **Hook 0–3 s, stacked three ways:** picture (the finished result, e.g. a phone showing the website), text headline from frame 1 without a fade-in (4–8 words, understandable on mute), a spoken sentence with a number/result.
- **Promise → payoff:** a concrete claim in the hook ("4× 100/100 in Google's test") plus an open-loop pill ("Proof at the end ↓"). Pay it off as its own 3 s beat before the CTA (riser → bass hit → chime). Never put the CTA before the payoff.
- Then: who I am (lower third) → the project with B-roll → numbered points (1/4 … 4/4) → payoff → CTA → end card (1.5–2 s).
- **Pacing:** a visual change every 1–1.5 s in the first 5 s, then every 2–4 s. B-roll about 35–50 % of the runtime.
- **Honesty:** numbers only if measured. Measure Lighthouse yourself, for example (`npx lighthouse@13 <url> --preset=desktop`, mobile several times because it fluctuates), and put method + date in small type into the graphic.

## Look

- **A-roll zooms:** jump-cut punch 100→112–120 %, emphasis 118→128 % in 4–6 frames, slow push 100→106 % across the clip. Return to 100 % after a punch (contrast). Anchor on the face, not the frame centre: `Position = target − (face − centre) × scale`.
- **Never show a raw screen recording:** phone mockup on a background in the brand colour (watermark monogram 7 %, fine grain, vignette), your own "9:41" status bar over the real one (recording dots gone), 3D fly-in (`rotationY/X` + `transformPerspective`), camera moves onto UI details with a frame in the accent colour, tap ripple on clicks. For zoom shots use razor-sharp stills from the recording (`ffmpeg -ss t -frames:v 1`), positions as fractions of the screen.
- **Fonts/colours:** a heavy sans for headlines/captions (weight 800), a quiet sans for small text, both set as variables in `assets/brand.css`. Colours from the brand book: a dark main colour, an accent colour used only as an accent (never a light accent as text on white; text ON the accent in the dark main colour), a light neutral.
- Looks cheap: decorative transitions (wipes, flares), emoji floods, glow, a hit sound on every cut, landscape video with bars.

## Captions (bottom left)

- Box: x 120–780 (max. 660 px wide), bottom edge y 1400. Top clear from y 270. Keeps clear of the Instagram AND TikTok UI (right button column, caption/username at the bottom ≥ 484 px). For paid ads move up to y 1090–1248.
- Heavy sans, 66 px (shrinks to 50 px instead of breaking long compound words), soft shadows instead of an outline. 1–3 words / ≤ 22 characters per block, break at punctuation.
- Normal sentence case (all-lowercase reads measurably slower).
- Karaoke: upcoming words at 55 % opacity → spoken 100 %. At most one keyword per sentence in the accent colour, with a small pop (1.08×). Word spacing via `gap` on a non-wrapping flex box, not spaces.
- Info cards (lower third, 1/4 points, chips, CTA) in the chest zone y 1030–1150: between chin and captions, the face stays clear.

## Sound

- Local SFX in `sfx/`: whoosh, whoosh-short, whoosh-cinematic, impact-bass-1/2, pop, click, click-soft, ping, riser, chime, sparkle, glitch-1..3, typing, sub-hit (not included in the repo, see `sfx/README.md`).
- Whoosh on every B-roll entry, click on UI zoom/tap, pop on text, one riser (last 3 s) into the payoff, bass hit only on 1–2 peaks. Levels per SFX list in the config (impact −13…−15 dB, whoosh −8, pop −10, click −2…−4).
- Music 15–20 dB under the voice, loud only where nobody speaks. Licensing: for business accounts only properly licensed music (e.g. Epidemic Sound or Artlist business plans) in the master; free option = add music inside the app (Meta Sound Collection / TikTok Commercial Music Library).

## Faceless reel (voice memo + phone screens + graphics)

Tools:
- `$S/transcribe.py` (runs without `condition_on_previous_text`, otherwise Whisper swallows whole takes). If the script was read twice in full: last clean take; a sentence with a slip from the other pass, splice parts of both if needed (reason in the cut list).
- Measure pauses by level (10 ms RMS, threshold = 20th percentile + 6 dB), not from Whisper.
- Cut list with `"caption_offset": 0.15` (Whisper is early) and `"caption_hold": 0.15` (a block ends 0.15 s after its last word, never after the clip) → `build_reel_timeline.py`.
- Scenes: start from `templates/scenes/` (karaoke caption overlay) and build your own scene library in `assets/` (e.g. search page with keyboard, website with Safari bar, typing via `tl.set`, frames/ripples on screenshot coordinates) plus the phone mockup helper `templates/assets/phone.js`. With many scenes, generate the HTML files with a small Python generator. Phone screenshots via Playwright (iPhone 13, DPR 3, `channel: 'chrome'`).
- `$S/build_voice_reel.py graphics/<reel>/reel.json`: voice (30 ms crossfade at splices), music with `pause_boost_db`, SFX with `align: "peak"`, scenes trimmed frame-accurately to their `data-duration` + caption overlay → master −14 LUFS / −1 dBTP. Step `xml` writes `graphics/<reel>/<reel>.xml` for Premiere (V1 scenes one by one, V2 overlay, A1 mix, A2–A4 voice/music/SFX as muted stems) → new Premiere project, import the XML. Example: `templates/examples/reel.json`.
- Put the music under the edit part: beat grid by regression, choose `music.offset` so the edit part starts on a beat, edit length = whole beats.

What the critic finds in faceless reels – check yourself first (typical: two reels 6 → 7 → 8 in 3 rounds each; the second already benefited from the first one's rules but failed round 1 on new mistakes: blur, spoiler hook, repetition):
- **Proof on screen:** every spoken claim about real clients must be visible verbatim in the picture (a screenshot of exactly that spot). Check the live website before building (where is the phone number really? opening hours?). Cut unproven parts of sentences ("booking and number at the top" → "booking at the top") instead of asking for a new recording.
- **Hook:** frame 0 = conflict (before|after or practice A|B, big phones ≈ 80 % width) + headline + target group ≥ 40 px, hold about 1.2 s, no captions meanwhile. Then immediate movement (typing, push-in), never > 1 s standstill.
- **Amount of text:** per moment at most headline + one chip + captions. If a sentence is the headline, it is not captioned (`HIDE` in the overlay). Put a counter (1/4) in the label subline instead of its own pill.
- **Headline changes** one after the other (old out 0.14 s, then new in), never crossfaded.
- **No empty frames** at scene boundaries: every scene shows content from frame 0, fly-ins start close to their end position, whips ≤ 0.2 s.
- **Captions:** box 90 % in the dark brand colour, unspoken words 55 %. Never on top of a big website headline during a zoom.
- **Zoom onto the phone:** fade out labels/chips first or place them lower (target y ≈ 1000); approach buttons near the edge with factor ≤ 1.5, otherwise the phone gets cropped.
- **Right safe zone:** nothing important beyond x ≈ 920, no accent frames or pills either.
- **Sound:** music −23 dB under the voice, +4 dB in pauses, loud (−9…−11 dB) only in the beat, edit part and end card. 15–18 SFX in 35–45 s, no pops under words, no riser for a calm brand.
- **End card:** a concrete reason to follow ("Next up: …") at ≥ 36 px, logo visible from frame 0.
- **Privacy/third-party brands in screenshots:** whatever must be blurred (host name, patient names) is burned into the image asset (ffmpeg `crop,boxblur` + `overlay`), never as a layer per scene. Otherwise the blur is missing in the thumbnail, during zooms or in later scenes.
- **Before/after hook:** frame 0 shows only the before, big and edge to edge (zoom ≥ 2.2 so the screen fills the frame width). Show the after only at the reveal (swipe, white flash, sub hit), otherwise it fizzles. White headline on a white website: a gradient in the dark brand colour (`.topshade`) behind it.
- **No repetition:** don't show the same website image several times with only a changing chip. Every statement gets its own moving picture (scroll, hard cut between language versions, split "typical site | client").
- **Edit part:** only real footage (no mockups), warm grade (`contrast 1.08, saturate 1.12, sepia 0.06`), 6–8 half beats, music at −5 dB there.
- **Read screenshots for unwanted messages:** cover or cut sentences like "site under construction" on the client's page, especially if the reel criticises exactly that.
- **Phrase chips positively:** a red ✕ reads on mute as a flaw of the site ("No form"), so use a green ✓ with a positive statement ("Straight to the phone").
- **Splices:** a stressed word before a mid-sentence cut −2 dB (`gain_db` on the clip) and 50–80 ms of air (`gap`), entry on the onset of the next word.
- **End card with keyword CTA:** ≥ 3 s, fully visible within 0.15 s, the keyword itself big (≈ 110 px in the accent colour).
- **Short intro:** cut sentences that only repeat what the header or picture already says; reveal or first punchline before 6 s. Show elements in the caption zone (y 1180–1400, e.g. a URL pill) only while no captions run there.
- **Edit part with a build:** let the music rise during the edit (e.g. −2 → +2 dB over the last 2 s) plus a quiet riser into the next scene change, otherwise the energy drops before the CTA.
- **Check footage edges:** feet/objects of the camera person at the frame edge → crop with a 110 % zoom and an anchor; never put the logo/wordmark on people, use calm surfaces.

## Brand film without dialog (footage + music + text)

Tools (all in `$S`; a cut list `graphics/<film>/<version>/edit.json` is the single source of truth, example `templates/examples/edit.json`):
- `hlg_lut.py <out.cube> --grade --exposure 0.48 --wb 0.95,1,1.05` – iPhone HLG → SDR with a grade (works without ffmpeg's zscale). Variants per shot: brighter (0.62) for dark hook shots, "soft" (0.38–0.42) against blown-out white walls, cooler (`--wb 0.78–0.84,1,1.16–1.22`) for warm artificial light.
- `render_shots.py <edit.json> [ids]` – shots with `in`, `dur`, `speed` (60p → 0.5 = clean slow motion, 2.0 + `blur` = time-lapse), `zoom` [start, end] + `anchor` (push-in on the 4K plane, up to zoom 2.0 without losing sharpness), `lut`, `eq`; 0.5 s handles for transitions; `extras` = additional shots (e.g. one half of a split screen).
- `gen_transitions.py <dir>` → HyperFrames composition V2 (transitions, split screen, end card from `<dir>/endcard.html`), library `assets/transitions.js` (copy from `templates/assets/transitions.js`, end card from `templates/endcard.html`): dissolve, blurdissolve, bloom, zoomthrough, whipleft/right, slideup, flash, punch, flashcard (2 frames of white → hard cut to the end card), tocard.
- `<dir>/comp-texts/index.html` → V3 texts (alpha, your own composition with `data-composition-id="texts"`; `make_imagefilm.sh` stops if it is missing). `build_imagefilm.py <edit.json> js|audio|master|xml`, everything at once with `make_imagefilm.sh <dir>` (~5–7 min). Contact sheet `frame_sheet.py`.
- Premiere: a new project per version, import the XML: V1 shots, V2 transitions + end card, V3 texts, A1 master mix, A2/A3 music/SFX as muted stems.

Process and rules that proved themselves:
- **Review the footage:** contact sheets of all clips (timestamps in `index.txt`), check the audio (Whisper hallucinates "thank you" on silence → iPhone audio is usually unusable → music throughout). Write a clip inventory with times into `STATUS.md` before cutting.
- **Analyse the music first:** a Mixkit page via curl → its JSON-LD gives title, genre and mp3 URL. With librosa find the energy curve, bass/highs per second, drop/breakdown. **Beat grid by linear regression over all beats** (not librosa's tempo – a 0.5 % error = 2–3 frames off after 30 s). Plan cuts, texts and SFX in beats, choose `music.offset` so film 0 is a downbeat. Breakdown too long → cut `music.segments` on bar lines. Ending: a hard `music.stop` on a beat + sub hit/chime, or end in a natural dip of the song. Before the drop: `lowpass_until` (music "behind the door") + riser.
- **Two versions that are really different:** a different structure (A linear: hook → place → work, B: work → question → place → answer on the drop), different music, form of address, typography (serif bottom left with a dark gradient vs. sans boxes), transitions, end card, takes. No line of text repeated verbatim.
- **Typography:** text bottom left (bottom edge y 1370, right edge max. x 930), never wrap lines → scale down lines that are too wide by script; make the block wider than the line (otherwise `overflow:hidden` cuts off the last glyph). Hook text from frame 0, ≤ 9 words, ≥ 2 s. Keep the dark gradient constant (don't fade it per text), subtle from y ≈ 1000. Designed moments instead of the same box every time: a question in the main colour directly on a white wall, a growing 01/02/03 list, split screen on the drop.
- **Client statements only if proven** (the client's website, its i18n files). Have descriptive sentences about treatments confirmed by the client.
- **What the critic always finds – check first:** reflections (camera person in black glass, printer lids, monitors), wine bottles/hair/cable mess, people in unflattering poses (open mouths, upside down: crop tight on hands, zoom 1.9–2.0 anchor y 0), text over faces, cut-off eyes, the same shot several times, people too small, a hook image greyer than the rest, a double action across a cut, an important move hidden in a bloom, CTA < 2.5 s, SFX > 10 dB under the music, true peak > −1 dBTP, white-balance jumps.
- **Sound:** put the SFX peak on the target time automatically (`peak`), clicks/shutter at +10…+16 dB, a whoosh on every whip, a sub hit on reveal/drop/logo. Master: the sum together to −14 LUFS, limiter 0.74 on the sum.
- Get consent from recognisable people (patients, staff, customers) before anything is published.

## Pitfalls

- HyperFrames `lint`/`snapshot` need an `index.html` per project → one scene per folder.
- Never put `<video data-start>` inside a timed wrapper; animate camera/phone with GSAP on untimed wrappers.
- Premiere MCP: `create_sequence` needs a .sqpreset file → create sequences by FCP XML import instead. Never overwrite existing sequences.
- After `import_fcp_xml` the sequence only sits in the project panel → open it via ExtendScript `app.project.openSequence(seq.sequenceID)`, otherwise the user sees "no edits".
- The XML import sets `autoToneMapEnabled=false` (HLG A-roll overexposed) and `compositeLinearColor=true` (alpha overlays look washed out) → flip them to `true`/`false` via `seq.getSettings()/setSettings()`.
- ExtendScript through `execute_extendscript` needs a `return`. Component and property names follow Premiere's UI language → address Motion by index: `c.components[1].properties[0]` = Position (normalised 0–1), `[1]` = Scale. Keyframe time = `c.inPoint + (sequence time − c.start)`, Bezier = interpolation 5. Clamp zoom positions so no edge shows: x ∈ [1080−540s, 540s], y ∈ [1920−960s, 960s].
- If `export_sequence` wrongly reports "Media Encoder not installed" → `seq.exportAsMediaDirect(out, epr, app.encoder.ENCODE_ENTIRE)` with `…/systempresets/4E49434B_48323634/00 - Match Source - High bitrate.epr`, then master the audio with a 2-pass `loudnorm` (I=−14, TP=−1, linear) and copy the video stream. In zsh write `${VAR}:linear` (`$VAR:l` is a zsh modifier).
- Captions on a light piece of clothing: a shadow is not enough → box in the dark brand colour at 82 % opacity. End the overlay clip before the end card (otherwise the CTA pill sits on top).
- Premiere "hangs" at startup (no window, 30–100 MB RAM, 0 % CPU, `bridge_unavailable`) = usually not hanging at all but **no project open and no start screen** (main thread idles in the event loop, check with `sample <pid> 1`). Don't kill it → menu File > New > Project… (the dialog may need foreground clicks) → type a name, skip import mode, Create → click the "MCP Bridge (CEP)" panel tab → `verify_premiere_connection`. Further projects without UI via ExtendScript `app.newProject(<path>.prproj)`, then `import_fcp_xml` (lands in the active project), `openSequence`, Linear Color off, `app.project.save()`.
- After switching projects the bridge's ExtendScript once hung (timeout 45 s, panel still shows "Connected") → load the XML via File > Import, set the sequence settings via the menu ("Composite in Linear Color" off), then save.
- HyperFrames renders with many videos: `NODE_OPTIONS=--max-old-space-size=12288`, otherwise Node runs out of memory. Alpha renders as ProRes 4444 are big (0.5–1.4 GB for 45 s).
- zsh in scripts: `$VAR` containing spaces is not split → use a function instead of `HF="npx …"`.
- Demo music: Mixkit (free licence), as a pre-ducked bed `audio/music-bed.wav` via `build_music_bed.py` (−19 dB under the dialog, −9 dB in payoff/end card, ≈ 17 dB under the voice).
