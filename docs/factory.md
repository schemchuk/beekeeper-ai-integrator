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

The weekly temp clean (F7.2) is a separate timer, independent of the bot:

```zsh
ln -sf "$PWD/deploy/beekeeper-temp-clean.service" "$PWD/deploy/beekeeper-temp-clean.timer" \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now beekeeper-temp-clean.timer
```

It empties `~/Desktop/temp/` every Monday 07:00 Berlin; `Persistent=true` makes it run at
the next start if the laptop was off. `beekeeper temp-clean --dry-run` lists what would go;
`systemctl --user list-timers beekeeper-temp-clean` shows the next run.

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
- The clock ticks every 15 minutes and right after a wake-up and runs the deadline jobs.
- Script (T30, `factory/script.py`, `prompts/script.md`): at T-3d 02:00 (or the first
  tick after it, while the slot is open) the head of the queue gets its release slot and
  the brain writes `episode.yaml`. The brain answers the YAML as text; the factory writes
  `episodes/<nnn>-<slug>/episode.yaml`, runs the `beekeeper validate` checks plus its own
  (id, slug, release, drawn scenes `hut`/`den`, known sfx) and gives a failing script back
  with its problems, up to 3 tries. A failed round is an alert; the next tick tries again,
  at most 3 rounds per slot (`work/factory/script-rounds.yaml`), then the idea stays in
  the queue and a Claude session is needed. A passing script binds the idea to the slot
  (`scripted`) and is committed with `episodes/`. At T-3d 07:00 (or the first tick after)
  the bot sends UA, DE, cover idea and the DE post, writes the same to
  `~/Desktop/temp/<episode>-script.md` (`mkdir -p` every time) and the slot is `sent`.
- Edits and approval (T31, `factory/review.py`, `prompts/edit.md`): while a script is
  `sent`, a "Reply" to the script message (typed or spoken) is an edit of it; any other
  message goes to the intake, whose brain may call it `edit` or `approve` (a new tale stays
  a story). An edit: the brain rewrites `episode.yaml` (UA as he says, DE re-adapted), the
  factory runs the night-script checks (up to 3 tries; a failure keeps the old script and
  says so), sends the new script with the changed German words marked `*like this*`,
  updates `~/Desktop/temp/<episode>-script.md` and commits; the slot stays `sent` and the
  new message is the one to reply to. A bare "погоджую" (also "згоден", "приймаю",
  `/approve`) accepts at once, no brain; silence: the clock accepts at T-1d 07:00 and says
  so in one line. Both commit `script accepted (...)` and the slot is `accepted`.
- Production (T32, `factory/production.py`): on the first tick after `accepted` the worker
  runs `beekeeper build episodes/<episode>` in a child process (both languages, up to
  90 min), sends the DE reel to the chat for a look (the UA reel stays in `out/`) and the
  slot is `built`; then the handoff (T33) creates `reel/<episode>` with `release_at` = the
  slot and the slot is `handed_off`; after the release time it is `released`. A failed
  build or handoff is an alert and is tried again on the next tick, 3 rounds per step
  (`work/factory/production-rounds.yaml`). While the build runs, other messages wait in
  the worker's line.
- "Стоп" (also `stop`, `/stop`, "зупини"; typed or spoken, no brain) before the release
  stops the next slot on its way out (`sent` to `handed_off`): an existing release is
  deleted with its tag, the slot is `stopped`, the idea goes back to the head of the queue.
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
