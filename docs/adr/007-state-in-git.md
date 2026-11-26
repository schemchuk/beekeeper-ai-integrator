# 007. Factory state in git: `factory/queue.yaml` and `factory/slots.yaml`

Status: ACCEPTED (Volodymyr, 2026-11-26).

## Context

The queue and each release slot's progress (sent, accepted, built, handed off) must survive
restarts and be readable. Silence-is-approval depends on knowing when a script was sent.

## Options

| Option | For | Against |
|--------|-----|---------|
| A. SQLite in `work/` | transactions | invisible in the repo, lost with the laptop, one more format |
| B. YAML in git, committed by the factory | readable, diffable, history for free, same style as `episode.yaml` and `bible/`; portfolio shows the process | many small commits |
| C. JSON in `work/` only | trivial | lost with the laptop, no history |

## Decision: B

`factory/queue.yaml` (ideas in order) and `factory/slots.yaml` (one entry per started slot,
state and timestamps, see `docs/architecture.md` §3). The slot state machine and the
deadlines are pure functions over these files and the current time. The factory commits
its content changes to `main` with `content:` messages and pushes; code changes keep the
PR + CI route. Only the Telegram offset and caches stay local in `work/factory/`.

## Consequences

- The process never has to be "remembered": restart, read the files, carry on.
- Writes are atomic (temp file + rename), then commit; a failed push is retried later.
