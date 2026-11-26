# Specification: the cartoon factory

Status: ACCEPTED (Volodymyr, 2026-11-26; gate 2 of 4: interview -> **spec** -> architecture
-> tasks).
Sources: `docs/interview/2026-11-26-round-4.md` (decisions win over older docs),
`docs/product.md` (content rules, audience), `docs/postpilot-requests.md` (R1-R4, ADR 024).

Where this spec and `docs/product.md` disagree, this spec wins. `product.md` §5 (everything
through postpilot's bot) and §9 (MVP = episode 002 only) are superseded.

## 1. Scope

The factory turns Volodymyr's ideas into finished German reels and hands them to postpilot.

| The factory does | The factory does not |
|------------------|----------------------|
| idea queue, scripts, approval in its own Telegram bot | publish to any network |
| voices, animation, cover, post text, render, check | keep network tokens or apps |
| handoff to postpilot by machine (R4) | touch postpilot's code or queue |
| statistics overview for Volodymyr (later milestone) | |

Each project does its own job. postpilot publishes under R1-R4, which it has shipped
(postpilot ADR 024).

## 2. Actors

- **Volodymyr**: sends ideas, edits the queue, edits and approves scripts. Only in Telegram,
  never with files. Nothing to tap when he agrees: silence is approval at each deadline.
- **Factory bot**: the factory's own Telegram bot, talks only to Volodymyr's chat.
- **Night run**: a systemd timer on the laptop starts the factory; Claude Code runs headless
  on his subscription (no API spend). Missed runs (laptop asleep) catch up on wake.
- **postpilot**: receives the package and publishes it.

## 3. Functional requirements

### F1. Idea intake
- F1.1 He sends an idea or a tall tale to the bot as text or voice. Voice is transcribed on
  the laptop.
- F1.2 Every message is stored verbatim and sorted into `bible/` as `bible/README.md` says
  (story file, calendar, characters, ideas, voice notes).
- F1.3 A message that is a story becomes a queue item; a command ("move", "delete", "show")
  acts on the queue. When unsure, the bot asks one short question.
- F1.4 The bot learns his way of speaking from every channel: this chat, Telegram text and
  Telegram voice notes. New phrases and images go to `voice/volodymyr.md`, and the bot
  answers in his style (Ukrainian, short, with his images). He uses Telegram on the laptop
  and on the phone; nothing depends on which one.

### F2. Idea queue
- F2.1 The queue is an ordered list of ideas, each with a short title and its source text.
- F2.2 The bot shows it on request: position, title, the release date it would get.
- F2.3 He can edit a title or text, move an item, delete it, or put an item first.
- F2.4 Release dates come from the rhythm (Tue and Thu 08:00 Europe/Berlin,
  `bible/schedule.md`): the head of the queue goes to the next free release slot.
- F2.5 Empty queue: 5 days before a release slot the bot asks him for an idea. If he has not
  answered by 20:00 the next day, the factory takes one from the reserves (`bible/ideas.md`,
  unused `bible/lore/` and `bible/stories/`, fitting the season in
  `bible/apiary-calendar.md`) and tells him which one it took.

### F3. Script
- F3.1 At night, 3 days before release, the factory writes the script for the slot's idea
  into `episodes/<nnn>-<slug>/episode.yaml` (ADR 001): Ukrainian and German side by side,
  cover block, post block (T11 rules), following `docs/product.md` §4 and `bible/`.
- F3.2 In the morning the bot sends it: Ukrainian text, German text, cover idea, post text.
  The same script also goes as a file to `~/Desktop/temp/` (created if missing, every time).
- F3.3 He answers with edits in Ukrainian (text or voice). The factory updates the Ukrainian,
  re-adapts the German and shows the changed German words marked.
- F3.4 Silence is approval: the script is accepted on the morning of the day before release.
  An explicit "погоджую" accepts it at once.
- F3.5 `beekeeper validate` must pass before the script is shown; a failing script is fixed
  by the factory, not shown to him.

### F4. Production
- F4.1 After acceptance: voices, timing, Remotion render of the DE reel and the cover,
  `beekeeper check` (output contract, cover as frame 0). This is today's `beekeeper build`.
- F4.2 The UA reel is rendered and archived, not published.
- F4.3 The bot sends him the finished DE reel for a look. A "стоп" before release stops the
  handoff or withdraws it (deletes the release before `release_at`).

### F5. Handoff to postpilot (R4)
- F5.1 The factory creates the GitHub release `reel/<episode>` with `reel_de.mp4`,
  `cover_de.png`, `post_de.txt` (and `post_threads.txt` when needed).
- F5.2 It dispatches postpilot's `factory-intake` with `{v: 1, episode, release_at, ai}`.
- F5.3 Failure: retry, then a Telegram alert to him in plain words. Never a second release of
  the same episode after publishing started.

### F7. The temp folder
- F7.1 `~/Desktop/temp/` receives the scripts for approval (F3.2). If the folder is missing,
  the factory creates it before every write.
- F7.2 The folder is emptied every Monday morning (07:00 Berlin). It does not depend on the
  laptop's state or on the factory process: if the laptop was off or asleep, the cleaning
  runs at the first start after that.

### F6. Statistics (after the MVP)
- F6.1 Monthly overview in Telegram, plus on request. Source of the numbers: decided in the
  architecture (postpilot does not track factory items yet).

## 4. Non-functional requirements

- N1. Runs on the laptop (Ryzen 7 5700U, CPU only). No paid services without asking.
- N2. Secrets (bot token, GitHub PAT for postpilot Actions) in `.env`, never in git.
- N3. Every step can be rerun: same input, same output; voice cache by hash (exists).
- N4. Volodymyr's time: no more than a few messages per episode; zero when he agrees.
- N5. Code, tests, CI, ADRs in English; bot speaks Ukrainian with him.
- N6. Portfolio: README in English, short `README.de.md`; both link the cartoons and show
  the factory -> postpilot contract.

## 5. MVP (one week)

F1, F2 (without the reserves rule F2.5 if time is short), F3, F4, F5 for one episode (003),
end to end with no manual step on the factory side. Done when 003 is published by postpilot
from a factory handoff, verified live.

F7 is part of the MVP.

Later: F2.5 reserves, F6 statistics, monthly overview, scene library, music.

## 6. Success after 8 weeks (about 16 episodes)

- 16 of 16 released on time (Tue/Thu 08:00 Berlin).
- On average at least 300 LinkedIn impressions per reel (002: 34).
- At least 3 conversations about automation that started from a cartoon.

## 7. Decided at the gate (2026-11-26)

> я згоден з пропозиціями, переходь до архітектури

- Q1. The monthly plan from `product.md` §5 is dropped: the queue with release dates (F2.2)
  is the plan.
- Q2. Deadlines kept: ask 5 days ahead, answer by 20:00 the next day, script 3 days ahead,
  accepted on the morning of the day before release.
