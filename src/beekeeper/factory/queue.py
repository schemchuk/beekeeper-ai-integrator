"""The idea queue, `factory/queue.yaml` (docs/spec.md F2.1-F2.3, ADR 007).

Immutable values: every operation returns a new `Queue`, the caller saves it. An idea leaves
the queue when its script is written (`take`) and comes back to the head on "стоп"
(`put_back`). Ids are never reused, so a slot's idea id always means one idea.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from .store import StateError, dump_time, load_time, read_yaml, require_aware, write_yaml

QUEUE_FILE = Path("factory/queue.yaml")


@dataclass(frozen=True)
class Idea:
    id: int
    title: str
    source: str  # his verbatim text, or the path of the story file in bible/
    added: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "added": dump_time(self.added),
        }

    @classmethod
    def from_dict(cls, data: object, where: str) -> Idea:
        if not isinstance(data, dict):
            raise StateError(f"{where}: expected a mapping")
        for key in ("id", "title", "source", "added"):
            if key not in data:
                raise StateError(f"{where}: missing '{key}'")
        if not isinstance(data["id"], int) or data["id"] < 1:
            raise StateError(f"{where}: 'id' must be a positive integer")
        return cls(
            id=data["id"],
            title=_text(data["title"], f"{where}: title"),
            source=_text(data["source"], f"{where}: source"),
            added=load_time(data["added"], f"{where}: added"),
        )


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{what} must not be empty")
    return value.strip()


@dataclass(frozen=True)
class Queue:
    items: tuple[Idea, ...] = ()
    next_id: int = 1

    def __len__(self) -> int:
        return len(self.items)

    def ids(self) -> list[int]:
        return [idea.id for idea in self.items]

    def head(self) -> Idea | None:
        return self.items[0] if self.items else None

    def get(self, idea_id: int) -> Idea:
        return self.items[self._index(idea_id)]

    def position(self, idea_id: int) -> int:
        """1-based position, as the bot shows it."""
        return self._index(idea_id) + 1

    def _index(self, idea_id: int) -> int:
        for i, idea in enumerate(self.items):
            if idea.id == idea_id:
                return i
        raise StateError(f"no idea #{idea_id} in the queue")

    def add(self, title: str, source: str, now: datetime) -> tuple[Queue, Idea]:
        """A new idea at the end of the queue."""
        require_aware(now)
        idea = Idea(
            id=self.next_id,
            title=_text(title, "title"),
            source=_text(source, "source"),
            added=now,
        )
        return Queue(self.items + (idea,), self.next_id + 1), idea

    def edit(self, idea_id: int, *, title: str | None = None, source: str | None = None) -> Queue:
        if title is None and source is None:
            raise StateError("nothing to edit")
        i = self._index(idea_id)
        idea = self.items[i]
        if title is not None:
            idea = replace(idea, title=_text(title, "title"))
        if source is not None:
            idea = replace(idea, source=_text(source, "source"))
        return replace(self, items=self.items[:i] + (idea,) + self.items[i + 1 :])

    def move(self, idea_id: int, position: int) -> Queue:
        """Put the idea at a 1-based position."""
        if not 1 <= position <= len(self.items):
            raise StateError(f"position must be 1..{len(self.items)}, got {position}")
        i = self._index(idea_id)
        rest = list(self.items[:i] + self.items[i + 1 :])
        rest.insert(position - 1, self.items[i])
        return replace(self, items=tuple(rest))

    def up(self, idea_id: int) -> Queue:
        position = self.position(idea_id)
        if position == 1:
            raise StateError(f"idea #{idea_id} is already first")
        return self.move(idea_id, position - 1)

    def first(self, idea_id: int) -> Queue:
        return self.move(idea_id, 1)

    def delete(self, idea_id: int) -> Queue:
        i = self._index(idea_id)
        return replace(self, items=self.items[:i] + self.items[i + 1 :])

    def take(self, idea_id: int) -> tuple[Queue, Idea]:
        """Remove the idea because a slot's script is being written from it."""
        idea = self.get(idea_id)
        return self.delete(idea_id), idea

    def put_back(self, idea: Idea) -> Queue:
        """A stopped slot's idea goes back to the head of the queue."""
        if idea.id in self.ids():
            raise StateError(f"idea #{idea.id} is already in the queue")
        return Queue((idea,) + self.items, max(self.next_id, idea.id + 1))

    def to_dict(self) -> dict:
        return {"next_id": self.next_id, "items": [idea.to_dict() for idea in self.items]}

    @classmethod
    def from_dict(cls, data: dict, where: str = "queue") -> Queue:
        raw = data.get("items") or []
        if not isinstance(raw, list):
            raise StateError(f"{where}: 'items' must be a list")
        items = tuple(Idea.from_dict(x, f"{where}: item {n}") for n, x in enumerate(raw, 1))
        ids = [idea.id for idea in items]
        if len(set(ids)) != len(ids):
            raise StateError(f"{where}: duplicate idea ids")
        next_id = data.get("next_id", max(ids, default=0) + 1)
        if not isinstance(next_id, int) or next_id <= max(ids, default=0):
            raise StateError(f"{where}: 'next_id' must be greater than every id")
        return cls(items, next_id)


def load_queue(path: Path = QUEUE_FILE) -> Queue:
    return Queue.from_dict(read_yaml(path), str(path))


def save_queue(queue: Queue, path: Path = QUEUE_FILE) -> None:
    write_yaml(path, queue.to_dict())
