"""`beekeeper factory`: the one long-running process of the factory (ADR 006).

Three loops in one process, so there is one writer of `factory/*.yaml` and no locks:

- poller (main thread): long-polls Telegram, answers quick things at once, hands the rest
  to the worker;
- worker (thread): runs jobs one at a time (whisper, Claude, build, handoff in later tasks);
  a failed job becomes a plain alert in the chat;
- clock (thread): ticks every 15 minutes and right after the laptop wakes up, and queues a
  `tick` job; deadline handlers are registered by the tasks that need them (T30-T33).

Until the router learns to sort ideas (T27), every text and voice note he sends is saved
verbatim to `voice/inbox/`, so nothing he tells the bot is lost.
"""

from __future__ import annotations

import logging
import queue
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .brain import BrainAuthError
from .calendar import BERLIN
from .telegram import Telegram, TelegramError, Update

log = logging.getLogger("beekeeper.factory")

WORK_DIR = Path("work/factory")
INBOX = Path("voice/inbox")
TICK_EVERY = 15 * 60  # seconds
CLOCK_STEP = 30  # seconds between wall-clock checks; a wake-up is noticed within this
POLL_TIMEOUT = 25  # seconds; keeps a stop request (SIGTERM) answered quickly

GREETING = (
    "Фабрика на місці. Пиши або наговорюй ідеї й побрехеньки: я все зберігаю дослівно. "
    "Сценарії, черга і ролики підтягнуться наступними кроками."
)
SAVED = "Записав дослівно. Розберу в біблію на найближчому сеансі."
SAVED_VOICE = "Голосове зберіг. Розшифрую на найближчому сеансі."


def now_berlin() -> datetime:
    return datetime.now(BERLIN)


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[], None]


class Offset:
    """The next Telegram update id to ask for, kept in `work/factory/offset` (local only)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> int | None:
        try:
            return int(self.path.read_text().strip())
        except (FileNotFoundError, ValueError):
            return None

    def save(self, value: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(f"{value}\n")
        tmp.replace(self.path)


class Factory:
    def __init__(
        self,
        bot: Telegram,
        root: Path = Path("."),
        clock: Callable[[], datetime] = now_berlin,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self.bot = bot
        self.root = root
        self.clock = clock
        self.wall = wall
        self.offset = Offset(root / WORK_DIR / "offset")
        self.jobs: queue.Queue[Job | None] = queue.Queue()
        self.stopping = threading.Event()
        self.tick_handlers: list[Callable[[datetime], None]] = []
        self._last_tick: float | None = None

    # --- incoming -------------------------------------------------------------------

    def handle(self, update: Update) -> None:
        """Quick work only: anything slow goes to the worker as a job."""
        log.info("update %s: %s", update.update_id, update.kind)
        if update.kind == "text" and update.text.strip().split("@")[0] == "/start":
            self.bot.send_message(GREETING)
        elif update.kind == "text":
            self.save_text(update)
            self.bot.send_message(SAVED)
        elif update.kind == "voice":
            self.submit(Job(f"voice {update.update_id}", lambda: self.save_voice(update)))
        elif update.kind == "button":
            self.bot.answer_button(update.callback_id, "Ця кнопка ще не працює")

    def save_text(self, update: Update) -> Path:
        stamp = self.clock().strftime("%Y-%m-%d-%H%M")
        path = self.root / INBOX / f"{stamp}-telegram-{update.update_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Telegram, {self.clock().isoformat(timespec='minutes')}\n\n"
            f"Verbatim from the factory bot (not sorted yet).\n\n{update.text}\n",
            encoding="utf-8",
        )
        log.info("saved text to %s", path)
        return path

    def save_voice(self, update: Update) -> Path:
        stamp = self.clock().strftime("%Y-%m-%d-%H%M")
        path = self.root / INBOX / f"{stamp}-telegram-{update.update_id}.ogg"
        self.bot.download(update.file_id, path)
        log.info("saved voice note to %s", path)
        self.bot.send_message(SAVED_VOICE)
        return path

    # --- worker ---------------------------------------------------------------------

    def submit(self, job: Job) -> None:
        self.jobs.put(job)

    def run_job(self, job: Job) -> None:
        log.info("job %s: start", job.name)
        try:
            job.run()
        except BrainAuthError as e:
            log.error("job %s: claude is logged out", job.name)
            self.alert(str(e))
        except Exception as e:
            log.exception("job %s failed", job.name)
            self.alert(f"Не вдалося: {job.name}. Причина: {e}. Спробую ще раз пізніше.")
        else:
            log.info("job %s: done", job.name)

    def worker(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            self.run_job(job)

    def alert(self, text: str) -> None:
        try:
            self.bot.send_message(text)
        except TelegramError:
            log.exception("could not send the alert")

    # --- clock ----------------------------------------------------------------------

    def clock_step(self) -> bool:
        """Queue a tick if 15 minutes of wall time have passed (or never ticked).

        Wall time, not a sleep counter: after a suspend the wall clock has jumped, so the
        next step after wake-up ticks at once and the handlers catch up due deadlines.
        """
        current = self.wall()
        if self._last_tick is not None and current - self._last_tick < TICK_EVERY:
            return False
        self._last_tick = current
        self.submit(Job("tick", self.tick))
        return True

    def tick(self) -> None:
        moment = self.clock()
        for handler in self.tick_handlers:
            handler(moment)

    def clock_loop(self) -> None:
        while not self.stopping.is_set():
            self.clock_step()
            self.stopping.wait(CLOCK_STEP)

    # --- poller ---------------------------------------------------------------------

    def poll_once(self, timeout: int = POLL_TIMEOUT) -> int:
        """One long poll; handles each update and saves the offset after it. Count."""
        offset = self.offset.load()
        updates, next_offset = self.bot.get_updates(offset, timeout=timeout)
        for update in updates:
            try:
                self.handle(update)
            except Exception as e:  # one bad update must not stop the bot (or loop it)
                log.exception("update %s failed", update.update_id)
                self.alert(f"Не зміг обробити повідомлення: {e}")
            self.offset.save(update.update_id + 1)
        if next_offset != offset and next_offset:
            self.offset.save(next_offset)
        return len(updates)

    def run(self) -> None:
        worker = threading.Thread(target=self.worker, name="worker", daemon=True)
        clock = threading.Thread(target=self.clock_loop, name="clock", daemon=True)
        worker.start()
        clock.start()
        log.info("factory started")
        backoff = 5
        while not self.stopping.is_set():
            try:
                self.poll_once()
                backoff = 5
            except TelegramError as e:
                # No network after a wake-up, Telegram down: wait and try again.
                log.warning("poll failed: %s; again in %s s", e, backoff)
                self.stopping.wait(backoff)
                backoff = min(backoff * 2, 300)
        self.jobs.put(None)
        worker.join(timeout=60)
        log.info("factory stopped")

    def stop(self, *_: object) -> None:
        self.stopping.set()


def main() -> int:
    from .telegram import load_config

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s: %(message)s")
    # httpx logs every request URL at INFO, and the bot token is part of the URL.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        config = load_config()
    except TelegramError as e:
        log.error("%s", e)
        return 1
    with Telegram(config) as bot:
        factory = Factory(bot)
        signal.signal(signal.SIGTERM, factory.stop)
        signal.signal(signal.SIGINT, factory.stop)
        factory.run()
    return 0
