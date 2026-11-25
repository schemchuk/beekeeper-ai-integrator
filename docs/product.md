# Product description

Status: DRAFT for review by Volodymyr (2026-11-25).
Sources: `docs/interview/2026-11-25-round-{1,2,3}.md`, `BRIEF.md`, `bible/`.

## 1. What it is

An episode factory for short cartoons (9:16 Reels, 30-60 s) about Pylyp (DE: Philipp), a
beekeeper pushed by life into IT in Germany. Volodymyr feeds ideas and tall tales and
approves; the factory writes, voices, animates and hands the reel to postpilot, which
publishes it.

## 2. Why

- **Main goal:** a job "for the soul" in Germany as an automation specialist.
- **Side goal:** a growing circle of interested people, possible future business partners.
- **Fallback:** from 2029 the same factory can serve the Ukrainian market.
- The factory itself is a portfolio piece: it shows the automation he offers.

Success signal: messages, contacts and interview invitations from German owners and HR.
The episode never asks for a job. The viewer should feel an irresistible urge to find
him, and after reading his profile, to bring a jar of honey and pretzels.

## 3. Audience and channels

- German-speaking owners of small and mid-size businesses, HR, IT people.
- Main channel: LinkedIn (his largest audience). postpilot also posts to Threads,
  Instagram Reels and Facebook Reels; that reach stays as it is.
- Ukrainian reels are rendered and archived, not published (no language mix in one feed).
- YouTube Shorts: not now. After 8 weeks of LinkedIn episodes, propose a free test with the
  same German reels.

## 4. Content rules

- Irony and kind smiles in every episode, right on the edge of a foul but within common
  rules. He must never blush; Pylyp walks with a straight back and an ironic smile.
- Targets: bureaucracy, the Jobcenter, clumsy HR, everyone who keeps people from living,
  finding work, working in comfort and being happy. Satire on systems and types, never
  on real people who can be recognised.
- Pylyp is Volodymyr by implication only: never said outright. Deep, academic beekeeping
  knowledge everywhere, together with IT.
- Original characters and jokes (`bible/characters.md`), episodes follow the beekeeper's
  calendar (`bible/apiary-calendar.md`), ideas come from `bible/ideas.md` and `bible/lore/`.
- German is the production language. The German text is adapted, not translated word for
  word, so the joke works for Germans.

## 5. How Volodymyr works with it

All through the postpilot Telegram bot; he never handles files.

| Step | What happens | Deadline / default |
|------|--------------|--------------------|
| Ideas | He sends tall tales, ideas, facts (text or voice) any time. The factory sorts them into `bible/`. | none |
| Monthly plan | The factory proposes next month's episodes (title, seed, release dates). | Sent on the 20th. If no edits by the 24th, a warning: "no edits by tomorrow morning, the plan is accepted". Accepted on the 25th morning. |
| Script | Each script arrives in Ukrainian with the German production text side by side. He edits the Ukrainian; the German is updated and shown with the changed words marked, so he learns German along the way. | Sent 3 days before release. Accepted automatically on the morning of the day before release, no warning. |
| Reel | Rendered DE (published) and UA (archived). | Goes to postpilot with the AI label. |
| Stats | Overview in Telegram. | Monthly, plus on request. |

His time: up to 15 h/week at first, going down to 7 h/week.

## 6. Release rhythm

Two episodes per week from the start: Tuesday and Thursday, 08:00 Europe/Berlin
(`bible/schedule.md`). Frequency may grow later.

## 7. Statistics

Roughly like postpilot: a tracked short link per post and language, daily snapshots of
views, reactions and clicks where the networks allow it, and an overview in Telegram.
What counts most: profile visits, messages, contacts, interview invitations.

## 8. Constraints

- Machine: Ryzen 7 5700U, no NVIDIA GPU (CPU is enough so far).
- Budget: free tools first; a small budget for a Claude subscription and API is allowed.
  Ask before any spending.
- Tools agreed so far: Remotion (animation), HolosTTS (UA voices), Chatterbox and Piper
  (DE voices), Python for script, voices and timing. Rationale goes to `docs/adr/`.
- Reel output: MP4 H.264 yuv420p, 1080x1920, 30 fps, AAC 48 kHz, 3-90 s, under 20 MB.
- Licenses: MIT for code, CC BY-NC 4.0 for characters and episodes.

## 9. First version (MVP)

In: episode 002 "Медунко в сплячці" from `episode.yaml`, the German and Ukrainian reels
rendered with no manual timing or assembly, the German reel handed to postpilot.

Out of scope for the MVP: the Telegram approval flow and silent approval, the monthly plan,
statistics, automatic idea sorting from Telegram. These need postpilot changes
(`docs/postpilot-requests.md`) and come in later milestones.

## 10. Open questions

- Music: none yet, undecided.
- Pylyp's German voice: clone of Volodymyr's voice (needs a recording from him).
- How the factory and postpilot exchange scripts and reels (API, shared database, files):
  decided in an ADR together with postpilot.
