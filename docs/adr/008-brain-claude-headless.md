# 008. The brain: Claude Code headless, fixed prompts, narrow tools

Status: PROPOSED (2026-11-26). Builds on interview round 4, question 2.

## Context

Four jobs need language understanding: (1) story or command, (2) sorting a story into
`bible/`, (3) writing an episode script, (4) applying his Ukrainian edits and re-adapting
the German. Decided: Claude Code headless on his subscription, no API spend.

## Decision

- Each job is one `claude -p` run with a prompt file from `prompts/` (versioned in git),
  `--output-format json`, a timeout, and `--allowedTools` limited to what the job needs:
  read anywhere in the repo; write only in `bible/` (job 2) or one `episodes/<nnn>/`
  folder (jobs 3, 4). No shell, no network, no git: the factory code commits.
- Job 1 answers with JSON only (`{kind: story|command|both|unclear, ...}`); queue
  operations are applied by the queue code, never by Claude editing YAML.
- After job 3 or 4, `beekeeper validate` must pass; the errors go back to Claude, up to 3
  tries, then an alert. A failing script is never shown to Volodymyr (F3.5).
- Buttons and slash commands skip the brain entirely, so most queue work costs nothing.

## Consequences

- Behaviour lives in readable prompt files, the same rules a chat session follows
  (`CLAUDE.md`, `bible/README.md`, `docs/product.md` §4, T11 post rules).
- An expired login stops only the brain jobs; the bot reports it.
- Tests use recorded answers; CI never runs Claude.
