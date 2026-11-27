# Architecture: the cartoon factory

Status: ACCEPTED (Volodymyr, 2026-11-26; gate 3 of 4: interview -> spec -> **architecture**
-> tasks). Date: 2026-11-26.
Implements `docs/spec.md` (ACCEPTED 2026-11-26). New decisions: ADR 006-010 (ACCEPTED 2026-11-26).
ADR 005 is superseded by ADR 009, ADR 009 by ADR 011 (release contract v2). ADR 001-004 stay as they are (episode file, Python on CPU,
voices, Remotion).

## 1. Overview

```
 Volodymyr's phone            Laptop (Kali, always on, lid closed)                 GitHub
 ┌───────────────┐  long    ┌────────────────────────────────────────────┐
 │ Telegram chat │  poll    │ beekeeper factory  (systemd user service)  │
 │ with the      │ ◀──────▶ │  poller thread: messages, voice, buttons   │
 │ factory bot   │          │  clock: every 15 min, deadlines (ADR 007)  │
 └───────────────┘          │  worker thread: one job at a time          │
                            │   ├─ whisper (voice -> text, ADR 010)      │
                            │   ├─ claude -p (sort, script, edits, 008)  │
                            │   ├─ beekeeper build (voices..check, 002)  │  release reel/<ep>
                            │   └─ handoff (ADR 011) ────────────────────┼──────────────▶ beekeeper-ai-
                            │  git: bible/, factory/, episodes/ -> push  │                integrator
                            └────────────────────────────────────────────┘  dispatch       (public)
                                                                             polls v2 release  │
                                                                           ─────────────▶ postpilot ─▶ LinkedIn,
                                                                                         (reads the   Threads,
                                                                                          release)    IG, FB
```

One process on the laptop does everything the factory does. It has no server, no database
and no paid service: the Telegram Bot API, Claude Code on the subscription, local whisper,
the existing pipeline, and GitHub.

## 2. Parts

| Part | Job | Code |
|------|-----|------|
| Telegram client | `getUpdates` long polling, `sendMessage`, `sendVideo`, `sendPhoto`, inline buttons, `getFile` for voice notes; only Volodymyr's chat id is served | `factory/telegram.py` |
| Router | sorts each update: button press or slash command -> queue code; free text or voice -> a job for the brain | `factory/router.py` |
| Queue | ideas in order, edit, move, delete, put first; dates from the rhythm | `factory/queue.py` |
| Calendar | pure functions: next release slots (Tue/Thu 08:00 Berlin), every deadline of a slot | `factory/calendar.py` |
| Clock | every 15 minutes and on wake: compares deadlines with the state, queues what is due | `factory/clock.py` |
| Worker | runs jobs one by one (whisper, Claude, build, handoff), reports to the chat | `factory/worker.py` |
| Brain | `claude -p` with a fixed prompt per job, limited tools, JSON answer | `factory/brain.py`, `prompts/*.md` |
| Handoff | GitHub release by contract v2 (`manifest.json`, `video.mp4`, `cover.png`, texts), optional `project-intake` dispatch, stop = delete release | `factory/handoff.py` |
| Git sync | commit and push the factory's content changes | `factory/gitsync.py` |
| Pipeline | today's `beekeeper build` (voices, timing, render, post, check), unchanged | `src/beekeeper/*` |

All new code lives in `src/beekeeper/factory/`. The pipeline does not know the factory
exists; the factory calls it like the CLI does.

## 3. Data (ADR 007)

Everything the factory needs to resume after a crash is in git; only the Telegram offset
and cache files are local.

```
factory/
  queue.yaml        ideas in order: id, title, source (verbatim text or story file), added
  slots.yaml        one entry per release slot that has started: date, idea id, episode,
                    state, timestamps (asked, script_sent, accepted, built, handed_off),
                    Telegram message ids of the script and reel messages
bible/              as today; stories land here verbatim (bible/README.md)
episodes/<nnn>-<slug>/episode.yaml   the script, cover and post (ADR 001)
work/factory/       local only: Telegram offset, downloaded voice notes, job log
out/<episode>/      local only: wavs, timelines, reels (as today)
```

### Slot lifecycle

```
free ──(idea at the head of the queue)──▶ planned
planned ──T-3d 02:00──▶ scripted ──07:00──▶ sent ◀──edits── (each edit: new UA, new DE, resent)
sent ──"погоджую" or T-1d 07:00──▶ accepted ──build──▶ built ──handoff──▶ handed_off
handed_off ──release_at passed──▶ released
"стоп" in sent/accepted/built/handed_off ──▶ stopped (release deleted, idea back to the queue head)
any step fails ──▶ same state + an alert to Volodymyr; the clock retries on its next tick
```

Before a slot is `planned`: at T-5d with an empty queue the bot asks for an idea; at T-4d
20:00 with no answer the factory takes one from the reserves and says which (F2.5, after
the MVP). The idea is bound to the slot when the script is written; until then the queue
order decides.

Rules fixed in code (T23, `factory/queue.py`, `factory/slots.py`):
- A slot is open for a new idea until its send deadline (T-3d 07:00); after that the next
  open slot is used, so he always gets the script at least two days before release.
- When the script is written the idea leaves the queue and is copied into the slot.
- A stopped slot stays used up (no surprise script for it); its idea goes back to the head
  of the queue and gets the next open slot.
- Idea ids are never reused.

## 4. Flows

**Idea in (F1).** Message -> router. Voice: download, whisper to Ukrainian text, show the
text back ("Почув так: ..."). Then one brain job: is it a story, a command, or both? A story
is saved verbatim and sorted into `bible/` (the same rules a chat session follows today) and
becomes a queue item with a short title; a command acts on the queue. Unsure: one short
question back. Commit `content: ...`, push.

**Queue (F2).** `/черга` lists position, title and release date with buttons per item
(up, first, edit, delete). Plain words ("постав про ведмедя першою") go through the brain,
which answers with a queue operation; the queue code applies it, so the brain never edits
`queue.yaml` itself.

**Script (F3).** T-3d 02:00: brain job "write episode" with the idea, `bible/`,
`docs/product.md` §4 and the T11 post rules; it writes `episode.yaml`. Then
`beekeeper validate`; on failure the brain gets the errors and tries again (up to 3 times,
then an alert). At 07:00 the bot sends UA text, DE text, cover idea and post text. An edit
(text or voice) is a brain job "apply edit": UA changed as asked, DE re-adapted, changed
German words marked in the reply. "погоджую" accepts at once; silence accepts at T-1d 07:00.

**Temp folder (F7).** Every script sent for approval is also written to
`~/Desktop/temp/<episode>-script.md` (UA, DE, cover idea, post); `mkdir -p` before every
write. Cleaning is a separate systemd user timer `beekeeper-temp-clean.timer`
(`OnCalendar=Mon 07:00 Europe/Berlin`, `Persistent=true`): if the laptop was off on Monday
morning, it runs at the next start. It does not need the factory process to be alive.

**His style (F1.4).** Every message from him (chat here, Telegram text, transcribed voice)
can carry phrases. A brain job after each conversation day adds new ones to
`voice/volodymyr.md`; all bot replies are written with that file in the prompt.

**Production (F4).** On `accepted`: `beekeeper build`, then the DE reel is sent to the chat
for a look. The UA reel stays in `out/` (archived, not sent).

**Handoff (F5, ADR 011).** Once the slot is accepted: release `reel/<episode>` with
`manifest.json` (`v: 2`, `release_at` with the Berlin offset, `ai: true`), `video.mp4`,
`cover.png`, `post_de.txt` (+ `post_threads.txt`); postpilot polls it, an optional
`project-intake` dispatch asks for an earlier scan. "стоп" before `release_at`
deletes the release. After `release_at` a stop is refused with a plain explanation.

## 5. Running on the laptop (ADR 006)

- `beekeeper factory` runs as a systemd **user** service, `Restart=always`, started at login
  (`loginctl enable-linger` so it also runs without an open session).
- Long polling needs no public address. Telegram keeps undelivered messages for 24 hours,
  so a sleeping laptop loses nothing short; the clock catches up all due deadlines on wake.
- The lid: on mains power the laptop stays awake with the lid closed
  (`HandleLidSwitchExternalPower=ignore`, decided A2).
- Claude Code login: if `claude -p` fails with an auth error, the bot says so in plain words
  and waits; nothing else breaks.
- Night jobs share the subscription limits with his daytime sessions; a script job is one
  run of a few minutes, at 02:00.

## 6. Secrets (`.env`, never in git)

| Name | For |
|------|-----|
| `FACTORY_BOT_TOKEN` | the factory's own bot (made with BotFather, free) |
| `FACTORY_CHAT_ID` | the only chat the bot serves |
| `POSTPILOT_DISPATCH_TOKEN` | fine-grained PAT: `schemchuk/postpilot`, Actions write; only for the optional `project-intake` scan |

Releases on this repo use the `gh` login that already exists on the laptop.

## 7. Testing

- Calendar, clock and slot transitions are pure functions: unit tests with a fake clock
  (DST change at the end of March and October included).
- Telegram and GitHub behind small interfaces with fakes; the brain behind an interface
  with recorded answers. CI never calls Telegram, Claude or GitHub.
- One manual end-to-end run with episode 003 is the MVP's done-condition (spec §5).

## 8. Statistics (F6, after the MVP)

Not designed yet. postpilot does not track factory items, and LinkedIn's API gives video
statistics only to approved apps. Options for that milestone: ask postpilot for snapshots
(its own process), or Volodymyr sends a screenshot and the factory reads it. Decided when
F6 starts.

## 9. Decided at the gate (2026-11-26)

- A1. The repo is already public (checked: `gh repo view` says PUBLIC). Nothing to do.
- A2. Lid setting: `HandleLidSwitchExternalPower=ignore` in a drop-in
  `/etc/systemd/logind.conf.d/lid.conf`. Done by Volodymyr on 2026-11-26 (file checked).
- A3. The factory commits content (stories, queue, scripts) to `main` by itself; code goes
  through PRs with CI.
- Added: F1.4 (his style from all channels) and F7 (scripts also to `~/Desktop/temp/`,
  emptied every Monday morning, independent of the laptop's state).
