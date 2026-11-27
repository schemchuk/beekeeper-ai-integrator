"""Production and the slot after it (docs/spec.md F4, F5; roadmap T32).

A clock handler that moves an accepted slot to the release, each step safe to repeat:

- accepted -> built: `beekeeper build episodes/<episode>` (voices, timing, render, post,
  check; both languages), then the DE reel goes to the chat for a look; the UA reel stays
  in `out/` (F4.2). A failed build is an alert; the next tick tries again, at most 3 rounds.
- built -> handed_off: the release `reel/<episode>` for postpilot (T33, `factory/handoff.py`)
  with `release_at` = the slot. Failures: the same rounds and alerts.
- handed_off -> released: once the release time has passed (postpilot publishes).

"Стоп" (F4.3), any time before the release: the slot is stopped, a release that exists is
deleted, the idea goes back to the head of the queue.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from beekeeper.episode import load_cast, load_episode
from beekeeper.render import reel_path

from .gitsync import GitSync
from .handoff import GhError, GitHub, HandoffError, hand_off, tag
from .intake import when
from .queue import QUEUE_FILE, load_queue, save_queue
from .script import CAST, EPISODES, PATHS
from .slots import SLOTS_FILE, Slot, State, load_slots, save_slots
from .slots import stop as stop_slot
from .store import read_yaml, write_yaml

log = logging.getLogger("beekeeper.factory.production")

OUT = Path("out")
ROUNDS = 3  # per step and slot, one per clock tick
ROUNDS_FILE = Path("work/factory/production-rounds.yaml")
BUILD_TIMEOUT = 90 * 60  # seconds; a CPU render of both languages takes a few minutes
STOP_WORDS = {"стоп", "stop", "/stop", "зупини", "зупинити"}
STOPPABLE = (State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF)

REEL = "Ролик {number} «{title}» готовий, вийде {day} о 08:00. «Стоп» до виходу зупинить."
FAILED = "{what} {episode} не вдалося: {problem}. Спробую ще раз за чверть години ({n} з {rounds})."
GAVE_UP = "{what} {episode} так і не вдалося ({rounds} спроби): {problem}. Потрібен сеанс з Claude."
STOPPED = "Зупинив {episode}{release}. Ідея знову перша в черзі."
NOTHING_TO_STOP = "Нема чого зупиняти: жоден ролик не чекає на вихід."
STOP_FAILED = (
    "Не зміг прибрати реліз {tag}: {problem}. Слот поки не зупинив, спробуй «стоп» ще раз."
)

Build = Callable[[Path, Path], tuple[bool, str]]  # (episode folder, repo root) -> ok, detail
HandOff = Callable[[Path, datetime, datetime], str]


def is_stop(text: str) -> bool:
    return text.strip().lower().split("@")[0].strip(" .!") in STOP_WORDS


def run_build(episode: Path, root: Path) -> tuple[bool, str]:
    """`beekeeper build` in a child process, so a crash in the pipeline stays there."""
    try:
        done = subprocess.run(
            [sys.executable, "-m", "beekeeper", "build", str(episode)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"збірка не скінчилась за {BUILD_TIMEOUT // 60} хв"
    if done.returncode == 0:
        return True, ""
    lines = (done.stderr or done.stdout).strip().splitlines()
    return False, lines[-1][:300] if lines else f"код виходу {done.returncode}"


class Production:
    def __init__(
        self,
        send_video: Callable[[Path, str], int],
        alert: Callable[[str], None],
        root: Path = Path("."),
        git: GitSync | None = None,
        build: Build = run_build,
        handoff: HandOff | None = None,
        github: GitHub | None = None,
    ) -> None:
        self.send_video = send_video
        self.alert = alert
        self.root = root
        self.git = git or GitSync(root)
        self.build = build
        self.github = github or GitHub()
        self.handoff = handoff or (lambda ep, at, now: hand_off(ep, at, now, self.github))

    # --- rounds -----------------------------------------------------------------------

    def _fail(self, step: str, slot: Slot, problem: str) -> None:
        rounds = read_yaml(self.root / ROUNDS_FILE)
        key = f"{step}:{slot.release.isoformat()}"
        n = int(rounds.get(key, 0)) + 1
        write_yaml(self.root / ROUNDS_FILE, {**rounds, key: n})
        what = "Зібрати ролик" if step == "build" else "Віддати postpilot"
        template = GAVE_UP if n >= ROUNDS else FAILED
        self.alert(
            template.format(what=what, episode=slot.episode, problem=problem, n=n, rounds=ROUNDS)
        )

    def _spent(self, step: str, slot: Slot) -> bool:
        rounds = read_yaml(self.root / ROUNDS_FILE)
        return int(rounds.get(f"{step}:{slot.release.isoformat()}", 0)) >= ROUNDS

    def _advance(self, slot: Slot, to: State, now: datetime, reel: int | None = None) -> None:
        slots = load_slots(self.root / SLOTS_FILE).advance(slot.release, to, now)
        if reel is not None:
            slots = slots.set_message(slot.release, "reel", reel)
        save_slots(slots, self.root / SLOTS_FILE)
        self.git.sync(f"slot {to.value}: {slot.episode}", PATHS)
        log.info("slot %s: %s", slot.episode, to.value)

    # --- the clock handler ------------------------------------------------------------

    def tick(self, now: datetime) -> None:
        for slot in load_slots(self.root / SLOTS_FILE).items:
            if slot.state == State.ACCEPTED and not self._spent("build", slot):
                if not self.make(slot, now):
                    continue
                slot = load_slots(self.root / SLOTS_FILE).get(slot.release)
            if slot.state == State.BUILT and not self._spent("handoff", slot):
                if not self.give(slot, now):
                    continue
                slot = load_slots(self.root / SLOTS_FILE).get(slot.release)
            if slot.state == State.HANDED_OFF and now >= slot.release:
                self._advance(slot, State.RELEASED, now)

    def make(self, slot: Slot, now: datetime) -> bool:
        """accepted -> built: build, then the DE reel to the chat."""
        ok, detail = self.build(EPISODES / str(slot.episode), self.root)
        reel = reel_path(self.root / OUT / str(slot.episode), "de")
        if ok and not reel.is_file():
            ok, detail = False, f"після збірки нема {reel.relative_to(self.root)}"
        if not ok:
            log.error("build %s: %s", slot.episode, detail)
            self._fail("build", slot, detail)
            return False
        number, title = self._title(slot)
        caption = REEL.format(number=number, title=title, day=when(slot.release))
        message = self.send_video(reel, caption)
        self._advance(slot, State.BUILT, now, reel=message)
        return True

    def give(self, slot: Slot, now: datetime) -> bool:
        """built -> handed_off: the release for postpilot."""
        try:
            outcome = self.handoff(self.root / OUT / str(slot.episode), slot.release, now)
        except HandoffError as e:
            log.error("handoff %s: %s", slot.episode, e.problems)
            self._fail("handoff", slot, "; ".join(e.problems))
            return False
        log.info("handoff %s: %s", slot.episode, outcome)
        self._advance(slot, State.HANDED_OFF, now)
        return True

    def _title(self, slot: Slot) -> tuple[str, str]:
        episode = load_episode(
            self.root / EPISODES / str(slot.episode), load_cast(self.root / CAST)
        )
        return episode.id, episode.title.get("ua", "")

    # --- "стоп" -----------------------------------------------------------------------

    def stoppable(self, now: datetime) -> list[Slot]:
        slots = load_slots(self.root / SLOTS_FILE).items
        return [s for s in slots if s.state in STOPPABLE and now < s.release]

    def stop(self, now: datetime) -> str:
        """Stop the next slot on its way out; what to say."""
        waiting: Sequence[Slot] = self.stoppable(now)
        if not waiting:
            return NOTHING_TO_STOP
        slot = waiting[0]
        release = ""
        if slot.state in (State.BUILT, State.HANDED_OFF):
            try:
                gone = self.github.delete_release(tag(str(slot.episode)))
            except GhError as e:
                return STOP_FAILED.format(tag=tag(str(slot.episode)), problem=e)
            release = ", реліз прибрав" if gone else ""
        queue, slots = stop_slot(
            load_queue(self.root / QUEUE_FILE),
            load_slots(self.root / SLOTS_FILE),
            slot.release,
            now,
        )
        save_queue(queue, self.root / QUEUE_FILE)
        save_slots(slots, self.root / SLOTS_FILE)
        self.git.sync(f"slot stopped: {slot.episode}", PATHS)
        log.info("slot %s stopped", slot.episode)
        return STOPPED.format(episode=f"{slot.episode} на {when(slot.release)}", release=release)
