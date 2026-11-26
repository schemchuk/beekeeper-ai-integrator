"""Release slots and their states, `factory/slots.yaml` (architecture §3, ADR 007).

A slot is one release date (Tue/Thu 08:00 Berlin). It gets an entry here once an idea is
planned for it. Transitions are checked; a refused one raises `StateError` and changes
nothing. Like the queue, values are immutable and the caller saves the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .calendar import BERLIN, deadlines, is_release_slot, release_slots
from .queue import Idea, Queue
from .store import StateError, dump_time, load_time, read_yaml, require_aware, write_yaml

SLOTS_FILE = Path("factory/slots.yaml")


class State(StrEnum):
    PLANNED = "planned"
    SCRIPTED = "scripted"
    SENT = "sent"
    ACCEPTED = "accepted"
    BUILT = "built"
    HANDED_OFF = "handed_off"
    RELEASED = "released"
    STOPPED = "stopped"


TRANSITIONS: dict[State, frozenset[State]] = {
    State.PLANNED: frozenset({State.SCRIPTED}),
    State.SCRIPTED: frozenset({State.SENT}),
    # sent -> sent: an edit, the new script is sent again
    State.SENT: frozenset({State.SENT, State.ACCEPTED, State.STOPPED}),
    State.ACCEPTED: frozenset({State.BUILT, State.STOPPED}),
    State.BUILT: frozenset({State.HANDED_OFF, State.STOPPED}),
    State.HANDED_OFF: frozenset({State.RELEASED, State.STOPPED}),
    State.RELEASED: frozenset(),
    State.STOPPED: frozenset(),
}

MESSAGE_KINDS = ("script", "reel")


@dataclass(frozen=True)
class Slot:
    release: datetime
    state: State
    idea: Idea
    episode: str | None = None  # episodes/<episode>/, set when the script is written
    times: dict[str, datetime] = field(default_factory=dict)  # state -> when it was entered
    messages: dict[str, int] = field(default_factory=dict)  # Telegram message ids

    @property
    def bound(self) -> bool:
        """The idea is fixed to this slot (script written) or the slot is used up."""
        return self.state != State.PLANNED

    def to_dict(self) -> dict:
        out: dict = {
            "release": dump_time(self.release),
            "state": self.state.value,
            "idea": self.idea.to_dict(),
        }
        if self.episode:
            out["episode"] = self.episode
        out["times"] = {k: dump_time(v) for k, v in self.times.items()}
        if self.messages:
            out["messages"] = dict(self.messages)
        return out

    @classmethod
    def from_dict(cls, data: object, where: str) -> Slot:
        if not isinstance(data, dict):
            raise StateError(f"{where}: expected a mapping")
        for key in ("release", "state", "idea"):
            if key not in data:
                raise StateError(f"{where}: missing '{key}'")
        release = load_time(data["release"], f"{where}: release").astimezone(BERLIN)
        if not is_release_slot(release):
            raise StateError(f"{where}: {release.isoformat()} is not a release slot")
        try:
            state = State(data["state"])
        except ValueError as e:
            raise StateError(f"{where}: unknown state {data['state']!r}") from e
        times_raw = data.get("times") or {}
        messages = data.get("messages") or {}
        if not isinstance(times_raw, dict) or not isinstance(messages, dict):
            raise StateError(f"{where}: 'times' and 'messages' must be mappings")
        for kind, message_id in messages.items():
            if kind not in MESSAGE_KINDS or not isinstance(message_id, int):
                raise StateError(f"{where}: bad message entry {kind!r}: {message_id!r}")
        episode = data.get("episode")
        if state != State.PLANNED and not episode:
            raise StateError(f"{where}: state {state.value} needs 'episode'")
        return cls(
            release=release,
            state=state,
            idea=Idea.from_dict(data["idea"], f"{where}: idea"),
            episode=episode,
            times={k: load_time(v, f"{where}: times.{k}") for k, v in times_raw.items()},
            messages=dict(messages),
        )


def is_open(release: datetime, now: datetime) -> bool:
    """Can a new idea still get this slot? Only while the script can go out on time."""
    return now < deadlines(release).send


@dataclass(frozen=True)
class Slots:
    items: tuple[Slot, ...] = ()

    def find(self, release: datetime) -> Slot | None:
        for slot in self.items:
            if slot.release == release:
                return slot
        return None

    def get(self, release: datetime) -> Slot:
        slot = self.find(release)
        if slot is None:
            raise StateError(f"no slot for {release.isoformat()}")
        return slot

    def _put(self, slot: Slot) -> Slots:
        rest = [s for s in self.items if s.release != slot.release]
        return Slots(tuple(sorted(rest + [slot], key=lambda s: s.release)))

    def plan(self, release: datetime, idea: Idea, now: datetime) -> Slots:
        """free -> planned, or a planned slot gets another idea (the queue order decides)."""
        require_aware(now)
        release = release.astimezone(BERLIN)
        if not is_release_slot(release):
            raise StateError(f"{release.isoformat()} is not a release slot")
        if not is_open(release, now):
            raise StateError(f"too late to plan the slot {release.isoformat()}")
        current = self.find(release)
        if current is not None and current.bound:
            raise StateError(f"slot {release.isoformat()} is already {current.state.value}")
        return self._put(Slot(release, State.PLANNED, idea, times={"planned": now}))

    def unplan(self, release: datetime) -> Slots:
        """A planned slot becomes free again (its idea is still in the queue)."""
        slot = self.get(release)
        if slot.state != State.PLANNED:
            raise StateError(f"only a planned slot can be freed, this one is {slot.state.value}")
        return Slots(tuple(s for s in self.items if s.release != slot.release))

    def advance(
        self, release: datetime, to: State, now: datetime, *, episode: str | None = None
    ) -> Slots:
        require_aware(now)
        slot = self.get(release)
        if to not in TRANSITIONS[slot.state]:
            raise StateError(
                f"slot {release.isoformat()}: {slot.state.value} -> {to.value} refused"
            )
        if to == State.STOPPED and now >= slot.release:
            raise StateError("the release time has passed, it can no longer be stopped")
        if to == State.RELEASED and now < slot.release:
            raise StateError("the release time has not come yet")
        if to == State.SCRIPTED:
            if not episode:
                raise StateError("a scripted slot needs its episode folder name")
            slot = replace(slot, episode=episode)
        elif episode is not None:
            raise StateError("the episode is set only when the script is written")
        times = dict(slot.times)
        times[to.value] = now
        return self._put(replace(slot, state=to, times=times))

    def set_message(self, release: datetime, kind: str, message_id: int) -> Slots:
        if kind not in MESSAGE_KINDS:
            raise StateError(f"message kind must be one of {MESSAGE_KINDS}, got {kind!r}")
        slot = self.get(release)
        return self._put(replace(slot, messages={**slot.messages, kind: message_id}))

    def to_dict(self) -> dict:
        return {"slots": [slot.to_dict() for slot in self.items]}

    @classmethod
    def from_dict(cls, data: dict, where: str = "slots") -> Slots:
        raw = data.get("slots") or []
        if not isinstance(raw, list):
            raise StateError(f"{where}: 'slots' must be a list")
        items = [Slot.from_dict(x, f"{where}: slot {n}") for n, x in enumerate(raw, 1)]
        releases = [s.release for s in items]
        if len(set(releases)) != len(releases):
            raise StateError(f"{where}: two entries for the same release slot")
        return cls(tuple(sorted(items, key=lambda s: s.release)))


def write_script(
    queue: Queue, slots: Slots, release: datetime, episode: str, now: datetime
) -> tuple[Queue, Slots]:
    """planned -> scripted: the idea leaves the queue and is fixed to the slot."""
    slot = slots.get(release)
    queue, idea = queue.take(slot.idea.id)
    slots = slots._put(replace(slot, idea=idea))
    return queue, slots.advance(release, State.SCRIPTED, now, episode=episode)


def stop(queue: Queue, slots: Slots, release: datetime, now: datetime) -> tuple[Queue, Slots]:
    """Stop ("стоп"): the slot is stopped and its idea goes back to the head of the queue.

    A stopped slot stays used up; the next idea goes to the next open slot.
    """
    slots = slots.advance(release, State.STOPPED, now)
    return queue.put_back(slots.get(release).idea), slots


def release_dates(queue: Queue, slots: Slots, now: datetime) -> list[tuple[Idea, datetime]]:
    """The date each idea in the queue would get (F2.2, F2.4): the queue in order fills the
    open slots that no bound slot holds."""
    require_aware(now)
    taken = {s.release for s in slots.items if s.bound}
    out: list[tuple[Idea, datetime]] = []
    ideas = iter(queue.items)
    idea = next(ideas, None)
    after = now
    while idea is not None:
        (candidate,) = release_slots(after, 1)
        after = candidate
        if candidate in taken or not is_open(candidate, now):
            continue
        out.append((idea, candidate))
        idea = next(ideas, None)
    return out


def load_slots(path: Path = SLOTS_FILE) -> Slots:
    return Slots.from_dict(read_yaml(path), str(path))


def save_slots(slots: Slots, path: Path = SLOTS_FILE) -> None:
    write_yaml(path, slots.to_dict())
