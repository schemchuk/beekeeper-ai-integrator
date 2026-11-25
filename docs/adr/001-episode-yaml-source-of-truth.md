# 001. `episode.yaml` is the single source of an episode

Status: ACCEPTED (Volodymyr, 2026-11-25)

## Context

Episode 001 was made by hand: lines in `lines.txt`, two SRT timings, an SVG, ffmpeg commands.
Nothing tied them together, so every change meant redoing the timing by hand. The product
(`docs/product.md` §1, §9) asks for one file in and two reels out, with no manual timing.
Volodymyr edits Ukrainian; the German production text must follow (§5).

## Decision

1. Each episode lives in `episodes/NNN-slug/episode.yaml`: id, title (UA, DE), release date,
   calendar month, seed (link to `bible/`), scene, and an ordered list of lines.
2. A line has `who` (a key of `characters/cast.yaml`), `ua`, `de`, optional `action`
   (what the speaker does on screen), `shot`, `onscreen` (text shown on screen), `sfx`, `note`
   and `pause` after it. A line without `who` is a silent shot with `onscreen` text.
3. German is adapted, not translated word for word; both texts sit side by side in the
   same line, so an edit to UA shows exactly which DE line must change.
4. Everything else (wav files, timings, subtitles, frames, MP4) is generated into
   `out/NNN-slug/` and never edited by hand. `out/` is not the source of anything.
5. Timing comes from the real wav durations plus pauses, never from a hand-made SRT.

## Consequences

- One place to review and to diff; Telegram previews are rendered from this file.
- The format grows by adding optional keys; old episodes keep working.
- Episode 001 stays as reference material only, or is rewritten into this format later.
