# Beekeeper AI Integrator: brief

(Working name until 2026-11-25: pasichnyk.)

An experimental episode factory for short AI cartoons about Pylyp (DE: Philipp), a beekeeper
who was pushed by life into retraining as an IT administrator in Germany. Pylyp is
Volodymyr's alter ego: Volodymyr really is a beekeeper, 57, retrained in IT in Germany.
The series is the story of "how I ended up living like this", told with humour.

Positioning (2026-11-25, Volodymyr): not a job seeker begging for work. A gentleman looking
for the right match, who may agree to help a specific person or company automate their
business processes: he takes the routine, they keep the blooming field for their ideas.

Written 2026-11-24 at the end of a postpilot session, so a new session can start here.

## Goal

One episode file in, finished Reels out (UA and DE), with no manual timing or assembly.
Today every step is manual: Claude writes the jokes and an SVG in a chat, Volodymyr runs
Piper and ffmpeg by hand. This project automates that.

```
episodes/NNN-slug/episode.yaml    topic, scene, lines per speaker, UA + DE text
  1. script     Claude drafts or polishes the jokes (UA first, DE translation)
  2. voices     Piper TTS, one wav per line, voice per speaker and language
  3. timing     subtitles (ASS) computed from the wav durations
  4. picture    SVG scene -> frames (animated, see below)
  5. assembly   ffmpeg: frames + voices + subtitles -> out/reel_ua.mp4, out/reel_de.mp4
  then          Volodymyr sends the reel to the postpilot Telegram bot with caption `/work ai`
```

Roadmap, small steps:
1. MVP: rebuild episode 001 from a YAML file, result comparable to the existing reels.
2. Scene library: "night monitor" (exists), "job interview", "apiary", "Jobcenter";
   Pylyp and the bee as reusable SVG parts.
3. Idea generator: a topic in, 3 script options out, Volodymyr picks one.
4. Later, maybe: hand the episode to postpilot directly instead of manual `/work`.

## Agreed with Volodymyr

- Folder `~/VS_Code_projects/beekeeper-ai-integrator` (renamed from `pasichnyk` on 2026-11-25).
  Private GitHub repo `schemchuk/beekeeper-ai-integrator`; it goes public with the first
  finished reel (ask before that step).
- Portfolio-grade: English README, MIT for code, CC BY-NC 4.0 for characters and episodes.
  Nothing paid except a small budget for a Claude subscription and API (2026-11-25).
- The spirit (Volodymyr, 2026-11-25): the project must never make him blush in front of
  readers and viewers; it should make him square his shoulders and walk through life with
  a light step and an ironic smile.
- Process (changed 2026-11-25 at Volodymyr's request): a conventional development flow,
  interview (`docs/interview/`) -> product description -> ADRs -> roadmap -> code. Small
  commits, Conventional Commits, and ask before anything that publishes or costs money.
- Interview 2026-11-25 (`docs/interview/`): German audience first, LinkedIn main channel,
  UA rendered and archived for a possible 2029 switch. 2 episodes per week from the start.
  Telegram (postpilot bot) is the channel for ideas, reviews, approvals and talk. He edits
  UA, edits flow to DE. Pylyp is him by implication only, never said outright; deep
  beekeeping knowledge everywhere. Satire on systems and types, never on real people.
  YouTube Shorts: remind him after 8 weeks of LinkedIn episodes.
- Everything free and local where possible (Piper TTS, ffmpeg, headless Chromium).
- Content is original (own characters, own jokes), no recreation of existing shows.

## Episode 001 "night code" (reference material)

`episodes/001-nichnyi-kod/` holds what was made by hand:
- `ua/`: `beekeeper.svg` (scene), `lines.txt` (12 lines, one per row, Piper input),
  `philip.srt` + `philip3.srt` (two timing versions), `reel_philip.mp4` (74 s, 1080x1920, AAC 44.1 kHz)
- `de/`: `beekeeper_de.svg`, `lines.txt`, `philip_de.srt`, `reel_philipp_de.mp4` (62 s, AAC 96 kHz)

Format: an interview, speakers "Ведуча"/"Moderatorin" (host) and "Пилип"/"Philipp".
The SVG (680x420 viewBox) is a tired cyberpunk beekeeper with a veiled hat and a cyber
monocle at a buggy monitor at night, rain outside, a bee nearby. It already has CSS
animations (typing code lines, blinking cursor, nodding head, coffee steam, bee wings,
pulsing errors), but the old reels used a static PNG of it. If it is reused, the coffee
becomes herbal tea (house rule, `bible/characters.md`). Rendering real animated
frames (headless Chromium/Playwright screenshots or a recorded page) is an easy win.

## How the voices were made (Volodymyr's notes, still valid)

- Piper TTS in the venv `~/tts` (`~/tts/bin/piper`), Kali, shell zsh.
- Voices: `python3 -m piper.download_voices <name>` (no name lists them). Models already
  downloaded: `~/tts/reel/uk_UA-ukrainian_tts-medium.onnx`,
  `~/tts/reel_de/de_DE-kerstin-low.onnx`, `~/tts/reel_de/de_DE-thorsten-medium.onnx`
  (each with its `.onnx.json`). Do not copy models into the repo.
- Ukrainian: one model, three speakers: `-s 0` lada (female), `-s 1` mykyta (male),
  `-s 2` tetiana (female). Host = `-s 0`, Pylyp = `-s 1`.
- German: host = de_DE-kerstin-low, Philipp = de_DE-thorsten-medium.
- One wav per line: `echo "text" | piper -m model.onnx [-s N] -f 01.wav`.
- Pitfalls already solved:
  - The Ukrainian model only knows lowercase Cyrillic: capitals are dropped (first letters
    eaten), Latin is not read. Before TTS: lowercase, and spell English words in Ukrainian
    (Bash -> баш, Linux -> лінукс, Kubernetes -> кубернетіс, IT -> ай-ті,
    command not found -> команд нот фаунд). Subtitles keep the original spelling.
    So each line needs a display text and a spoken text (UA only).
  - German voices need none of this.
  - `${t,,}` works only in bash, zsh says "bad substitution". Prefer Python for the pipeline.
  - Check the `-s` flag with `piper --help`.

## How the video was assembled

- SVG -> PNG (rsvg-convert -w 1920; rsvg-convert is NOT installed now, ImageMagick `magick`
  and `chromium` are), crop to vertical, place on a 1080x1920 background (ImageMagick),
  title on top, room for subtitles at the bottom.
- wav durations via ffprobe; lines back to back with a 0.45 s pause.
- Subtitles: ASS with times from the wav durations, caption colour per speaker.
  Font Inter (not found by fc-list now: install or pick another font).
- Audio: all wavs mixed with adelay + amix (normalize=0), then loudnorm=I=-16:TP=-1.5.
- Video: libx264, 30 fps, subtitles=sub.ass, AAC 160k. Result ~62-76 s.
- No music on purpose: added later in the Reels editor.

## Output requirements (learned in postpilot's live run, 2026-11-24)

The reel goes through postpilot to LinkedIn, Threads, Instagram and Facebook Reels:
- MP4, H.264 yuv420p, 1080x1920 (9:16), 30 fps.
- Audio AAC at 48 kHz (Instagram rejects higher rates; the DE reel had 96 kHz).
- Duration 3-90 s (Reels limit), file under 20 MB (Telegram bot download limit).
- AI-generated: send with `/work ai` so the posts carry the AI label.
- Long interview text does not fit a Telegram caption (1024 chars): send the video with
  `/work ai`, then reply to the bot's "Video received" message with the text.
- Cover rule (Volodymyr, 2026-11-26): LinkedIn shows the first frame as the thumbnail, so
  frame 0 of every reel is a bright cover with a glowing **monitor** in it (IT people are
  drawn to a screen like a magnet), a recognizable character and the episode title.
  Dark or night hooks come after it, never on frame 0. Applies from episode 003 on; 002
  stays as published. Built in: `cover` block in `episode.yaml`, frame 0 held 0.5 s,
  `cover_<lang>.png` for the thumbnail; `post` block -> `post_<lang>.txt` (hook, grain,
  question, offer, hashtags; `validate` rejects begging and biography).

## First steps for the new session

1. Read this file and look at `episodes/001-nichnyi-kod/`.
2. Propose the `episode.yaml` format (speakers, voice per language, display vs spoken text,
   scene, title) and a minimal Python pipeline layout; agree on it with Volodymyr.
3. Build the MVP on episode 001, compare with the existing reels, then iterate.
