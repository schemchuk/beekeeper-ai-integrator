# Prompts of the factory brain (ADR 008)

One brain job = one `claude -p` run = two files here:

- `<job>.md`: the instructions. The factory sends this text, then `---`, then the job's
  input (his words, the idea, the edit) on stdin.
- `<job>.schema.json`: the JSON schema of the answer. Claude answers through
  `--json-schema`, and `factory/brain.py` checks the answer again.

Tools per job are set in code (`brain.Job.writes`): every job may read the repo; only the
jobs that need it may write, and only in their folder (`bible/` or one `episodes/<nnn>/`).
No shell, network, MCP or git.

| Job | Task | Writes |
|-----|------|--------|
| `hello` | smoke test: `python -m beekeeper.factory.brain` | nothing |
| `intake` | his message: story, command, both, unsure, or (while a script waits) edit / approve; sort a story into `bible/` (T27, T31) | `bible/` (not `bible/stories/`) |
| `script` | the night script: `episode.yaml` as text (T30) | nothing (the factory writes) |
| `edit` | his edit of a sent script: the new `episode.yaml`, UA as he says, DE re-adapted (T31) | nothing (the factory writes) |
| `style` | a finished day of his Telegram messages: new phrases for `voice/volodymyr.md` (T35) | nothing (the factory appends) |

Jobs that write to him (`intake`, `script`, `edit`, `style`) get `voice/volodymyr.md` in
the prompt, between the instructions and the input (`Job.voice`).
