# postpilot and this project

postpilot (`~/VS_Code_projects/postpilot`) is a separate project with its own process and its
own problems. Decided 2026-11-26 (`docs/interview/2026-11-26-round-4.md`): this project is
the cartoon factory with its own Telegram bot; postpilot is only the **publisher**, under our
rules R1-R4. If postpilot declines them or has not shipped them by 2026-12-14, the factory
publishes by itself.

## What postpilot does for us today (checked 2026-11-26)

Reel 002 (DE) went through it and was published on 2026-11-25 on LinkedIn DE, Threads,
Instagram Reels and Facebook Reels (postpilot `docs/STATUS.md`, ADR 019, 021-023).

| It gives | Facts |
|----------|-------|
| Working accounts and tokens | LinkedIn (Videos API), Threads, Instagram and Facebook Reels, with renewal reminders |
| Video handling | takes a Telegram `file_id`, no file host; fits non-9:16 video with ffmpeg; Reels need 3-90 s; max 20 MB |
| AI label | `KI-generiertes Video / AI-generated video` line, Instagram `is_ai_generated` |
| Reliability | idempotent publishing, Retry/Skip button on failure, readable error lines (ADR 022) |
| Intake | guided `/work` in its bot: Original/AI-generated, video, then description or none (ADR 023) |

## Where it does not fit us

| Gap | Effect on us |
|-----|--------------|
| The description is rewritten: `Done` runs Claude plus the humanizer on our text | our approved post (hook, question, offer, BRIEF rules) is not posted as written |
| `No description` goes to Reels only | the only verbatim path skips LinkedIn, our main channel |
| No thumbnail upload (`uploadThumbnail: False`) | the cover rule (T21) does not reach LinkedIn; 002's dark frame got 25 impressions |
| Publishes right after Approve, no release time | Tue/Thu 08:00 needs Volodymyr's tap at that hour |
| Manual intake only | 7 steps per reel in the postpilot bot (`/work`, kind, video, description, text, Done, Approve) |
| The first run needed hotfixes and manual DB steps | it works now, but is young |

## Taken back into this project (no longer requests)

These were filed with postpilot on 2026-11-25 and are this project's own scope now:

- Telegram control channel: ideas and tall tales in, chat with Volodymyr.
- Scripts and the monthly plan: review, edit, silent approval (`docs/product.md` §5).
- Ukrainian edits flowing to the German production text.
- Statistics for the cartoons.
- The handoff contract (ADR 005, `factory-intake`): to be revisited in the architecture.

## Still asked of postpilot (publishing only)

| Date | Request | Status |
|------|---------|--------|
| 2026-11-25 | Keep the cross-network reach (LinkedIn, Threads, Instagram, Facebook Reels). | as is |
| 2026-11-25 | Manual intake stays (`/work`, AI and original videos). | as is |
| 2026-11-25 | Rework the manual intake: clear steps, hints, feedback on every press. | done: ADR 021 webhook, ADR 023 guided `/work` (T25a-b, 2026-11-26) |
| 2026-11-25 | German first; Ukrainian LinkedIn paused. | done: postpilot ADR 020 |
| 2026-11-26 | **Publishing rules for factory reels**, deadline 2026-12-14: R1 post text as written, no AI rewrite; R2 `cover.png` as thumbnail on LinkedIn, IG, FB; R3 publish at the given release time; R4 machine handoff, never twice. Details: interview round 4. Replaces the separate thumbnail request. | open |

The Friday GitHub post request (2026-11-26) is about postpilot's own rubric, not the
cartoons; it stays with postpilot.
