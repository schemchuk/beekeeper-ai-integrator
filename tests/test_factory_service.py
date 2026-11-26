from datetime import datetime

import pytest

from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.service import GREETING, SAVED, SAVED_VOICE, TICK_EVERY, Factory, Job
from beekeeper.factory.telegram import TelegramError, Update

NOW = datetime(2026, 11, 26, 12, 30, tzinfo=BERLIN)


class FakeBot:
    def __init__(self, batches=()):
        self.batches = list(batches)
        self.sent = []
        self.answered = []
        self.asked_offsets = []
        self.fail_send = False

    def get_updates(self, offset=None, timeout=50):
        self.asked_offsets.append(offset)
        updates = self.batches.pop(0) if self.batches else []
        next_offset = max([u.update_id + 1 for u in updates], default=offset or 0)
        return updates, next_offset

    def send_message(self, text, buttons=None):
        if self.fail_send:
            raise TelegramError("sendMessage: down")
        self.sent.append(text)
        return [1]

    def answer_button(self, callback_id, text=""):
        self.answered.append((callback_id, text))

    def download(self, file_id, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"OGG " + file_id.encode())
        return target


class FakeWall:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def wall():
    return FakeWall()


def make(tmp_path, bot, wall=None):
    return Factory(bot, root=tmp_path, clock=lambda: NOW, wall=wall or FakeWall())


def drain(factory):
    while not factory.jobs.empty():
        factory.run_job(factory.jobs.get())


def text(uid, body):
    return Update(update_id=uid, kind="text", message_id=uid, text=body)


def test_start_gets_a_greeting(tmp_path):
    bot = FakeBot([[text(1, "/start")]])
    factory = make(tmp_path, bot)
    assert factory.poll_once(timeout=0) == 1
    assert bot.sent == [GREETING]
    assert not (tmp_path / "voice/inbox").exists()


def test_text_is_saved_verbatim(tmp_path):
    tale = "А було таке: ведмідь заліз у вулик і заснув."
    bot = FakeBot([[text(7, tale)]])
    factory = make(tmp_path, bot)
    factory.poll_once(timeout=0)
    (saved,) = (tmp_path / "voice/inbox").iterdir()
    assert saved.name == "2026-11-26-1230-telegram-7.md"
    assert tale in saved.read_text(encoding="utf-8")
    assert bot.sent == [SAVED]


def test_voice_is_downloaded_by_the_worker(tmp_path):
    voice = Update(update_id=8, kind="voice", message_id=8, file_id="F1", duration=5)
    bot = FakeBot([[voice]])
    factory = make(tmp_path, bot)
    factory.poll_once(timeout=0)
    assert bot.sent == []  # slow work is not done in the poller
    drain(factory)
    saved = tmp_path / "voice/inbox/2026-11-26-1230-telegram-8.ogg"
    assert saved.read_bytes() == b"OGG F1"
    assert bot.sent == [SAVED_VOICE]


def test_button_is_answered(tmp_path):
    press = Update(update_id=9, kind="button", callback_id="cb", data="q:up:1")
    bot = FakeBot([[press]])
    make(tmp_path, bot).poll_once(timeout=0)
    assert bot.answered and bot.answered[0][0] == "cb"


def test_offset_survives_a_restart(tmp_path):
    bot = FakeBot([[text(5, "/start"), text(6, "/start")]])
    make(tmp_path, bot).poll_once(timeout=0)
    assert (tmp_path / "work/factory/offset").read_text().strip() == "7"
    again = FakeBot()
    make(tmp_path, again).poll_once(timeout=0)
    assert again.asked_offsets == [7]


def test_a_failing_reply_does_not_stop_the_poller(tmp_path):
    bot = FakeBot([[text(1, "/start"), text(2, "/start")]])
    bot.fail_send = True
    factory = make(tmp_path, bot)
    assert factory.poll_once(timeout=0) == 2
    assert factory.offset.load() == 3


def test_failed_job_becomes_an_alert(tmp_path):
    bot = FakeBot()
    factory = make(tmp_path, bot)

    def broken():
        raise RuntimeError("whisper missing")

    factory.run_job(Job("voice 1", broken))
    assert len(bot.sent) == 1
    assert "voice 1" in bot.sent[0] and "whisper missing" in bot.sent[0]


def test_clock_ticks_every_15_minutes(tmp_path, wall):
    seen = []
    factory = make(tmp_path, FakeBot(), wall)
    factory.tick_handlers.append(seen.append)
    assert factory.clock_step()  # first step ticks at once
    wall.t += TICK_EVERY - 1
    assert not factory.clock_step()
    wall.t += 1
    assert factory.clock_step()
    drain(factory)
    assert seen == [NOW, NOW]


def test_clock_ticks_right_after_wake_up(tmp_path, wall):
    factory = make(tmp_path, FakeBot(), wall)
    factory.clock_step()
    wall.t += 8 * 3600  # the laptop slept all night
    assert factory.clock_step()


def test_run_stops_on_request(tmp_path):
    bot = FakeBot([[text(1, "/start")]])
    factory = make(tmp_path, bot)
    original = bot.get_updates

    def poll_then_stop(offset=None, timeout=50):
        result = original(offset, timeout)
        factory.stop()
        return result

    bot.get_updates = poll_then_stop
    factory.run()
    assert bot.sent[0] == GREETING


def test_main_keeps_the_token_out_of_the_log(monkeypatch):
    import logging

    from beekeeper.factory import service

    monkeypatch.setattr(
        "beekeeper.factory.telegram.load_config",
        lambda: (_ for _ in ()).throw(TelegramError("FACTORY_BOT_TOKEN is not set")),
    )
    assert service.main() == 1
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
