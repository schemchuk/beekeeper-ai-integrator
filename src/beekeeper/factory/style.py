"""His style (F1.4): new phrases from Telegram go to `voice/volodymyr.md` once a day.

Every text he sends and every transcribed voice note is appended to a day log
`work/factory/said/<date>.md` (local, never committed: the repo is public). From 07:00
Berlin the clock hands every finished day (before today) to the `style` brain job, which
picks new phrases and images. The factory keeps only quotes found word for word in that
day's messages and not yet in the file, appends them under `SECTION`, commits, and tells him
which ones it saved. The day log is removed after a good run and stays for a retry otherwise.

The chat with Claude Code is the other channel: its sessions add to the same file by the
rule in `CLAUDE.md`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path

from .brain import VOICE, Brain, BrainAuthError, BrainError, Job
from .gitsync import GitSync

log = logging.getLogger("beekeeper.factory.style")

JOB = Job("style", timeout=5 * 60, voice=True)
SAID = Path("work/factory/said")
RUN_FROM = time(7, 0)  # Berlin; the phrases come with the morning, not at midnight
SECTION = "## From Telegram (added by the factory)"
SAVED = "Записав у твій словничок:\n{items}"
LOG_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("ʼ", "'")
    return re.sub(r"\s+", " ", re.sub(r"[«»\"“”„]", "", text)).strip()


class Style:
    def __init__(
        self,
        brain: Brain,
        send: Callable[[str], object] = lambda _text: None,
        root: Path = Path("."),
        git: GitSync | None = None,
    ) -> None:
        self.brain = brain
        self.send = send
        self.root = root
        self.git = git

    # --- the day log ------------------------------------------------------------------

    def record(self, text: str, now: datetime, source: str = "text") -> Path | None:
        """Append one message of his to today's log; commands like /start are skipped."""
        body = text.strip()
        if not body or body.startswith("/"):
            return None
        path = self.root / SAID / f"{now.date().isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"## {now.strftime('%H:%M')} {source}\n\n{body}\n\n")
        return path

    def days(self, now: datetime) -> list[tuple[date, Path]]:
        """Finished days with a log, oldest first."""
        folder = self.root / SAID
        if not folder.is_dir():
            return []
        found = []
        for path in folder.iterdir():
            match = LOG_NAME.match(path.name)
            if match and (day := date.fromisoformat(match.group(1))) < now.date():
                found.append((day, path))
        return sorted(found)

    # --- the daily job ----------------------------------------------------------------

    def tick(self, now: datetime) -> int:
        """Clock handler: from 07:00 learn from every finished day. Phrases saved."""
        if now.time() < RUN_FROM:
            return 0
        saved = 0
        for day, path in self.days(now):
            try:
                saved += self.learn(day, path)
            except BrainAuthError:
                raise
            except BrainError as e:  # the log stays, the next tick tries again
                log.error("style %s: %s", day, e)
                return saved
        return saved

    def learn(self, day: date, path: Path) -> int:
        said = path.read_text(encoding="utf-8")
        task = f"Day: {day.isoformat()}\n\nHis messages that day:\n\n{said.strip()}"
        answer = self.brain.ask(JOB, task)
        voice = self.root / VOICE
        known = _norm(voice.read_text(encoding="utf-8")) if voice.is_file() else ""
        heard = _norm(said)
        fresh, seen = [], set()
        for item in answer.get("phrases", []):
            quote = item["quote"].strip().strip('«»"“”„').strip()
            key = _norm(quote)
            if not key or key in seen or key in known or key not in heard:
                log.info("style %s: skip %r", day, quote)
                continue
            seen.add(key)
            fresh.append((quote, item["note"].strip()))
        if fresh:
            self.append(day, fresh)
            if self.git:
                self.git.sync(answer.get("commit") or f"voice: phrases of {day}", [str(VOICE)])
            items = "\n".join(f"«{quote}»: {note}" for quote, note in fresh)
            self.send(SAVED.format(items=items))
        path.unlink(missing_ok=True)
        return len(fresh)

    def append(self, day: date, fresh: list[tuple[str, str]]) -> None:
        voice = self.root / VOICE
        text = voice.read_text(encoding="utf-8") if voice.is_file() else "# Volodymyr's voice\n"
        text = text.rstrip() + "\n"
        if SECTION not in text:
            text += f"\n{SECTION}\n\n"
        lines = "".join(f'- "{quote}" ({note}; Telegram, {day})\n' for quote, note in fresh)
        voice.parent.mkdir(parents=True, exist_ok=True)
        tmp = voice.with_suffix(".tmp")
        tmp.write_text(text + lines, encoding="utf-8")
        tmp.replace(voice)
