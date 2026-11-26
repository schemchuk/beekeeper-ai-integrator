# Architecture decisions

One file per decision. Status: PROPOSED until Volodymyr accepts it, then ACCEPTED (with date).

| # | Decision | Status |
|---|----------|--------|
| [001](001-episode-yaml-source-of-truth.md) | `episode.yaml` is the single source of an episode | ACCEPTED |
| [002](002-python-pipeline-local-cpu.md) | Python pipeline, run locally on CPU | ACCEPTED |
| [003](003-voices.md) | Voices: HolosTTS (UA), Chatterbox + Piper (DE) | ACCEPTED |
| [004](004-animation-remotion.md) | Animation and assembly with Remotion | ACCEPTED |
| [005](005-handoff-to-postpilot.md) | Automatic handoff of reels to postpilot | SUPERSEDED by 009 |
| [006](006-factory-bot-on-laptop.md) | Factory bot: one long-polling process on the laptop | ACCEPTED |
| [007](007-state-in-git.md) | Factory state in git (`factory/queue.yaml`, `slots.yaml`) | ACCEPTED |
| [008](008-brain-claude-headless.md) | Brain: Claude Code headless, fixed prompts, narrow tools | ACCEPTED |
| [009](009-handoff-by-github-release.md) | Handoff by GitHub release + `factory-intake` | ACCEPTED |
| [010](010-voice-notes-whisper.md) | Voice notes transcribed locally with whisper | ACCEPTED |
