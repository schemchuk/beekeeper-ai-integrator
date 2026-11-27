"""Edits and approval of a sent script (docs/spec.md F3.3, F3.4; roadmap T31).

A script in the chat (slot `sent`) waits for him until T-1d 07:00:

- an edit, typed or spoken, in Ukrainian: the brain rewrites `episode.yaml` (the Ukrainian
  as he says, the German re-adapted, not translated), the factory runs the same checks as
  for the night script (up to 3 tries; a failure keeps the old script) and sends the new
  script with the changed German words marked `*like this*`. The slot stays `sent`, the
  new message is the one a "Reply" points to;
- "погоджую" accepts at once (`accepted`);
- silence: the clock accepts it at T-1d 07:00 and says so in one line.

Which message is an edit: a "Reply" to the script message always is; otherwise the intake
brain decides (kind `edit` or `approve`), since he also drops stories while a script waits.
A bare "погоджую" needs no brain.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from beekeeper.episode import Episode, load_cast, load_episode

from .brain import Brain, BrainAuthError, BrainError, Job
from .calendar import deadlines
from .gitsync import GitSync
from .intake import ENGLISH_DAYS, when
from .script import CAST, EPISODES, PATHS, TEMP, TRIES, message, problems, script_lines, to_temp
from .slots import SLOTS_FILE, Slot, State, load_slots, save_slots

log = logging.getLogger("beekeeper.factory.review")

JOB = Job("edit", timeout=10 * 60)
APPROVE_WORDS = {
    "погоджую",
    "погоджено",
    "погоджуюсь",
    "погоджуюся",
    "згоден",
    "приймаю",
    "/approve",
}

NOTHING_OPEN = "Зараз жоден сценарій не чекає на згоду."
ACCEPTED = "Прийняв {number} «{title}» на {day}. Далі ролик."
SILENT = "Мовчання — знак згоди: прийняв {number} «{title}» на {day}. Далі ролик."
NOT_EDITED = (
    "Правку не вніс з {tries} спроб: {problem}. Сценарій лишився як був; "
    "скажи інакше або «погоджую»."
)
DE_MARKED = "Змінені німецькі слова позначив *зірочками*."
DE_SAME = "Німецький текст не змінився."


def is_approve(text: str) -> bool:
    """A bare approval, answered without the brain."""
    words = text.strip().lower().split("@")[0].strip(" .!,)")
    return words in APPROVE_WORDS


def _tokens(lines: list[str]) -> list[str]:
    out: list[str] = []
    for n, line in enumerate(lines):
        if n:
            out.append("\n")
        out += line.split()
    return out


def mark(old: list[str], new: list[str]) -> list[str]:
    """`new` with every word that is not in `old` wrapped in `*...*` (runs of words together)."""
    a, b = _tokens(old), _tokens(new)
    changed = [False] * len(b)
    for tag, _i1, _i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                changed[j] = b[j] != "\n"
    lines: list[str] = []
    words: list[str] = []
    run: list[str] = []

    def close() -> None:
        if run:
            words.append(f"*{' '.join(run)}*")
            run.clear()

    for token, hit in zip(b, changed, strict=True):
        if token == "\n":
            close()
            lines.append(" ".join(words))
            words.clear()
        elif hit:
            run.append(token)
        else:
            close()
            words.append(token)
    close()
    lines.append(" ".join(words))
    return lines if b else []


class Review:
    def __init__(
        self,
        brain: Brain,
        send: Callable[[str], list[int]],
        root: Path = Path("."),
        git: GitSync | None = None,
        temp: Path = TEMP,
    ) -> None:
        self.brain = brain
        self.send = send
        self.root = root
        self.git = git or GitSync(root)
        self.temp = temp

    # --- which slot -------------------------------------------------------------------

    def waiting(self) -> list[Slot]:
        """Sent scripts that wait for him, the earliest release first."""
        return [s for s in load_slots(self.root / SLOTS_FILE).items if s.state == State.SENT]

    def target(self, reply_to: int | None) -> Slot | None:
        """The waiting slot whose script message he answered with "Reply"."""
        if reply_to is None:
            return None
        for slot in self.waiting():
            if slot.messages.get("script") == reply_to:
                return slot
        return None

    def pick(self, episode: str | None = None) -> Slot | None:
        waiting = self.waiting()
        if episode:
            for slot in waiting:
                if slot.episode == episode:
                    return slot
        return waiting[0] if waiting else None

    def describe(self) -> list[str]:
        """The waiting scripts for the intake brain."""
        out = []
        for slot in self.waiting():
            title = self._episode(slot).title.get("ua", "")
            out.append(f"  {slot.episode}: «{title}» ({slot.release:%Y-%m-%d})")
        return out

    def route(self, text: str, reply_to: int | None, now: datetime) -> str | None:
        """Handle the message here if it is plainly for a waiting script; None otherwise."""
        slot = self.target(reply_to)
        if is_approve(text) and (slot or self.waiting()):
            return self.approve(now, slot.episode if slot else None)
        if slot:
            return self.edit(text, now, slot.episode)
        return None

    def _episode(self, slot: Slot) -> Episode:
        return load_episode(self.root / EPISODES / str(slot.episode), load_cast(self.root / CAST))

    # --- approval ---------------------------------------------------------------------

    def _accept(self, slot: Slot, now: datetime, by: str) -> Episode:
        slots = load_slots(self.root / SLOTS_FILE).advance(slot.release, State.ACCEPTED, now)
        save_slots(slots, self.root / SLOTS_FILE)
        self.git.sync(f"script accepted ({by}): {slot.episode}", PATHS)
        log.info("script %s accepted (%s)", slot.episode, by)
        return self._episode(slot)

    def approve(self, now: datetime, episode: str | None = None) -> str:
        slot = self.pick(episode)
        if slot is None:
            return NOTHING_OPEN
        ep = self._accept(slot, now, "approved")
        return ACCEPTED.format(number=ep.id, title=ep.title.get("ua", ""), day=_day(slot))

    def tick(self, now: datetime) -> int:
        """Silence is approval: accept every waiting script whose T-1d 07:00 has come."""
        accepted = 0
        for slot in self.waiting():
            if now < deadlines(slot.release).accept:
                continue
            ep = self._accept(slot, now, "silence")
            self.send(SILENT.format(number=ep.id, title=ep.title.get("ua", ""), day=_day(slot)))
            accepted += 1
        return accepted

    # --- an edit ----------------------------------------------------------------------

    def task(self, slot: Slot, words: str, current: str, last: tuple[str, list[str]] | None):
        lines = [
            f"Episode folder: episodes/{slot.episode}/",
            f"Release: {slot.release.isoformat()} ({ENGLISH_DAYS[slot.release.weekday()]})",
            "",
            "His edit:",
            words.strip(),
            "",
            "The current episode.yaml:",
            current.rstrip(),
        ]
        if last:
            text, found = last
            lines += ["", "Your last attempt failed these checks:"]
            lines += [f"- {p}" for p in found]
            lines += ["", "Your last attempt:", text]
        return "\n".join(lines)

    def edit(self, words: str, now: datetime, episode: str | None = None) -> str:
        """Apply his edit and send the new script; what to say besides (often nothing)."""
        slot = self.pick(episode)
        if slot is None:
            return NOTHING_OPEN
        path = self.root / EPISODES / str(slot.episode) / "episode.yaml"
        current = path.read_text(encoding="utf-8")
        cast = load_cast(self.root / CAST)
        old = load_episode(path, cast)
        number, slug = str(slot.episode).split("-", 1)
        last: tuple[str, list[str]] | None = None
        found: list[str] = []
        answer: dict | None = None
        for attempt in range(1, TRIES + 1):
            try:
                answer = self.brain.ask(JOB, self.task(slot, words, current, last))
            except BrainAuthError:
                raise
            except BrainError as e:
                log.warning("edit try %s: %s", attempt, e)
                found, answer = [str(e)], None
                continue
            text = answer["yaml"]
            path.write_text(text.rstrip() + "\n", encoding="utf-8")
            found = problems(path, number, slug, slot.release, cast)
            if not found:
                break
            log.warning("edit try %s: %s problem(s)", attempt, len(found))
            path.write_text(current, encoding="utf-8")  # the old script stays until one passes
            last, answer = (text, found), None
        if answer is None:
            first = found[0] if found else "unknown"
            more = f" (і ще {len(found) - 1})" if len(found) > 1 else ""
            return NOT_EDITED.format(tries=TRIES, problem=f"{first}{more}")

        new = load_episode(path, cast)
        old_de, new_de = script_lines(old, "de"), script_lines(new, "de")
        marked = mark(old_de, new_de)
        legend = DE_SAME if old_de == new_de else DE_MARKED
        parts = [answer["reply"].strip(), legend, message(new, slot, marked, edited=True)]
        note = to_temp(self.temp, new, slot)
        if note:
            parts.append(note)
        ids = self.send("\n\n".join(p for p in parts if p))
        slots = load_slots(self.root / SLOTS_FILE)
        slots = slots.advance(slot.release, State.SENT, now)  # sent -> sent: the new script
        slots = slots.set_message(slot.release, "script", ids[0])
        save_slots(slots, self.root / SLOTS_FILE)
        self.git.sync(answer["commit"].strip() or f"script edit: {slot.episode}", PATHS)
        log.info("script %s edited", slot.episode)
        return ""


def _day(slot: Slot) -> str:
    return when(slot.release)
