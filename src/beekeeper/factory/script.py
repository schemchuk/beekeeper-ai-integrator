"""The night script and the morning message (docs/spec.md F3.1, F3.2, F3.5, F7.1; T30).

A clock handler. Two steps, each safe to repeat after a crash or a suspend:

- write (T-3d 02:00 or the first tick after it, while the slot is still open): the head of
  the queue gets its release slot, the brain writes `episode.yaml` for it, the factory
  saves it to `episodes/<nnn>-<slug>/` and runs the same checks as `beekeeper validate`
  plus what the renderer needs (scenes, sfx, id, release). A failing script goes back to
  the brain with its problems, up to 3 tries; a failed round is an alert, and the next
  tick starts another round, at most 3 rounds per slot. Only a passing script binds the
  idea to the slot (`scripted`), is committed and pushed.
- send (T-3d 07:00 or the first tick after it): UA text, DE text, cover idea and the DE
  post go to the chat, and the same script to `~/Desktop/temp/<episode>-script.md`
  (the folder is created every time). The slot becomes `sent`.

The brain returns the YAML as text and never writes files itself: the factory alone
decides where an episode lives.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from beekeeper.episode import Episode, EpisodeError, load_cast, load_episode
from beekeeper.post import post_text
from beekeeper.sfx import LIBRARY

from .brain import Brain, BrainAuthError, BrainError, Job
from .calendar import deadlines
from .gitsync import CONTENT, GitSync
from .intake import ENGLISH_DAYS, when
from .queue import QUEUE_FILE, Idea, load_queue, save_queue
from .slots import SLOTS_FILE, Slot, Slots, State, load_slots, release_dates, save_slots
from .slots import write_script as bind_script
from .store import read_yaml, write_yaml

log = logging.getLogger("beekeeper.factory.script")

JOB = Job("script", timeout=15 * 60)
TRIES = 3  # brain tries per round
ROUNDS = 3  # rounds per slot, one per clock tick
EPISODES = Path("episodes")
CAST = Path("characters/cast.yaml")
ROUNDS_FILE = Path("work/factory/script-rounds.yaml")
TEMP = Path.home() / "Desktop" / "temp"
PATHS = (*CONTENT, "episodes")
SCENES = {"hut", "den"}  # drawn in animation/src/scenes/index.tsx
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

NAMES = {
    "pylyp": ("Пилип", "Philipp"),
    "bzynka": ("Бзинька", "Bsinka"),
    "medunko": ("Медунко", "Medunko"),
    "siryi": ("Сірий", "Isegrim"),
    "koliuchka": ("Колючка", "Pieks"),
}

FAILED = (
    "Сценарій на {day} не склався з {tries} спроб: {problem}. "
    "Спробую ще раз за чверть години ({round} з {rounds})."
)
GAVE_UP = (
    "Сценарій на {day} так і не склався ({rounds} кола по {tries} спроби): {problem}. "
    "Ідея лишилась у черзі, потрібен сеанс з Claude."
)


class ScriptError(RuntimeError):
    pass


def name(who: str | None, lang: str) -> str:
    if who is None:
        return ""
    ua, de = NAMES.get(who, (who, who))
    return ua if lang == "ua" else de


def next_number(root: Path, slots: Slots) -> str:
    """The next free episode number: after every folder in `episodes/` and every slot."""
    used = [0]
    folder = root / EPISODES
    names = [p.name for p in folder.iterdir() if p.is_dir()] if folder.is_dir() else []
    names += [s.episode for s in slots.items if s.episode]
    for entry in names:
        head = entry.split("-", 1)[0]
        if head.isdigit():
            used.append(int(head))
    return f"{max(used) + 1:03d}"


def problems(path: Path, number: str, slug: str, release: datetime, cast: set[str]) -> list[str]:
    """What `beekeeper validate` says, plus what the factory and the renderer need."""
    try:
        episode = load_episode(path, cast)
    except EpisodeError as e:
        return list(e.problems)
    found = []
    if episode.id != number:
        found.append(f"id must be {number!r}, got {episode.id!r}")
    if episode.slug != slug:
        found.append(f"slug must be {slug!r}, got {episode.slug!r}")
    raw = str(episode.extra.get("release", ""))
    try:
        same = datetime.fromisoformat(raw) == release
    except ValueError:
        same = False
    if not same:
        found.append(f"release must be {release.isoformat()!r}, got {raw!r}")
    if episode.cover is None:
        found.append("cover block is required")
    if episode.post is None:
        found.append("post block is required")
    for n, line in enumerate(episode.lines, 1):
        scene = line.shot.get("scene")
        if scene and scene not in SCENES:
            found.append(f"lines[{n}]: scene {scene!r} is not drawn; use {sorted(SCENES)}")
        if line.sfx and line.sfx not in LIBRARY:
            found.append(f"lines[{n}]: unknown sfx {line.sfx!r}; known: {sorted(LIBRARY)}")
    return found


# --- the message --------------------------------------------------------------------------


def script_lines(episode: Episode, lang: str) -> list[str]:
    out = []
    for line in episode.lines:
        for shown in line.onscreen.get(lang, []):
            out.append(f"[на екрані: {shown}]" if lang == "ua" else f"[Bildschirm: {shown}]")
        if line.text.get(lang):
            out.append(f"{name(line.who, lang)}: {line.text[lang]}")
    if episode.end_card.get(lang):
        out.append(
            f"[фінал: {episode.end_card[lang]}]"
            if lang == "ua"
            else f"[Abspann: {episode.end_card[lang]}]"
        )
    return out


def cover_idea(episode: Episode) -> str:
    if episode.cover is None:
        return ""
    who = ", ".join(name(w, "ua") for w in episode.cover.who)
    monitor = episode.cover.monitor.get("ua", "").replace("\n", " / ")
    return f"{who}; на моніторі: «{monitor}»"


def message(
    episode: Episode,
    slot: Slot,
    de_lines: list[str] | None = None,
    edited: bool = False,
) -> str:
    """The script for the chat; `de_lines` replaces the German text (marked after an edit)."""
    accept = deadlines(slot.release).accept
    head = "Новий сценарій" if edited else "Сценарій"
    de = script_lines(episode, "de") if de_lines is None else de_lines
    parts = [
        f"{head} {episode.id} «{episode.title.get('ua', '')}» на {when(slot.release)} о 08:00.",
        "🇺🇦 Українською\n" + "\n".join(script_lines(episode, "ua")),
        f"🇩🇪 Deutsch: «{episode.title.get('de', '')}»\n" + "\n".join(de),
        f"Обкладинка: {cover_idea(episode)}",
        "Пост (DE):\n" + post_text(episode, "de").strip(),
        "Правки пиши відповіддю на це повідомлення, текстом або голосом. «Погоджую» приймає "
        "одразу; "
        f"якщо мовчатимеш, приймаю {when(accept)} о 07:00.",
    ]
    return "\n\n".join(parts)


def markdown(episode: Episode, slot: Slot) -> str:
    title = episode.title
    return "\n".join(
        [
            f"# {episode.id} {title.get('ua', '')} / {title.get('de', '')}",
            "",
            f"Release: {slot.release.isoformat()}. Episode folder: `episodes/{slot.episode}/`.",
            "",
            "## UA",
            "",
            *script_lines(episode, "ua"),
            "",
            "## DE",
            "",
            *script_lines(episode, "de"),
            "",
            "## Cover",
            "",
            cover_idea(episode),
            "",
            "## Post DE",
            "",
            post_text(episode, "de").strip(),
            "",
            "## Post UA",
            "",
            post_text(episode, "ua").strip(),
            "",
        ]
    )


# --- the clock handler -----------------------------------------------------------------------


class Scripts:
    def __init__(
        self,
        brain: Brain,
        send: Callable[[str], list[int]],
        alert: Callable[[str], None],
        root: Path = Path("."),
        git: GitSync | None = None,
        temp: Path = TEMP,
    ) -> None:
        self.brain = brain
        self.send = send
        self.alert = alert
        self.root = root
        self.git = git or GitSync(root)
        self.temp = temp

    def tick(self, now: datetime) -> None:
        self.write_due(now)
        self.send_due(now)

    # --- write ------------------------------------------------------------------------

    def _rounds(self) -> dict:
        return read_yaml(self.root / ROUNDS_FILE)

    def write_due(self, now: datetime) -> bool:
        """Write the script of the next slot if its night has come; True if one was written."""
        queue = load_queue(self.root / QUEUE_FILE)
        slots = load_slots(self.root / SLOTS_FILE)
        dates = release_dates(queue, slots, now)
        if not dates:
            return False
        idea, release = dates[0]
        if now < deadlines(release).script:
            return False
        key = release.isoformat()
        rounds = self._rounds()
        done = int(rounds.get(key, 0))
        if done >= ROUNDS:
            return False
        try:
            folder, commit = self.write(idea, release, slots)
        except ScriptError as e:
            done += 1
            write_yaml(self.root / ROUNDS_FILE, {**rounds, key: done})
            day = when(release)
            template = GAVE_UP if done >= ROUNDS else FAILED
            self.alert(template.format(day=day, tries=TRIES, problem=e, round=done, rounds=ROUNDS))
            return False
        slots = slots.plan(release, idea, now)
        queue, slots = bind_script(queue, slots, release, folder, now)
        save_queue(queue, self.root / QUEUE_FILE)
        save_slots(slots, self.root / SLOTS_FILE)
        rounds.pop(key, None)
        write_yaml(self.root / ROUNDS_FILE, rounds)
        self.git.sync(commit, PATHS)
        log.info("script %s written for %s", folder, key)
        return True

    def task(self, number: str, idea: Idea, release: datetime, last: tuple[str, list[str]] | None):
        lines = [
            f"Episode number: {number}",
            f"Release: {release.isoformat()} ({ENGLISH_DAYS[release.weekday()]})",
            f"Idea #{idea.id}: {idea.title}",
            f"Source: {idea.source}",
        ]
        if last:
            text, found = last
            lines += ["", "Your last attempt failed these checks:"]
            lines += [f"- {p}" for p in found]
            lines += ["", "Your last attempt:", text]
        return "\n".join(lines)

    def write(self, idea: Idea, release: datetime, slots: Slots) -> tuple[str, str]:
        """Brain -> episode.yaml -> checks, up to TRIES times; the folder name and commit."""
        number = next_number(self.root, slots)
        cast = load_cast(self.root / CAST)
        last: tuple[str, list[str]] | None = None
        found: list[str] = []
        for attempt in range(1, TRIES + 1):
            try:
                answer = self.brain.ask(JOB, self.task(number, idea, release, last))
            except BrainAuthError:
                raise
            except BrainError as e:
                log.warning("script try %s: %s", attempt, e)
                found = [str(e)]
                continue
            slug, text = answer["slug"].strip(), answer["yaml"]
            if not SLUG.match(slug):
                found = [f"slug {slug!r} must be lowercase latin words joined by '-'"]
                last = (text, found)
                continue
            folder = f"{number}-{slug}"
            target = self.root / EPISODES / folder
            if target.exists():
                found = [f"episodes/{folder} already exists; pick another slug"]
                last = (text, found)
                continue
            target.mkdir(parents=True)
            (target / "episode.yaml").write_text(text.rstrip() + "\n", encoding="utf-8")
            found = problems(target / "episode.yaml", number, slug, release, cast)
            if not found:
                return folder, answer["commit"].strip()
            log.warning("script try %s: %s problem(s)", attempt, len(found))
            shutil.rmtree(target)
            last = (text, found)
        first = found[0] if found else "unknown"
        more = f" (і ще {len(found) - 1})" if len(found) > 1 else ""
        raise ScriptError(f"{first}{more}")

    # --- send -------------------------------------------------------------------------

    def send_due(self, now: datetime) -> int:
        """Send every written script whose morning has come; how many were sent."""
        slots = load_slots(self.root / SLOTS_FILE)
        sent = 0
        for slot in slots.items:
            if slot.state != State.SCRIPTED or now < deadlines(slot.release).send:
                continue
            cast = load_cast(self.root / CAST)
            episode = load_episode(self.root / EPISODES / str(slot.episode), cast)
            text = message(episode, slot)
            note = self.to_temp(episode, slot)
            ids = self.send(text if not note else f"{text}\n\n{note}")
            slots = slots.advance(slot.release, State.SENT, now)
            slots = slots.set_message(slot.release, "script", ids[0])
            save_slots(slots, self.root / SLOTS_FILE)
            self.git.sync(f"script sent: {slot.episode}", PATHS)
            sent += 1
        return sent

    def to_temp(self, episode: Episode, slot: Slot) -> str:
        return to_temp(self.temp, episode, slot)


def to_temp(temp: Path, episode: Episode, slot: Slot) -> str:
    """Write the script to the temp folder; a note for the chat if that failed."""
    try:
        temp.mkdir(parents=True, exist_ok=True)  # every time: he cleans the folder
        path = temp / f"{slot.episode}-script.md"
        path.write_text(markdown(episode, slot), encoding="utf-8")
    except OSError as e:
        log.warning("temp copy failed: %s", e)
        return f"(Копію в {temp} не записав: {e.strerror or e}.)"
    return ""
