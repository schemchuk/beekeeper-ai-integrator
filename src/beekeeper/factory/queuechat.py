"""The queue in the chat (docs/spec.md F2.2-F2.3, roadmap T29).

`/queue` (or "черга") shows the queue at once, without the brain: position, title, release
date, and a row of buttons per idea: up, first, edit, delete. A press edits the same message,
so the chat holds one live view of the queue instead of a pile of old lists.

Button data carries the idea id, not its position, so an old message never moves the wrong
idea: a gone idea is said plainly and the view is refreshed.

Delete asks once more. Edit asks for a new title; his next message (text or voice) becomes
that title and does not go to the intake. "Відміна" keeps the title.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .gitsync import GitSync
from .intake import place, show_queue
from .queue import QUEUE_FILE, Queue, load_queue, save_queue
from .slots import SLOTS_FILE, load_slots
from .store import StateError, read_yaml, write_yaml
from .telegram import Buttons

log = logging.getLogger("beekeeper.factory.queuechat")

PREFIX = "q"
EDIT_FILE = Path("work/factory/edit.yaml")
MAX_TITLE = 80
SHOW_WORDS = {"/queue", "/черга", "черга", "черга?", "покажи чергу", "чергу"}
CANCEL_WORDS = {"відміна", "скасуй", "скасувати", "не треба", "/cancel"}

ASK_TITLE = "Нова назва для «{title}»? Напиши одним рядком. «Відміна» лишить як є."
ASK_DELETE = "Викинути «{title}» з черги?"
GONE = "Цієї ідеї вже нема в черзі."
KEPT = "Лишив «{title}» як є."
DELETED = "Викинув «{title}» з черги."
BAD_TITLE = "Назва порожня, лишив «{title}» як є."


def is_show(text: str) -> bool:
    """A plain request for the queue, answered without the brain."""
    words = text.strip().lower().split("@")[0].rstrip(".!")
    return words in SHOW_WORDS


@dataclass(frozen=True)
class View:
    """What the bot shows: text, buttons, and a short toast for a pressed button."""

    text: str
    buttons: Buttons = field(default_factory=list)
    toast: str = ""


def buttons(queue: Queue) -> Buttons:
    rows = []
    for n, idea in enumerate(queue.items, 1):
        row = []
        if n > 1:
            row += [(f"⬆ {n}", f"{PREFIX}:up:{idea.id}"), (f"⏫ {n}", f"{PREFIX}:first:{idea.id}")]
        row += [(f"✏ {n}", f"{PREFIX}:edit:{idea.id}"), (f"🗑 {n}", f"{PREFIX}:del:{idea.id}")]
        rows.append(row)
    return rows


class QueueChat:
    def __init__(self, root: Path = Path("."), git: GitSync | None = None) -> None:
        self.root = root
        self.git = git or GitSync(root)

    def _load(self) -> Queue:
        return load_queue(self.root / QUEUE_FILE)

    def _save(self, queue: Queue, commit: str) -> None:
        save_queue(queue, self.root / QUEUE_FILE)
        self.git.sync(commit)

    def view(self, now: datetime, queue: Queue | None = None, note: str = "") -> View:
        queue = self._load() if queue is None else queue
        slots = load_slots(self.root / SLOTS_FILE)
        text = show_queue(queue, slots, now)
        if note:
            text = f"{note}\n\n{text}"
        return View(text, buttons(queue))

    # --- buttons --------------------------------------------------------------------

    def press(self, data: str, now: datetime) -> View:
        """One button press; the new content of the pressed message."""
        parts = data.split(":")
        if parts[0] != PREFIX:
            raise StateError(f"not a queue button: {data!r}")
        op = parts[1] if len(parts) > 1 else ""
        if op == "show":
            return self.view(now)
        try:
            idea_id = int(parts[2])
        except (IndexError, ValueError):
            raise StateError(f"broken queue button: {data!r}") from None
        queue = self._load()
        if idea_id not in queue.ids():
            return self._with(self.view(now, queue, GONE), toast=GONE)
        title = queue.get(idea_id).title

        if op == "up":
            if queue.position(idea_id) == 1:
                return self._with(self.view(now, queue), toast="Вже перша.")
            return self._change(queue.up(idea_id), idea_id, f"queue: up #{idea_id}", now)
        if op == "first":
            return self._change(queue.first(idea_id), idea_id, f"queue: first #{idea_id}", now)
        if op == "del":
            return View(
                ASK_DELETE.format(title=title),
                [[("Так, викинути", f"{PREFIX}:del!:{idea_id}"), ("Ні", f"{PREFIX}:show")]],
            )
        if op == "del!":
            queue = queue.delete(idea_id)
            self._save(queue, f"queue: delete #{idea_id}")
            note = DELETED.format(title=title)
            return self._with(self.view(now, queue, note), toast=note)
        if op == "edit":
            self.save_editing(idea_id)
            return self._with(self.view(now, queue, ASK_TITLE.format(title=title)), toast="Пиши")
        raise StateError(f"unknown queue button: {data!r}")

    def _change(self, queue: Queue, idea_id: int, commit: str, now: datetime) -> View:
        self._save(queue, commit)
        slots = load_slots(self.root / SLOTS_FILE)
        note = place(queue, slots, idea_id, now)
        return self._with(self.view(now, queue, note), toast=note)

    @staticmethod
    def _with(view: View, toast: str) -> View:
        return View(view.text, view.buttons, toast)

    # --- editing a title --------------------------------------------------------------

    def editing(self) -> int | None:
        """The id of the idea whose new title his next message is, if any."""
        value = read_yaml(self.root / EDIT_FILE).get("idea")
        return value if isinstance(value, int) else None

    def save_editing(self, idea_id: int | None) -> None:
        path = self.root / EDIT_FILE
        if idea_id is None:
            path.unlink(missing_ok=True)
        else:
            write_yaml(path, {"idea": idea_id})

    def finish_edit(self, text: str, now: datetime) -> View:
        """His message after "✏": the new title, or "відміна"."""
        idea_id = self.editing()
        self.save_editing(None)
        queue = self._load()
        if idea_id is None or idea_id not in queue.ids():
            return self.view(now, queue, GONE)
        old = queue.get(idea_id).title
        if text.strip().lower().rstrip(".!") in CANCEL_WORDS:
            return self.view(now, queue, KEPT.format(title=old))
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        title = lines[0][:MAX_TITLE].strip() if lines else ""
        if not title:
            return self.view(now, queue, BAD_TITLE.format(title=old))
        queue = queue.edit(idea_id, title=title)
        log.info("idea #%s renamed", idea_id)
        return self._change(queue, idea_id, f"queue: rename #{idea_id}", now)
