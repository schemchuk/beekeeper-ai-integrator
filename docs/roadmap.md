# Roadmap

Status: ACCEPTED (Volodymyr, 2026-11-25).
Sources: `docs/product.md`, `docs/adr/001-005`. One task = one small PR-sized step with tests.
Tasks marked **postpilot** are requests (`docs/postpilot-requests.md`), built in postpilot's
own process, not here.

## M1. MVP: episode 002 from YAML to two reels

Goal (`docs/product.md` §9): `beekeeper build episodes/002-medunko-v-splyachtsi` gives
`out/002-.../reel_de.mp4` and `reel_ua.mp4` with no manual timing or assembly; the DE reel
goes to postpilot by hand with `/work ai`.

| # | Task | Done when |
|---|------|-----------|
| T01 ✅ | Python package skeleton: `pyproject.toml`, `src/beekeeper/`, CLI `beekeeper`, pytest, ruff, CI on GitHub Actions | `beekeeper --help` runs, CI green |
| T02 ✅ | Episode schema (ADR 001): load and validate `episode.yaml` (lines, `who`, `ua`/`de`, optional `shot`, `onscreen`, `sfx`, `pause`), clear errors with line numbers | 002 validates; broken samples fail with a readable message |
| T03 ✅ | Voice step (ADR 003): one `synthesize()` interface over the existing `tools/holos_engine.py`, `chatterbox_engine.py` and Piper, settings from `cast.yaml`, `fx` with rubberband, loudness, 48 kHz; per-line cache by hash | 002 voiced in UA and DE; a one-line edit re-voices one line |
| T04 ✅ | Timing step: durations from wav + pauses -> `timeline.json` per language (lines, on-screen texts, sfx, start/end in frames at 30 fps) | timeline matches the wav lengths; unit tests |
| T05 ✅ | Remotion project (ADR 004): composition 1080x1920 30 fps reading `timeline.json`, audio track, subtitles in Inter, scenes as plain backgrounds | a render of 002 plays with correct sync |
| T06 ✅ | Characters as components from `characters/*.svg`: idle, talking (mouth/pose switch while their line plays), simple entrance | Pylyp and Medunko move and talk in 002 |
| T07 ✅ | Scenes for 002: hut (night, snow, laptop, phone) and den; phone close-up with message pop-ins and buzz sfx | both scenes look like the script |
| T08 | `render` + `check` steps (ADR 002): Python calls Remotion per language, then checks the output contract (H.264 yuv420p, 1080x1920, 30 fps, AAC 48 kHz, 3-90 s, < 20 MB) | `beekeeper build` makes both reels and passes `check` |
| T09 | Script finished: Volodymyr's edits to 002 (Pylyp's lines in his words, final punchline) | he approves the text |
| T10 | First real reel: build 002, Volodymyr watches, fixes, then `/work ai` the DE reel | the reel is published by postpilot |

Order: T01-T04, then T05-T08, T09 can run in parallel any time before T10.
After T10: ask Volodymyr about making the repo public (BRIEF: public with the first finished reel).

## M2. Automatic handoff (ADR 005)

| # | Task |
|---|------|
| **postpilot** | ADR + `factory-intake` workflow: approved item at `release_at`, idempotent by `episode` |
| T11 | `post` block in `episode.yaml` (DE + UA post text), approved with the script |
| T12 | `handoff` step: `sendVideo` of the DE reel to his chat, then `workflow_dispatch` with the v1 JSON; `.env` secrets; retry + Telegram alert; UA reel archived |

## M3. Telegram workflow (`docs/product.md` §5)

| # | Task |
|---|------|
| **postpilot** | Ideas and tall tales in via Telegram, handed to the factory |
| T13 | Idea intake: sort incoming stories into `bible/` as `bible/README.md` says |
| **postpilot** | Script review in Telegram: UA + DE side by side, his UA edits, silent approval the morning before release |
| T14 | UA edit -> DE update with changed words marked |
| **postpilot** | Monthly plan: sent on the 20th, warning on the 24th, accepted on the 25th morning |
| T15 | Monthly plan generator from `bible/apiary-calendar.md`, `bible/ideas.md`, `bible/schedule.md` (Tue + Thu 08:00 Berlin) |
| T16 | Scheduler on the laptop: build the day before release after the script is accepted |

## M4. Two episodes a week, steady

| # | Task |
|---|------|
| T17 | Scene library: job interview, Jobcenter, apiary (seasons), office |
| T18 | Script generator: seed in, 3 options out, he picks one |
| T19 | Music decision (open question, `docs/product.md` §10) |
| **postpilot** | Statistics for factory reels, monthly overview in Telegram |
| T20 | After 8 LinkedIn weeks: remind him about a free YouTube Shorts test |
