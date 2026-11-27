"""Idea intake (docs/spec.md F1.1-F1.3, architecture §4 "Idea in").

One brain job per message decides: story, command, both, or unsure. The factory itself
writes the story verbatim to `bible/stories/` (the brain only sorts facts and the seed into
the rest of `bible/`), adds it to the queue, applies the queue command, then commits and
pushes. Unsure: one short question back; his next message is read together with the first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .brain import Brain, BrainError, Job
from .gitsync import GitSync
from .queue import QUEUE_FILE, Idea, Queue, load_queue, save_queue
from .slots import SLOTS_FILE, Slots, load_slots, release_dates
from .store import StateError, read_yaml, write_yaml

log = logging.getLogger("beekeeper.factory.intake")

JOB = Job("intake", writes=("bible",), timeout=5 * 60)
STORIES = Path("bible/stories")
PENDING_FILE = Path("work/factory/pending.yaml")
DEFAULT_QUESTION = "Це побрехенька для черги чи команда?"
WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "нд")
ENGLISH_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True)
class Pending:
    """A message the brain was unsure about, and the question it asked."""

    text: str
    question: str
    uid: int


def when(moment: datetime) -> str:
    return f"{WEEKDAYS[moment.weekday()]} {moment:%d.%m}"


def queue_lines(queue: Queue, slots: Slots, now: datetime) -> list[tuple[int, Idea, datetime]]:
    return [(n, idea, at) for n, (idea, at) in enumerate(release_dates(queue, slots, now), 1)]


def show_queue(queue: Queue, slots: Slots, now: datetime) -> str:
    lines = queue_lines(queue, slots, now)
    if not lines:
        return "Черга порожня."
    return "Черга:\n" + "\n".join(f"{n}. {idea.title}, {when(at)}" for n, idea, at in lines)


def place(queue: Queue, slots: Slots, idea_id: int, now: datetime) -> str:
    for n, idea, at in queue_lines(queue, slots, now):
        if idea.id == idea_id:
            return f"«{idea.title}»: у черзі №{n}, вийде {when(at)} о 08:00."
    return ""


class Intake:
    def __init__(self, brain: Brain, root: Path = Path("."), git: GitSync | None = None) -> None:
        self.brain = brain
        self.root = root
        self.git = git or GitSync(root)
        self.showed = False  # the last reply lists the queue: the factory adds its buttons

    # --- state ----------------------------------------------------------------------

    def load_pending(self) -> Pending | None:
        data = read_yaml(self.root / PENDING_FILE)
        if not data.get("text"):
            return None
        return Pending(str(data["text"]), str(data.get("question", "")), int(data.get("uid", 0)))

    def save_pending(self, pending: Pending | None) -> None:
        path = self.root / PENDING_FILE
        if pending is None:
            path.unlink(missing_ok=True)
        else:
            write_yaml(
                path, {"text": pending.text, "question": pending.question, "uid": pending.uid}
            )

    # --- the job --------------------------------------------------------------------

    def task(
        self,
        text: str,
        story_file: Path,
        queue: Queue,
        slots: Slots,
        now: datetime,
        pending: Pending | None,
    ) -> str:
        lines = [
            f"Today: {now:%Y-%m-%d} ({ENGLISH_DAYS[now.weekday()]})",
            f"Reserved story file: {story_file.as_posix()}",
            "",
            "Queue (id, position, title, release):",
        ]
        rows = queue_lines(queue, slots, now)
        lines += [f"  #{idea.id} at {n}: {idea.title} ({at:%Y-%m-%d})" for n, idea, at in rows]
        if not rows:
            lines.append("  (empty)")
        if pending:
            lines += ["", f'Earlier message (you asked: "{pending.question}"):', pending.text]
        lines += ["", "His message:", text]
        return "\n".join(lines)

    def process(self, text: str, uid: int, now: datetime) -> str:
        """Handle one message; the reply for the chat."""
        self.showed = False
        pending = self.load_pending()
        source_uid = pending.uid if pending else uid
        story_file = STORIES / f"{now:%Y-%m-%d}-telegram-{source_uid}.md"
        queue = load_queue(self.root / QUEUE_FILE)
        slots = load_slots(self.root / SLOTS_FILE)

        answer = self.brain.ask(JOB, self.task(text, story_file, queue, slots, now, pending))
        kind = answer["kind"]
        log.info("intake %s: %s", uid, kind)
        if kind == "unsure":
            question = (answer.get("question") or "").strip() or DEFAULT_QUESTION
            first = pending.text if pending else text
            self.save_pending(Pending(first, question, source_uid))
            return question

        replies = [answer["reply"].strip()]
        new_idea: Idea | None = None
        if kind in ("story", "both"):
            story = answer.get("story")
            if not story:
                raise BrainError("intake: a story without a title")
            self.write_story(story_file, story["title"], text, pending, now)
            queue, new_idea = queue.add(story["title"], story_file.as_posix(), now)
        if kind in ("command", "both"):
            command = answer.get("command")
            if not command:
                raise BrainError("intake: a command without an operation")
            queue, said = self.apply(command, queue, slots, new_idea, now)
            replies.append(said)
        elif new_idea:
            replies.append(place(queue, slots, new_idea.id, now))

        save_queue(queue, self.root / QUEUE_FILE)
        self.save_pending(None)
        self.git.sync(answer["commit"])
        return "\n".join(r for r in replies if r)

    def write_story(
        self, path: Path, title: str, text: str, pending: Pending | None, now: datetime
    ) -> None:
        def quote(body: str) -> str:
            return "\n".join(f"> {line}".rstrip() for line in body.strip().splitlines())

        if pending:
            body = f"{quote(pending.text)}\n\nAsked: {pending.question}\n\n{quote(text)}"
        else:
            body = quote(text)
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"# {now:%Y-%m-%d}: {title} (Volodymyr, verbatim)\n\n"
            f"Raw source from the factory bot in Telegram, {now:%Y-%m-%d %H:%M}, kept word for\n"
            "word. Facts go to `../apiary-calendar.md`, `../characters.md`, ideas to\n"
            "`../ideas.md`.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        log.info("story saved to %s", path)

    def apply(
        self, command: dict, queue: Queue, slots: Slots, new_idea: Idea | None, now: datetime
    ) -> tuple[Queue, str]:
        """Apply one queue operation from the brain; the queue and what to say about it."""
        op = command["op"]
        if op == "show":
            self.showed = True
            return queue, show_queue(queue, slots, now)
        idea_id = command.get("idea")
        if idea_id == 0 and new_idea:
            idea_id = new_idea.id
        try:
            if not isinstance(idea_id, int) or idea_id < 1:
                raise StateError("не сказано, яку ідею")
            title = queue.get(idea_id).title
            if op == "first":
                queue = queue.first(idea_id)
            elif op == "up":
                queue = queue.up(idea_id)
            elif op == "move":
                queue = queue.move(idea_id, command.get("position") or 0)
            elif op == "rename":
                queue = queue.edit(idea_id, title=command.get("title") or "")
            elif op == "delete":
                return queue.delete(idea_id), f"Викинув «{title}» з черги."
            else:
                raise StateError(f"невідома дія {op}")
        except StateError as e:
            return queue, f"З чергою не вийшло: {e}."
        return queue, place(queue, slots, idea_id, now)
