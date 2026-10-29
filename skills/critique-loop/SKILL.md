---
name: critique-loop
description: Quality loop with the critic agent for anything that goes out – Reels, videos, websites, apps, designs, texts. Finish the work, let the `critic` agent score it (1–10, compared with professional work), below 8/10 apply its feedback and have it re-scored until at least 8/10; afterwards improve the skill that produced the work. Use when the user says "review", "feedback", "critique", "rate this", "until 8/10", or another skill requires the quality loop.
---

# Critique loop (until at least 8/10)

The agent `critic` (`agents/critic.md`; installed as a plugin it may be listed as `<plugin>:critic`) is a ruthless creative director. Its scale:
1 = badly made, a Reel gets ≤ 50 views, nobody watches to the end · 7 = decent but not yet professional · **8 = minimum level to deliver/publish** · 9 = very good marketing agency · 10 = perfect, almost unreachable.
It has rubrics for Reels/videos, websites/apps, designs and texts, and it changes nothing.

This skill knows no particular producer. Skills that produce work (e.g. `reel-editor`) point to it, not the other way round.

## Process

1. **Finish the work and check it yourself** before the critic sees it: obvious mistakes otherwise cost a whole round. For videos e.g. contact sheet and loudness, for websites the phone view and the console.
2. **Start the critic** (in the background, `run_in_background: true`):
   - `subagent_type: "critic"`. If the agent is not known in the running session yet (just installed), use `general-purpose` with the first line "First read `<path to agents/critic.md>` and follow it exactly."
   - A brief with everything it needs to judge: **file/URL**, **brief and goal** (for Reels the funnel stage: top/middle/bottom), **target group**, **brand** (colours, fonts, tone, formal/informal address), **proven claims** (everything else counts as unproven), **project documents** (script, cut list, source HTML …), **paths to helper scripts** (e.g. `frame_sheet.py`), a **scratch folder** for its images, round number.
   - Remember its agent ID: the same instance scores all further rounds.
3. **Below 8/10:** a new iteration.
   - Work through its TOP PROBLEMS by impact, at least the first three. Things that are only limits of the material (e.g. only one take exists) get noted instead of bent.
   - Produce again, check briefly yourself.
   - Let **the same agent** re-score via SendMessage: "Round N. Score as if you saw the work for the first time, not milder because something was fixed. Changed: …" with the list of changes.
   - Repeat until the overall score is at least 8. Small polish it still names at 8 may go in without a new round; check it yourself afterwards.
4. **Log** next to the work (`critique-log.md` in the work's project folder): per round the score, the three biggest problems and what was changed.
5. **Hand over to the user only at 8/10 or better.** State score and number of rounds, plus briefly what the critic still misses for a 9.
6. **Then improve the producing skill** so the next time takes fewer rounds: every problem the critic found that generalises becomes a rule, a check step or a default in that skill (e.g. for Reels in `reel-editor/SKILL.md` under "What the critic finds"). Record the number of rounds as a reference value. One-off project details don't belong there.

## Rules
- The critic's score is not talked up or rounded. If a piece is still below 8 after four rounds, show the user where it stands and what it hinges on (usually material or brief).
- The critic is never told to be milder and gets no hints about the desired score.
- Always pass the proven claims: invented numbers, reviews or client statements are a hard problem, however good the rest is.
