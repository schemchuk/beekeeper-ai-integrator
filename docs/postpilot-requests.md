# postpilot and this project

postpilot (`~/VS_Code_projects/postpilot`) is a separate project with its own process and its
own problems. Decided 2026-11-26 (`docs/interview/2026-11-26-round-4.md`): this project is
the cartoon factory with its own Telegram bot; postpilot is only the **publisher**, under our
rules R1-R4. postpilot shipped them on 2026-11-26 (ADR 024, see the review below), so
there is no fallback: the factory never publishes by itself, each project does its own job.

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
| 2026-11-26 | **Publishing rules for factory reels**: R1 post text as written, no AI rewrite; R2 `cover.png` as thumbnail on LinkedIn, IG, FB; R3 publish at the given release time; R4 machine handoff, never twice. Details: interview round 4. Replaces the separate thumbnail request. | done in code 2026-11-26: postpilot ADR 024, T26a-c (PRs #56-58); not verified live |
| 2026-11-26 | From postpilot (Volodymyr's decision): factory reels also go to **YouTube Shorts** and **TikTok**. See the section below. | proposed: postpilot ADR 026, not built yet |

The Friday GitHub post request (2026-11-26) is about postpilot's own rubric, not the
cartoons; it stays with postpilot.

## Review of postpilot ADR 024 (2026-11-26)

Read against R1-R4 in postpilot's code (`channels/factory.py`, `sources/factory.py`,
`factory-intake.yml`, `publish-reels.yml`). Verdict: it fits; the factory keeps postpilot as
its publisher and does not build its own.

| Rule | How postpilot does it | Note |
|------|-----------------------|------|
| R1 text as written | source `factory` never calls Claude or the humanizer; LinkedIn, IG, FB get `post_de.txt` plus the AI label line, Threads gets `post_threads.txt` or `post_de.txt` up to 500 chars | LinkedIn special characters are escaped; length limits (LinkedIn 3000, IG 2200, Threads 500) are checked at intake, so a too-long text fails at handoff, not at release |
| R2 cover | LinkedIn `uploadThumbnail` + PNG; IG `cover_url` + `thumb_offset=0`; FB thumbnail best effort | FB may keep frame 0, which is our cover anyway (T21) |
| R3 release time | item created APPROVED with `release_at`; `publish-reels` runs every 15 min | goes out within about 15 min of 08:00 |
| R4 machine handoff | public GitHub release `reel/<episode>` with `reel_de.mp4`, `cover_de.png`, `post_de.txt` (+ `post_threads.txt`), then `workflow_dispatch` of `factory-intake` with `{v: 1, episode, release_at, ai}`; `episode` unique, hashes checked again at publish | a fix before release replaces the item; after the first channel published, a repeat is refused. Stop = delete the release before `release_at` |

Open points:
- Not verified live: no `reel/*` release exists yet. First check with 003: intake with a
  future `release_at`, see the notice in postpilot's Telegram chat, then let it publish.
- IG `cover_url` through GitHub's redirecting download URL is untested.
- Factory items get no statistics in postpilot yet (short links, snapshots). Statistics are
  this project's scope (interview round 4); where the numbers come from is for the spec.
- Our side to build (replaces T12): render, make the release with the four assets, dispatch
  with a fine-grained PAT (postpilot repo, Actions write) kept in `.env`.

## Notice from postpilot: YouTube Shorts and TikTok (2026-11-26)

Volodymyr decided that factory reels go to two more channels. postpilot ADR 026 (PROPOSED,
`docs/decisions/026-youtube-shorts-and-tiktok.md` in postpilot) covers it. Nothing changes in the
release contract (ADR 024): same tag, same assets, same dispatch.

| Channel | What postpilot does with a factory reel |
|---------|------------------------------------------|
| YouTube Shorts (`shemchuk`) | public Short at `release_at`, category Science & Technology, `containsSyntheticMedia` from `ai`. Title: the first line of `post_de.txt` if it fits 100 chars, else its first sentence, else `Volodymyr Shemchuk · <date>`. Description: `post_de.txt` as written plus the AI label line. Cover: `cover_de.png` via `thumbnails.set`, best effort (needs channel phone verification). |
| TikTok (`@volodymyr.shemchuk`) | the app is not audited by TikTok yet. Until then the reel goes to Volodymyr's TikTok inbox as a draft at `release_at`; he finishes it in the app with the caption from the Telegram notice. After the audit: direct post at `release_at` if he picks the privacy level in the intake notice in time, otherwise again a draft. `is_aigc` from `ai`, cover = frame 0. Other channels are never held by TikTok. |

What the factory may add (optional, no change needed):
- `title_de.txt` in the release, at most 100 characters: used as the YouTube title instead of the
  rule above.
- Keep `post_de.txt` under 2200 characters if the full text should reach TikTok; longer text skips
  TikTok with a note.
