# Running the factory bot

The factory is one process, `beekeeper factory`, run as a systemd **user** service
(ADR 006, `docs/architecture.md` §5). Secrets come from `.env` in the repo folder
(`FACTORY_BOT_TOKEN`, `FACTORY_CHAT_ID`; never in git).

## Install (once)

```zsh
cd ~/VS_Code_projects/beekeeper-ai-integrator
uv pip install -e ".[dev]"            # puts .venv/bin/beekeeper in place
mkdir -p ~/.config/systemd/user
ln -sf "$PWD/deploy/beekeeper-factory.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now beekeeper-factory
loginctl enable-linger "$USER"        # runs without an open session, starts at boot
```

## Everyday

```zsh
systemctl --user status beekeeper-factory      # running?
journalctl --user -u beekeeper-factory -f      # its log
systemctl --user restart beekeeper-factory     # after a code change
systemctl --user disable --now beekeeper-factory   # switch it off
```

`Restart=always`: if the process dies, systemd starts it again after 10 seconds.

## What it does now

- `/start` -> a greeting.
- Any text -> saved verbatim to `voice/inbox/` first ("Записав, розбираю."), then the
  intake brain job (T27, `prompts/intake.md`) decides: story, command, both, or unsure.
  - story: the factory writes it word for word to `bible/stories/<date>-telegram-<id>.md`,
    the brain adds the seed to `bible/ideas.md` (and new facts to the calendar or
    characters), the idea goes to the end of `factory/queue.yaml`; the reply says its
    place and release date;
  - command: show the queue, put an idea first, up, to a place, rename, delete;
  - unsure: one short question; his next message is read together with the first.
  Then the inbox file is removed and the factory commits `content: ...` (only `bible/` and
  `factory/`) and pushes. If sorting fails, the message stays in `voice/inbox/` for the
  next Claude session.
- Voice notes (T28, ADR 010) -> "Слухаю..." at once; the worker downloads the note to
  `work/factory/voice/` (local, never committed), local whisper (`medium`, `uk`, CPU)
  transcribes it, the bot shows "Почув так: ..." and then handles the text like a typed
  one (inbox, intake). A caption goes with the text. If whisper fails or hears nothing,
  the audio stays in `work/factory/voice/` and he gets a plain alert. `FACTORY_WHISPER_MODEL`
  in the unit environment switches the model (e.g. `large-v3`).
- `/queue` (in the bot's command menu) or "черга" / "покажи чергу" (T29) -> the queue at
  once, no brain: position, title, release date, and per idea the buttons ⬆ (up), ⏫
  (first), ✏ (new title) and 🗑 (delete, asks once more). A press redraws the same message.
  After ✏ his next message, typed or spoken, is the new title (not an idea); "відміна"
  keeps the old one; the pending edit lives in `work/factory/edit.yaml`. Every change is
  committed (`content: queue: ...`). A queue shown after a worded request gets the buttons
  too.
- The clock ticks every 15 minutes and right after a wake-up; deadline jobs hook in with
  T30-T33.
- The Telegram offset is kept in `work/factory/offset` (local), so a restart does not
  answer old messages again.

## The factory commits to `main`

The service runs from this folder and commits content to `main` by itself (A3). It commits
only while the folder is on `main`: on another branch its changes wait in the working tree
and go in with the next sync. So code work happens in a separate worktree, and this folder
stays on `main`:

```zsh
git worktree add ../bk-<task> -b feat/<task>    # work there, PR, merge
git worktree remove ../bk-<task>
git pull && systemctl --user restart beekeeper-factory   # here, after the merge
```

A rejected push is rebased on `origin/main` once and pushed again; whatever is still not
pushed goes with the clock's next tick.
