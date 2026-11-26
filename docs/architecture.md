# Architecture: the cartoon factory

Status: DRAFT for Volodymyr's approval (gate 3 of 4: interview -> spec -> **architecture**
-> tasks). Date: 2026-11-26.
Implements `docs/spec.md` (ACCEPTED 2026-11-26). New decisions: ADR 006-010 (PROPOSED).
ADR 005 is superseded by ADR 009. ADR 001-004 stay as they are (episode file, Python on CPU,
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
                            │   └─ handoff (ADR 009) ────────────────────┼──────────────▶ beekeeper-ai-
                            │  git: bible/, factory/, episodes/ -> push  │                integrator
                            └────────────────────────────────────────────┘  dispatch       (public)
                                                                             factory-intake    │
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
| Handoff | GitHub release + `factory-intake` dispatch, stop = delete release | `factory/handoff.py` |
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

**Production (F4).** On `accepted`: `beekeeper build`, then the DE reel is sent to the chat
for a look. The UA reel stays in `out/` (archived, not sent).

**Handoff (F5, ADR 009).** Right after the reel is sent: release `reel/<episode>` with four
assets, then the `factory-intake` dispatch with `release_at`. "стоп" before `release_at`
deletes the release. After `release_at` a stop is refused with a plain explanation.

## 5. Running on the laptop (ADR 006)

- `beekeeper factory` runs as a systemd **user** service, `Restart=always`, started at login
  (`loginctl enable-linger` so it also runs without an open session).
- Long polling needs no public address. Telegram keeps undelivered messages for 24 hours,
  so a sleeping laptop loses nothing short; the clock catches up all due deadlines on wake.
- The lid: `HandleLidSwitch=suspend` today (default in `/etc/systemd/logind.conf`). For night
  runs the laptop must stay awake on a closed lid, on mains power at least:
  `HandleLidSwitchExternalPower=ignore`. This is a system setting; Volodymyr decides.
- Claude Code login: if `claude -p` fails with an auth error, the bot says so in plain words
  and waits; nothing else breaks.
- Night jobs share the subscription limits with his daytime sessions; a script job is one
  run of a few minutes, at 02:00.

## 6. Secrets (`.env`, never in git)

| Name | For |
|------|-----|
| `FACTORY_BOT_TOKEN` | the factory's own bot (made with BotFather, free) |
| `FACTORY_CHAT_ID` | the only chat the bot serves |
| `POSTPILOT_DISPATCH_TOKEN` | fine-grained PAT: `schemchuk/postpilot`, Actions write |

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

## 9. Open points for Volodymyr

- A1. **The repo must be public before episode 003.** postpilot downloads the release
  without a token (`sources/factory.py`), so a private repo means no handoff. BRIEF already
  says "public with the first finished reel", and 002 is published. Proposed: make it
  public now, after a check that no secret or private file is in the history.
- A2. **The lid setting** (§5): proposed `HandleLidSwitchExternalPower=ignore`, so the
  laptop on the charger stays awake with the lid closed.
- A3. **The factory commits content to `main` by itself** (stories, queue, scripts), with
  `content:` commits; code still comes through PRs with CI. Proposed: yes.
