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

The jobs of T27 (story or command, sort into `bible/`), T30 (script) and T31 (edits) add
their files here.
