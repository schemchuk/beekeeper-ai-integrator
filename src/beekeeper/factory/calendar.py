"""Release slots and their deadlines (docs/spec.md F2.4, F2.5, F3; architecture §3).

Pure functions, no clock of their own: callers pass `now`. All wall-clock times are
Europe/Berlin, so a deadline keeps its local hour across a DST change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
RELEASE_WEEKDAYS = (1, 3)  # Tuesday, Thursday (Monday is 0)
RELEASE_TIME = time(8, 0)


def _at(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=BERLIN)


def _require_aware(moment: datetime) -> None:
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")


def is_release_slot(moment: datetime) -> bool:
    """True if `moment` is exactly a release slot (Tue/Thu 08:00 Berlin)."""
    _require_aware(moment)
    local = moment.astimezone(BERLIN)
    on_day = local.weekday() in RELEASE_WEEKDAYS
    return on_day and local.time() == RELEASE_TIME


def release_slots(after: datetime, count: int) -> list[datetime]:
    """The next `count` release slots strictly after `after`."""
    _require_aware(after)
    if count < 0:
        raise ValueError("count must not be negative")
    slots: list[datetime] = []
    day = after.astimezone(BERLIN).date()
    while len(slots) < count:
        if day.weekday() in RELEASE_WEEKDAYS:
            slot = _at(day, RELEASE_TIME)
            if slot > after:
                slots.append(slot)
        day += timedelta(days=1)
    return slots


def next_release_slot(after: datetime) -> datetime:
    return release_slots(after, 1)[0]


@dataclass(frozen=True)
class Deadlines:
    """Every deadline of one release slot, in order."""

    ask: datetime  # T-5d 08:00: empty queue -> ask him for an idea
    ask_reply_by: datetime  # T-4d 20:00: no answer -> take one from the reserves
    script: datetime  # T-3d 02:00: write the script
    send: datetime  # T-3d 07:00: send it for approval
    accept: datetime  # T-1d 07:00: silence is approval
    release: datetime  # T 08:00: postpilot publishes

    def items(self) -> list[tuple[str, datetime]]:
        return [
            ("ask", self.ask),
            ("ask_reply_by", self.ask_reply_by),
            ("script", self.script),
            ("send", self.send),
            ("accept", self.accept),
            ("release", self.release),
        ]

    def due(self, now: datetime) -> list[str]:
        """Names of the deadlines that have come by `now` (catch-up after sleep)."""
        _require_aware(now)
        return [name for name, moment in self.items() if moment <= now]


def deadlines(release: datetime) -> Deadlines:
    if not is_release_slot(release):
        raise ValueError(f"not a release slot: {release.isoformat()}")
    day = release.astimezone(BERLIN).date()
    return Deadlines(
        ask=_at(day - timedelta(days=5), time(8, 0)),
        ask_reply_by=_at(day - timedelta(days=4), time(20, 0)),
        script=_at(day - timedelta(days=3), time(2, 0)),
        send=_at(day - timedelta(days=3), time(7, 0)),
        accept=_at(day - timedelta(days=1), time(7, 0)),
        release=_at(day, RELEASE_TIME),
    )
