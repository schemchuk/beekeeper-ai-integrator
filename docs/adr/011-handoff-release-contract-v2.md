# 011. Handoff to postpilot by release contract v2

Status: ACCEPTED (Volodymyr, 2026-11-27). Supersedes ADR 009. Follows postpilot's
[publishing contract](https://github.com/schemchuk/postpilot/blob/main/docs/publishing-contract.md)
(release contract v2).

## Context

ADR 009 handed a reel over as a release with `reel_de.mp4` and `cover_de.png`, then a
`factory-intake` dispatch with `{v: 1, ...}`. postpilot replaced that with one contract for
all projects: it polls each registered project's public releases every 15 minutes and reads
everything it needs from the release itself. This project is registered in postpilot's
`config/projects.toml` as `beekeeper`: kind `reel`; channels `linkedin-de`, `threads`,
`instagram`, `facebook`, `youtube`, `tiktok`; approval `auto`; `max_per_day = 2`.

## Decision

1. **Release.** After `check` passes, the DE reel was sent to the chat and the slot is
   `accepted` (his "погоджую" or silence at T-1d 07:00), the factory creates a regular
   published release (not draft, not prerelease) on `schemchuk/beekeeper-ai-integrator`,
   tag `reel/<episode>`. `<episode>` is the episode folder name, e.g.
   `003-...`; it already matches `[a-z0-9]+(?:-[a-z0-9]+)*`, 1-80 characters.
2. **Assets**, copied into a staging folder under the contract's names:
   - `manifest.json`
   - `video.mp4` (from `out/<episode>/reel_de.mp4`)
   - `cover.png` (from `out/<episode>/cover_de.png`)
   - `post_de.txt`
   - `post_threads.txt`, only when `post_de.txt` is over 500 characters.
3. **Manifest**, exactly these keys:
   `{"v": 2, "kind": "reel", "id": "<episode>", "release_at": "<slot>", "ai": true}`.
   `release_at` is the slot in ISO 8601 with uppercase `T` and the Europe/Berlin offset,
   e.g. `2026-12-01T08:00:00+01:00`. `ai` is always `true` (the reels are AI-made).
   `channels` is left out: postpilot then uses every reel channel in the project entry,
   which Volodymyr approved there.
4. **Checks before the release**, so intake never rejects a reel: `post_de.txt` at most
   2,157 characters (2,200 minus the 43-character AI label) and 12,000 bytes;
   `post_threads.txt` at most 500 characters and 2,000 bytes; both UTF-8, not blank, no NUL;
   `video.mp4` 3-90 s and at most 100,000,000 bytes; `cover.png` a PNG of at most
   10,000,000 bytes; `release_at` from 1 hour ago to 60 days ahead.
5. **Earlier scan.** After the release the factory may dispatch
   `project-intake.yml -f project=beekeeper` on `schemchuk/postpilot`. It is optional:
   polling picks the release up within about 15 minutes. A successful dispatch does not
   mean the release was accepted; the result is in postpilot's Telegram chat.
6. **Approval is ours.** The project is `auto`, so postpilot takes the release as approved.
   The factory creates it only after the slot is `accepted`.
7. **Fix and repeat.** The same episode keeps the same tag and ID. A fix replaces the assets
   on the same release, which postpilot accepts until a channel starts publishing. After
   that the factory never touches the release again.
8. **Failure.** 3 retries with a pause, then an alert to Volodymyr in plain words.
9. **First release.** Before the project's first release (episode 003, T37) the factory asks
   Volodymyr in the chat and waits for his yes.
10. **v1 ends.** The factory never dispatches `factory-intake` (v1). Once the first v2
    release is published, v1 is gone from this project: ADR 009 stays only as history, and
    the `factory-intake` mentions go from the docs.

## Consequences

- No postpilot credential is needed for intake; the repo stays public so postpilot can
  download the assets. `POSTPILOT_DISPATCH_TOKEN` (fine-grained, `schemchuk/postpilot`,
  Actions write) is needed only for the optional earlier scan.
- The pipeline keeps its own file names (`reel_de.mp4`, `cover_de.png`); only the release
  uses the contract's names.
- Publishing goes to all six reel channels of the project entry, YouTube Shorts and a
  TikTok draft included. Narrowing that is a `channels` list in the manifest.
- **"стоп" after the handoff.** postpilot has no withdraw step: with `auto` approval the
  item is accepted at intake, and a deleted release fails at publication with a Retry/Skip
  prompt in postpilot's chat. So "стоп" before the release is created stops it cleanly;
  after it, the factory deletes the release and tells Volodymyr to press Skip in postpilot.
  A clean withdraw is a request to postpilot, if he wants one.
- The release must stay available until every channel has published (postpilot checks the
  hashes again when it downloads).
