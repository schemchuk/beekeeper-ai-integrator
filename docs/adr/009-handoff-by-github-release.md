# 009. Handoff to postpilot by GitHub release and `factory-intake`

Status: ACCEPTED (Volodymyr, 2026-11-26). Supersedes ADR 005. Matches postpilot ADR 024 (shipped
2026-11-26, review in `docs/postpilot-requests.md`).

## Context

ADR 005 chose Telegram `file_id`s; but a `file_id` belongs to one bot, and the factory now has
its own. postpilot ADR 024 instead reads a GitHub release of this repo.

## Decision

1. After `check` passes and the DE reel was sent to the chat, the factory creates the release
   `reel/<episode>` on `schemchuk/beekeeper-ai-integrator` with `reel_de.mp4`,
   `cover_de.png`, `post_de.txt` and, when the DE text is over 500 characters,
   `post_threads.txt`.
2. It dispatches `factory-intake` on `schemchuk/postpilot` with
   `{v: 1, episode, release_at, ai: true}` (`release_at` = the slot, Europe/Berlin offset).
3. Before the release it checks the texts against postpilot's limits (LinkedIn 3000,
   Instagram 2200, Threads 500), so a text never fails at intake.
4. Failure: 3 retries with a pause, then an alert in plain words. A fix before `release_at`
   replaces the release and dispatches again; after `release_at` the factory never
   creates a second release of the same episode.
5. "стоп" before `release_at` deletes the release (postpilot then skips the item).

## Consequences

- The repo is public (it is): postpilot downloads the release without a token.
- Secret: `POSTPILOT_DISPATCH_TOKEN` (fine-grained, postpilot repo, Actions write) in `.env`;
  releases use the laptop's existing `gh` login.
- No Telegram file size coupling between the bots; the 20 MB limit stays in `check`.
