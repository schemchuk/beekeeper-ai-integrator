# 010. Voice notes transcribed locally with whisper

Status: ACCEPTED (Volodymyr, 2026-11-26).

## Context

Volodymyr dictates ideas and edits by voice (F1.1, F3.3), in Ukrainian with dialect words.
No paid services (N1).

## Decision

openai-whisper, already installed on the laptop (`~/.local/bin/whisper`), model `medium`,
language `uk`, CPU. The bot shows the text back before acting ("Почув так: ..."), so a bad
transcription is caught by him in one glance. The text is what gets stored verbatim; audio
files stay in `work/factory/` and are not committed.

## Consequences

- A one-minute note takes about a minute on the Ryzen 7; the bot replies "слухаю" at once.
- If `medium` proves weak on his dialect, try `large-v3` (slower) before anything paid.
