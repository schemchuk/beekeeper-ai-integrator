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
- Any text or voice note -> saved verbatim to `voice/inbox/` (text as `.md`, voice as
  `.ogg`) and confirmed in the chat. The next Claude session sorts it (CLAUDE.md). From T27
  the bot sorts ideas itself.
- The clock ticks every 15 minutes and right after a wake-up; deadline jobs hook in with
  T30-T33.
- The Telegram offset is kept in `work/factory/offset` (local), so a restart does not
  answer old messages again.
