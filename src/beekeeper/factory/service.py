"""`beekeeper factory`: the one long-running process of the factory (ADR 006).

Three loops in one process, so there is one writer of `factory/*.yaml` and no locks:

- poller (main thread): long-polls Telegram, answers quick things at once, hands the rest
  to the worker;
- worker (thread): runs jobs one at a time (whisper, Claude, build, handoff in later tasks);
  a failed job becomes a plain alert in the chat;
- clock (thread): ticks every 15 minutes and right after the laptop wakes up, and queues a
  `tick` job; deadline handlers are registered by the tasks that need them (T30-T33).

Every text he sends is first saved verbatim to `voice/inbox/`, so nothing he tells the bot
is lost; then the intake job (T27) sorts it and the file is removed. If sorting fails, the
file stays for the next Claude session.

A voice note (T28, ADR 010) is downloaded to `work/factory/voice/` (never committed),
transcribed by local whisper, shown back ("Почув так: ...") and then handled like a text.

The queue in the chat (T29): `/queue` or "черга" shows it with buttons, no brain; a button
press edits that message; after "✏" his next message is the new title, not an idea.
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

from .brain import Brain, BrainAuthError, BrainError
from .calendar import BERLIN
from .gitsync import GitSync
from .intake import Intake
from .queuechat import QueueChat, View, is_show
from .telegram import Telegram, TelegramError, Update
from .transcribe import TranscribeError, Transcriber, Whisper

log = logging.getLogger("beekeeper.factory")

WORK_DIR = Path("work/factory")
INBOX = Path("voice/inbox")
AUDIO = WORK_DIR / "voice"
TICK_EVERY = 15 * 60  # seconds
CLOCK_STEP = 30  # seconds between wall-clock checks; a wake-up is noticed within this
POLL_TIMEOUT = 25  # seconds; keeps a stop request (SIGTERM) answered quickly

GREETING = (
    "Фабрика на місці. Пиши ідеї й побрехеньки: зберігаю дослівно, кладу в біблію і в "
    "чергу. /queue або «черга» покаже чергу з кнопками. Голосові теж слухаю."
)
COMMANDS = (("queue", "Черга ідей"), ("start", "Що вміє фабрика"))
SAVED = "Записав дослівно. Розберу в біблію на найближчому сеансі."
TAKEN = "Записав, розбираю."
NOT_SORTED = (
    "Не зміг розібрати: {error}. Повідомлення лежить дослівно в voice/inbox/, нічого не пропало."
)
SAVED_VOICE = "Голосове зберіг. Розшифрую на найближчому сеансі."
LISTENING = "Слухаю..."
HEARD = "Почув так: {text}"
NOT_HEARD = "Не розчув голосове: {error}. Запис лежить у work/factory/voice/, нічого не пропало."


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
        intake: Intake | None = None,
        transcriber: Transcriber | None = None,
        queue_chat: QueueChat | None = None,
    ) -> None:
        self.bot = bot
        self.queue_chat = queue_chat
        self.intake = intake
        self.transcriber = transcriber
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
        elif update.kind == "text" and self.queue_chat and is_show(update.text):
            self.submit(Job("queue", self.show_queue))
        elif update.kind == "text" and self.queue_chat and self.queue_chat.editing() is not None:
            self.submit(Job("rename", lambda: self.rename(update.text)))
        elif update.kind == "text" and self.intake:
            path = self.save_text(update.text, update.update_id)
            self.bot.send_message(TAKEN)
            self.submit(
                Job(
                    f"intake {update.update_id}",
                    lambda: self.take_in(update.text, update.update_id, path),
                )
            )
        elif update.kind == "text":
            self.save_text(update.text, update.update_id)
            self.bot.send_message(SAVED)
        elif update.kind == "voice" and self.transcriber:
            self.bot.send_message(LISTENING)
            self.submit(Job(f"voice {update.update_id}", lambda: self.hear(update)))
        elif update.kind == "voice":
            self.submit(Job(f"voice {update.update_id}", lambda: self.save_voice(update)))
        elif update.kind == "button" and self.queue_chat and update.data.startswith("q:"):
            self.submit(Job(f"button {update.data}", lambda: self.press(update)))
        elif update.kind == "button":
            self.bot.answer_button(update.callback_id, "Ця кнопка ще не працює")

    def save_text(self, body: str, uid: int, source: str = "Verbatim") -> Path:
        stamp = self.clock().strftime("%Y-%m-%d-%H%M")
        path = self.root / INBOX / f"{stamp}-telegram-{uid}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Telegram, {self.clock().isoformat(timespec='minutes')}\n\n"
            f"{source} from the factory bot (not sorted yet).\n\n{body}\n",
            encoding="utf-8",
        )
        log.info("saved text to %s", path)
        return path

    def take_in(self, body: str, uid: int, path: Path) -> None:
        assert self.intake is not None
        if self.queue_chat and self.queue_chat.editing() is not None:  # a voice note after "✏"
            self.rename(body)
            path.unlink(missing_ok=True)
            return
        try:
            reply = self.intake.process(body, uid, self.clock())
        except BrainAuthError:
            raise
        except BrainError as e:
            log.error("intake %s: %s", uid, e)
            self.alert(NOT_SORTED.format(error=e))
            return
        path.unlink(missing_ok=True)
        if self.queue_chat and getattr(self.intake, "showed", False):
            self.show(View(reply, self.queue_chat.view(self.clock()).buttons))
        else:
            self.bot.send_message(reply)

    # --- the queue in the chat (T29) --------------------------------------------------

    def show(self, view: View) -> None:
        self.bot.send_message(view.text, buttons=view.buttons or None)

    def show_queue(self) -> None:
        assert self.queue_chat is not None
        self.show(self.queue_chat.view(self.clock()))

    def rename(self, body: str) -> None:
        assert self.queue_chat is not None
        self.show(self.queue_chat.finish_edit(body, self.clock()))

    def press(self, update: Update) -> None:
        """A queue button: answer the spinner, then redraw the pressed message."""
        assert self.queue_chat is not None
        try:
            view = self.queue_chat.press(update.data, self.clock())
        except Exception:
            self.bot.answer_button(update.callback_id, "Не вийшло")
            raise
        self.bot.answer_button(update.callback_id, view.toast)
        if update.message_id is None:
            self.show(view)
            return
        try:
            self.bot.edit_message(update.message_id, view.text, view.buttons)
        except TelegramError as e:  # too old to edit, deleted: a fresh message instead
            log.warning("could not edit message %s: %s", update.message_id, e)
            self.show(view)

    def save_voice(self, update: Update) -> Path:
        stamp = self.clock().strftime("%Y-%m-%d-%H%M")
        path = self.root / INBOX / f"{stamp}-telegram-{update.update_id}.ogg"
        self.bot.download(update.file_id, path)
        log.info("saved voice note to %s", path)
        self.bot.send_message(SAVED_VOICE)
        return path

    def hear(self, update: Update) -> None:
        """Voice note -> whisper -> "Почув так: ..." -> the same way as a text."""
        assert self.transcriber is not None
        stamp = self.clock().strftime("%Y-%m-%d-%H%M")
        audio = self.root / AUDIO / f"{stamp}-telegram-{update.update_id}.ogg"
        self.bot.download(update.file_id, audio)
        log.info("saved voice note to %s", audio)
        try:
            heard = self.transcriber.transcribe(audio, update.duration)
        except TranscribeError as e:
            log.error("voice %s: %s", update.update_id, e)
            self.alert(NOT_HEARD.format(error=e))
            return
        body = f"{heard}\n\n{update.text.strip()}" if update.text.strip() else heard
        self.bot.send_message(HEARD.format(text=body))
        path = self.save_text(body, update.update_id, source=f"Whisper transcript of {audio.name}")
        if self.intake:
            self.take_in(body, update.update_id, path)
        else:
            self.bot.send_message(SAVED)

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
    root = Path(".")
    git = GitSync(root)
    with Telegram(config) as bot:
        factory = Factory(
            bot,
            root=root,
            intake=Intake(Brain(root), root, git),
            transcriber=Whisper(),
            queue_chat=QueueChat(root, git),
        )
        try:
            bot.set_commands(COMMANDS)
        except TelegramError as e:
            log.warning("command menu not set: %s", e)
        factory.tick_handlers.append(git.retry)
        signal.signal(signal.SIGTERM, factory.stop)
        signal.signal(signal.SIGINT, factory.stop)
        factory.run()
    return 0
