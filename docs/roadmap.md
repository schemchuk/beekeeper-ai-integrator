# Roadmap

Status: M1-M2 ACCEPTED (Volodymyr, 2026-11-25). M5 ACCEPTED (Volodymyr, 2026-11-26; gate 4 of 4:
interview -> spec -> architecture -> **tasks**).
Sources: `docs/product.md`, `docs/spec.md`, `docs/architecture.md`, `docs/adr/001-010`. One task = one small PR-sized step with tests.
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
| T08 ✅ | `render` + `check` steps (ADR 002): Python calls Remotion per language, then checks the output contract (H.264 yuv420p, 1080x1920, 30 fps, AAC 48 kHz, 3-90 s, < 20 MB) | `beekeeper build` makes both reels and passes `check` |
| T09 ✅ | Script finished: Volodymyr's edits to 002 (Pylyp's lines in his words, final punchline) | he approves the text |
| T10 ✅ | First real reel: build 002, Volodymyr watches, fixes, then `/work ai` the DE reel | the reel is published by postpilot |

Order: T01-T04, then T05-T08, T09 can run in parallel any time before T10.
After T10: ask Volodymyr about making the repo public (BRIEF: public with the first finished reel).

## M2. Automatic handoff (ADR 005)

| # | Task |
|---|------|
| **postpilot** | ADR + `factory-intake` workflow: approved item at `release_at`, idempotent by `episode` |
| T11 ✅ | `post` block in `episode.yaml` (DE + UA post text), approved with the script. Rules (2026-11-26): the first line is a hook (a pain or a question, not "Neuer Zeichentrickfilm"); a question at the end that invites comments; an offer, never a request ("Wiederkehrende Aufgaben im Team? Schreiben Sie mir."); a "grain" for the reader (tip, script, link to the real code); `beekeeper validate` checks the parts are there |
| T21 ✅ | Cover (BRIEF cover rule): `cover` block in `episode.yaml` (monitor text with a recognizable IT pain, character, title); Remotion still `cover.png` and the same picture as frame 0 of both reels; `check` fails a reel without it |
| T12 ❌ | Superseded by T33 (ADR 009). Was: `handoff` step: `sendVideo` of the DE reel to his chat, then `workflow_dispatch` with the v1 JSON; `.env` secrets; retry + Telegram alert; UA reel archived |

## M3. Telegram workflow (`docs/product.md` §5)

Superseded by M5 (2026-11-26): the factory runs its own Telegram bot (ADR 006), postpilot
only publishes; the monthly plan is dropped (spec §7 Q1). Kept for history.

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

T17-T20 stay as the backlog after M5; the postpilot statistics row is replaced by F6.

| # | Task |
|---|------|
| T17 | Scene library: job interview, Jobcenter, apiary (seasons), office |
| T18 | Script generator: seed in, 3 options out, he picks one |
| T19 | Music decision (open question, `docs/product.md` §10) |
| **postpilot** | Statistics for factory reels, monthly overview in Telegram |
| T20 | After 8 LinkedIn weeks: remind him about a free YouTube Shorts test |

## M5. The factory (`docs/spec.md`, `docs/architecture.md`, ADR 006-010)

Goal (spec §5): episode 003 goes from an idea in Telegram to a post published by postpilot,
with no manual step on the factory side. Code in `src/beekeeper/factory/`; Telegram, GitHub
and Claude behind interfaces with fakes, so CI never calls them.

| # | Task | Done when |
|---|------|-----------|
| T22 | Calendar (`calendar.py`): next release slots Tue/Thu 08:00 Europe/Berlin, every deadline of a slot (T-5d ask, T-4d 20:00, T-3d 02:00 script, 07:00 send, T-1d 07:00 accept) | unit tests with a fake clock, DST in March and October |
| T23 | State (ADR 007): `factory/queue.yaml` and `factory/slots.yaml` load/save; queue ops edit, move, delete, first; release date per item; slot states and transitions | unit tests for every op and transition, invalid transitions refused |
| T24 | Telegram client (`telegram.py`): `getUpdates`, `sendMessage`, `sendVideo`, `sendPhoto`, inline buttons, `getFile`; serves only `FACTORY_CHAT_ID`; config from `.env` | tests with a fake HTTP layer; a live smoke test by hand with his bot |
| T25 | `beekeeper factory` process: poller, worker (one job at a time), clock every 15 min and on wake; systemd user unit + `loginctl enable-linger` steps in the docs | the service starts, survives a restart, answers `/start` |
| T26 | Brain (ADR 008): `claude -p` wrapper, one prompt file per job in `prompts/`, JSON answer checked against a schema, auth error -> plain alert | tests with recorded answers |
| T27 | Idea intake (F1.1-F1.3): text -> brain: story, command or both; story saved verbatim and sorted into `bible/`, becomes a queue item; unsure -> one short question; git sync commits `content: ...` and pushes | a sample tall tale ends up in `bible/` and the queue |
| T28 | Voice notes (ADR 010): download, local whisper to Ukrainian, "Почув так: ..." back, then T27 | a recorded voice note becomes the right text |
| T29 | Queue in chat (F2.2-F2.4): `/черга` with position, title, date and buttons (up, first, edit, delete); plain words -> brain -> a queue op | the ops work from buttons and from words |
| T30 | Script (F3.1, F3.2, F3.5, F7.1): T-3d 02:00 brain writes `episode.yaml`; `beekeeper validate`, up to 3 retries, then an alert; 07:00 UA, DE, cover idea, post to the chat and `~/Desktop/temp/<episode>-script.md` (`mkdir -p` every time) | a fake-clock run writes, validates and sends a script |
| T31 | Edits and approval (F3.3, F3.4): UA edit (text or voice) -> new UA, re-adapted DE, changed German words marked; "погоджую" accepts at once, silence at T-1d 07:00 | edit and both approval paths tested |
| T32 | Production (F4): on `accepted` run `beekeeper build`, send the DE reel to the chat, UA reel stays in `out/` | a fake build moves the slot to `built` and sends the reel |
| T33 | Handoff (F5, ADR 009): release `reel/<episode>` with reel, cover, post texts; `factory-intake` dispatch `{v: 1, episode, release_at, ai}`; retry + alert; "стоп" before `release_at` deletes the release, after it is refused; never two releases of one episode | tests with a fake GitHub; idempotency tested |
| T34 | Temp cleaning (F7.2): `beekeeper-temp-clean.timer`, `OnCalendar=Mon 07:00 Europe/Berlin`, `Persistent=true`, independent of the factory | timer installed, a dry run lists what it would delete |
| T35 | His style (F1.4): a daily brain job adds new phrases from all channels to `voice/volodymyr.md`; all bot replies use that file | a sample day adds a phrase; replies carry the file in the prompt |
| T36 | README (N6): `README.md` in English and a short `README.de.md`; link the cartoons, show the factory -> postpilot contract (R1-R4) | both READMEs in `main` |
| T37 | MVP run: episode 003 end to end, live, published by postpilot from a factory handoff | 003 is on LinkedIn on its slot |

Order: T22-T26 (base), then T27-T29 (ideas), T30-T33 (one slot from script to handoff),
T34-T36 any time, T37 last. Before T24 Volodymyr makes the bot with BotFather (token into `.env`).
The lid setting (architecture §9 A2) is already done.

After the MVP: F2.5 reserves, F6 statistics, then M4 (T17-T20).
