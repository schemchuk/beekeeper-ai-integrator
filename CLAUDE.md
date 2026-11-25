# Beekeeper AI Integrator

- Talk to Volodymyr in Ukrainian. Code, comments, commits and docs in English.
- Start by reading BRIEF.md: goal, agreed decisions, TTS and video notes, output requirements.
- Conventional development flow: interview (`docs/interview/`) -> product description ->
  ADRs -> roadmap -> code. Small commits (Conventional Commits); ask before publishing
  anything, creating a GitHub repo, or spending money.
- Prefer Python for the pipeline (zsh is the user's shell; avoid bash-only tricks in docs).
- Project memory lives in the repo: `bible/` (characters, gags, episode log) and
  `voice/volodymyr.md` (his style of speech). At session start, process new files in
  `voice/inbox/`. At session end, add what you learned about his speech from the session
  itself to `voice/volodymyr.md`.
- Volodymyr drops stories and tall tales (побрехеньки) straight into the chat, often dictated
  by voice, mixed with commands. Tell them apart: a story narrates (past, memories, "а було
  таке…"), a command asks you to do something. A message can hold both. Unsure: ask one short
  question. Never ask him to use files or `voice/inbox/` himself.
- Process stories as `bible/README.md` describes (verbatim story file, calendar, characters, ideas, voice).
  Episodes follow the beekeeper's calendar (`bible/apiary-calendar.md`).
