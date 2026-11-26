# 006. The factory bot: one long-polling process on the laptop

Status: PROPOSED (2026-11-26).

## Context

Spec F1-F5: the factory talks to Volodymyr through its own Telegram bot, writes scripts at
night with Claude Code on his subscription, renders on the laptop's CPU (ADR 002). The
laptop is the only machine that can do voices, render and Claude Code for free.

## Options

| Option | For | Against |
|--------|-----|---------|
| A. Webhook on a free host (Cloudflare Worker), jobs on the laptop | bot answers while the laptop sleeps | two runtimes, a queue between them, the laptop still does all the work |
| B. Long polling from the laptop, one process | no public address, no host, one runtime; Telegram keeps updates 24 h | no answer while the laptop sleeps |
| C. Separate systemd timer for deadlines plus a bot process | simple pieces | two writers of the same files, needs locking |

## Decision: B

`beekeeper factory` is one systemd user service: a poller thread (updates, quick replies
like "прийняв, працюю"), a clock (every 15 min and on wake: due deadlines), and a worker
thread running one long job at a time (whisper, Claude, build, handoff). One process means
one writer of `factory/*.yaml`, so no locks. The spec's "systemd timer" becomes the internal
clock with catch-up after sleep; the effect is the same.

## Consequences

- When the laptop sleeps, the bot is silent; messages wait up to 24 h in Telegram.
- The laptop stays on and awake at night (lid setting, `docs/architecture.md` §5).
- Telegram client on `httpx` (one new dependency), no bot framework.
