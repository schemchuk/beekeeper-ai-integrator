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


def test_logged_out_claude_is_said_plainly(tmp_path):
    from beekeeper.factory.brain import AUTH_MESSAGE, BrainAuthError

    bot = FakeBot()
    factory = make(tmp_path, bot)

    def logged_out():
        raise BrainAuthError()

    factory.run_job(Job("script 003", logged_out))
    assert bot.sent == [AUTH_MESSAGE]


class FakeIntake:
    def __init__(self, error=None):
        self.seen = []
        self.error = error

    def process(self, body, uid, now):
        self.seen.append((body, uid))
        if self.error:
            raise self.error
        return "У черзі №1."


def test_text_goes_to_intake_and_leaves_the_inbox(tmp_path):
    from beekeeper.factory.service import TAKEN

    intake = FakeIntake()
    bot = FakeBot([[text(7, "А було таке...")]])
    factory = Factory(bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake)
    factory.poll_once(timeout=0)
    assert bot.sent == [TAKEN]
    assert len(list((tmp_path / "voice/inbox").iterdir())) == 1  # safe before sorting
    drain(factory)
    assert intake.seen == [("А було таке...", 7)]
    assert bot.sent == [TAKEN, "У черзі №1."]
    assert list((tmp_path / "voice/inbox").iterdir()) == []


def test_failed_sorting_keeps_the_message(tmp_path):
    from beekeeper.factory.brain import BrainError

    intake = FakeIntake(BrainError("intake: answer off the schema"))
    bot = FakeBot([[text(7, "А було таке...")]])
    factory = Factory(bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake)
    factory.poll_once(timeout=0)
    drain(factory)
    assert "voice/inbox" in bot.sent[-1]
    (kept,) = (tmp_path / "voice/inbox").iterdir()
    assert "А було таке..." in kept.read_text(encoding="utf-8")


class FakeEars:
    def __init__(self, heard="А було таке: ведмідь заснув у вулику.", error=None):
        self.heard = heard
        self.error = error
        self.seen = []

    def transcribe(self, audio, duration=0):
        self.seen.append((audio.read_bytes(), duration))
        if self.error:
            raise self.error
        return self.heard


def voice_note(uid=8, caption=""):
    return Update(
        update_id=uid, kind="voice", message_id=uid, file_id="F1", duration=5, text=caption
    )


def test_voice_note_is_heard_shown_back_and_taken_in(tmp_path):
    from beekeeper.factory.service import LISTENING

    ears, intake = FakeEars(), FakeIntake()
    bot = FakeBot([[voice_note()]])
    factory = Factory(
        bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake, transcriber=ears
    )
    factory.poll_once(timeout=0)
    assert bot.sent == [LISTENING]  # at once; whisper runs in the worker
    drain(factory)
    assert ears.seen == [(b"OGG F1", 5)]
    assert bot.sent[1] == "Почув так: А було таке: ведмідь заснув у вулику."
    assert intake.seen == [("А було таке: ведмідь заснув у вулику.", 8)]
    assert bot.sent[2] == "У черзі №1."
    assert (tmp_path / "work/factory/voice/2026-11-26-1230-telegram-8.ogg").exists()
    assert list((tmp_path / "voice/inbox").iterdir()) == []  # sorted, so removed


def test_voice_caption_goes_with_the_text(tmp_path):
    intake = FakeIntake()
    bot = FakeBot([[voice_note(caption="це на четвер")]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=intake,
        transcriber=FakeEars("Медунко прокинувся."),
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert intake.seen == [("Медунко прокинувся.\n\nце на четвер", 8)]


def test_voice_not_heard_keeps_the_audio(tmp_path):
    from beekeeper.factory.transcribe import TranscribeError

    intake = FakeIntake()
    bot = FakeBot([[voice_note()]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=intake,
        transcriber=FakeEars(error=TranscribeError("у голосовому нічого не розчув")),
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert "нічого не розчув" in bot.sent[-1] and "work/factory/voice" in bot.sent[-1]
    assert intake.seen == []
    assert (tmp_path / "work/factory/voice/2026-11-26-1230-telegram-8.ogg").exists()


def test_voice_heard_but_not_sorted_stays_in_the_inbox(tmp_path):
    from beekeeper.factory.brain import BrainError

    bot = FakeBot([[voice_note()]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=FakeIntake(BrainError("off the schema")),
        transcriber=FakeEars(),
    )
    factory.poll_once(timeout=0)
    drain(factory)
    (kept,) = (tmp_path / "voice/inbox").iterdir()
    assert "ведмідь заснув" in kept.read_text(encoding="utf-8")
    assert "Whisper transcript" in kept.read_text(encoding="utf-8")


# --- T31: the script waiting for approval -----------------------------------------------


class FakeReview:
    def __init__(self, waiting=True):
        self.routed = []
        self.waiting_now = waiting

    def route(self, body, reply_to, now):
        self.routed.append((body, reply_to))
        if body.strip().lower().rstrip(".!") == "погоджую":
            return "Прийняв 004." if self.waiting_now else None
        if reply_to == 501:
            return ""  # an edit: the review sends the new script itself
        return None


def test_pogodzhuyu_needs_no_brain_and_no_inbox(tmp_path):
    intake, review = FakeIntake(), FakeReview()
    bot = FakeBot([[text(9, "Погоджую!")]])
    factory = Factory(
        bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake, review=review
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert bot.sent == ["Прийняв 004."]
    assert intake.seen == []
    assert not (tmp_path / "voice/inbox").exists()


def test_pogodzhuyu_with_nothing_waiting(tmp_path):
    from beekeeper.factory.review import NOTHING_OPEN

    bot = FakeBot([[text(9, "погоджую")]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=FakeIntake(),
        review=FakeReview(waiting=False),
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert bot.sent == [NOTHING_OPEN]


def test_a_reply_to_the_script_is_an_edit(tmp_path):
    from beekeeper.factory.service import TAKEN

    intake, review = FakeIntake(), FakeReview()
    edit = Update(update_id=10, kind="text", message_id=10, text="Заміни фінал.", reply_to=501)
    bot = FakeBot([[edit]])
    factory = Factory(
        bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake, review=review
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert review.routed == [("Заміни фінал.", 501)]
    assert intake.seen == []
    assert bot.sent == [TAKEN]  # nothing more: the new script came from the review
    assert list((tmp_path / "voice/inbox").iterdir()) == []


def test_other_text_still_goes_to_the_intake(tmp_path):
    intake, review = FakeIntake(), FakeReview()
    bot = FakeBot([[text(11, "А було таке...")]])
    factory = Factory(
        bot, root=tmp_path, clock=lambda: NOW, wall=FakeWall(), intake=intake, review=review
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert review.routed == [("А було таке...", None)]
    assert intake.seen == [("А було таке...", 11)]


def test_a_spoken_edit_as_a_reply(tmp_path):
    intake, review = FakeIntake(), FakeReview()
    ears = FakeEars()
    note = Update(update_id=12, kind="voice", message_id=12, file_id="F1", duration=5, reply_to=501)
    bot = FakeBot([[note]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=intake,
        transcriber=ears,
        review=review,
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert review.routed == [(ears.heard, 501)]
    assert intake.seen == []


# --- T32: "стоп" ------------------------------------------------------------------------


class FakeProduction:
    def __init__(self):
        self.stops = 0

    def stop(self, now):
        self.stops += 1
        return "Зупинив 004."


def test_stop_needs_no_brain(tmp_path):
    intake, production = FakeIntake(), FakeProduction()
    bot = FakeBot([[text(13, "Стоп!")]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=intake,
        production=production,
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert bot.sent == ["Зупинив 004."]
    assert production.stops == 1 and intake.seen == []


def test_a_spoken_stop(tmp_path):
    intake, production = FakeIntake(), FakeProduction()
    bot = FakeBot([[voice_note()]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=lambda: NOW,
        wall=FakeWall(),
        intake=intake,
        transcriber=FakeEars(heard="Стоп."),
        production=production,
    )
    factory.poll_once(timeout=0)
    drain(factory)
    assert production.stops == 1 and intake.seen == []
    assert bot.sent[-1] == "Зупинив 004."
