# 005. Automatic handoff of reels to postpilot

Status: SUPERSEDED by ADR 009 (2026-11-26): the factory has its own bot, so Telegram
`file_id`s cannot be shared; postpilot ADR 024 reads a GitHub release instead.
Was: ACCEPTED (Volodymyr, 2026-11-25).

## Context

Volodymyr decided on 2026-11-25 that the factory hands its reels to postpilot automatically;
postpilot distributes them by its own rules, and his manual `/work` intake stays as it is.
Facts on the postpilot side (2026-11-25):
- ADR 019 (S3 own video): videos live in Telegram, postpilot stores only the `file_id`
  (no bytes in Neon), max 20 MB, channels download via `getFile` at publish time.
- ADR 020: Ukrainian LinkedIn posts are paused; DE goes to LinkedIn, Threads, IG and FB Reels.
- All postpilot jobs run on GitHub Actions, triggered by cron-job.org via `workflow_dispatch`.
- A Telegram bot never receives its own messages, so the factory cannot "send `/work`" itself.

## Options

| Option | For | Against |
|--------|-----|---------|
| A. Keep manual `/work ai` | nothing to build | not automatic; against the decision |
| B. Factory writes rows into postpilot's Neon DB | direct | couples to postpilot's schema and migrations; DB password on the laptop |
| C. Factory uploads the reel to Telegram, then calls a postpilot workflow with the `file_id` | reuses ADR 019 storage and channels; postpilot owns its DB; one small contract | needs a new postpilot workflow and two secrets on the laptop |
| D. File host / GitHub release + webhook | no Telegram limit | new host, new secrets, more parts |

## Decision: C

1. After `check` passes (ADR 002), the factory sends the DE reel with the postpilot bot's
   `sendVideo` to Volodymyr's chat. That message is also his "reel ready" notice. The
   response gives `file_id`, `file_unique_id`, duration, width, height.
2. The factory then calls `workflow_dispatch` on a new postpilot workflow `factory-intake`
   with one JSON input (the contract, versioned):
   `{v: 1, episode: "002-medunko-v-splyachtsi", release_at: "2026-12-01T08:00:00+01:00",
   file_id, file_unique_id, duration, width, height, ai: true, post: {de, ua}}`.
3. The post text (`post.de`, `post.ua`) is written by the factory together with the script and
   approved with it (silent approval, `docs/product.md` §5), so the reel needs no second tap.
4. postpilot creates the item as approved and publishes it at `release_at` on its own
   channels; `episode` is the idempotency key (a repeated call changes nothing).
5. The UA reel is not sent; it stays in `out/` and is archived.
6. Secrets on the laptop (in `.env`, never committed): the postpilot bot token and a
   fine-grained PAT limited to the postpilot repo, Actions write.
7. No veto step between handoff and release: no Stop button (Volodymyr, 2026-11-25). The
   script approval is the last say.
8. If either call fails, the factory retries, then tells Volodymyr in Telegram; the manual
   `/work ai` stays the fallback.

## For postpilot to decide (its ADR)

- New source (S4 "factory") or S3 with a flag; scheduled publish at `release_at`
  (S3 publishes right after approval today).
- Statistics for factory items (`docs/product.md` §7).

## Consequences

- The factory and postpilot share only a small JSON contract and Telegram `file_id`s.
- Reels stay under 20 MB (already in the output contract).
- Until postpilot ships `factory-intake`, the handoff is the manual `/work ai` (MVP).
