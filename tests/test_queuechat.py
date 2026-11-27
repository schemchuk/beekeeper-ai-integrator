from datetime import datetime

import pytest

from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.queue import Queue, load_queue, save_queue
from beekeeper.factory.queuechat import GONE, QueueChat, buttons, is_show
from beekeeper.factory.service import Factory
from beekeeper.factory.store import StateError
from beekeeper.factory.telegram import Update

NOW = datetime(2026, 11, 26, 12, 30, tzinfo=BERLIN)  # Thursday


class FakeGit:
    def __init__(self):
        self.synced = []

    def sync(self, message, paths=None):
        self.synced.append(message)
        return True


def make(tmp_path, *titles):
    queue = Queue()
    for title in titles:
        queue, _ = queue.add(title, "chat", NOW)
    save_queue(queue, tmp_path / "factory/queue.yaml")
    git = FakeGit()
    return QueueChat(tmp_path, git), git


def titles(tmp_path):
    return [idea.title for idea in load_queue(tmp_path / "factory/queue.yaml").items]


def data(view):
    return [d for row in view.buttons for _, d in row]


@pytest.mark.parametrize("text", ["/queue", "/queue@bot", "Черга", "покажи чергу!", "/черга"])
def test_show_words(text):
    assert is_show(text)


@pytest.mark.parametrize("text", ["черга завтра?", "А було таке", "поміняй чергу"])
def test_not_show_words(text):
    assert not is_show(text)


def test_view_lists_ideas_with_dates_and_buttons(tmp_path):
    chat, _ = make(tmp_path, "Пошта", "Ярмарок")
    view = chat.view(NOW)
    assert view.text == "Черга:\n1. Пошта, вт 01.12\n2. Ярмарок, чт 03.12"
    # the first idea cannot go up
    assert data(view) == ["q:edit:1", "q:del:1", "q:up:2", "q:first:2", "q:edit:2", "q:del:2"]


def test_button_data_fits_telegram(tmp_path):
    queue = Queue(next_id=10**9)
    queue, _ = queue.add("Довга", "chat", NOW)
    for row in buttons(queue):
        for _, d in row:
            assert len(d.encode()) <= 64


def test_empty_queue(tmp_path):
    chat, _ = make(tmp_path)
    view = chat.view(NOW)
    assert view.text == "Черга порожня."
    assert view.buttons == []


def test_up_and_first(tmp_path):
    chat, git = make(tmp_path, "Пошта", "Ярмарок", "Рій")
    view = chat.press("q:up:3", NOW)
    assert titles(tmp_path) == ["Пошта", "Рій", "Ярмарок"]
    assert view.text.startswith("«Рій»: у черзі №2, вийде чт 03.12 о 08:00.")
    assert view.toast.startswith("«Рій»")
    chat.press("q:first:2", NOW)
    assert titles(tmp_path) == ["Ярмарок", "Пошта", "Рій"]
    assert git.synced == ["queue: up #3", "queue: first #2"]


def test_up_on_the_first_changes_nothing(tmp_path):
    chat, git = make(tmp_path, "Пошта", "Ярмарок")
    view = chat.press("q:up:1", NOW)
    assert view.toast == "Вже перша."
    assert titles(tmp_path) == ["Пошта", "Ярмарок"]
    assert git.synced == []


def test_delete_asks_first(tmp_path):
    chat, git = make(tmp_path, "Пошта", "Ярмарок")
    ask = chat.press("q:del:1", NOW)
    assert ask.text == "Викинути «Пошта» з черги?"
    assert data(ask) == ["q:del!:1", "q:show"]
    assert titles(tmp_path) == ["Пошта", "Ярмарок"]
    back = chat.press("q:show", NOW)
    assert back.text.startswith("Черга:")
    done = chat.press("q:del!:1", NOW)
    assert titles(tmp_path) == ["Ярмарок"]
    assert done.text.startswith("Викинув «Пошта» з черги.")
    assert git.synced == ["queue: delete #1"]


def test_old_button_of_a_gone_idea(tmp_path):
    chat, git = make(tmp_path, "Пошта")
    view = chat.press("q:first:7", NOW)
    assert view.toast == GONE
    assert view.text.startswith(GONE)
    assert git.synced == []


def test_broken_button(tmp_path):
    chat, _ = make(tmp_path, "Пошта")
    with pytest.raises(StateError):
        chat.press("q:up:x", NOW)
    with pytest.raises(StateError):
        chat.press("q:fly:1", NOW)


def test_edit_takes_the_next_message_as_title(tmp_path):
    chat, git = make(tmp_path, "Пошта", "Ярмарок")
    ask = chat.press("q:edit:2", NOW)
    assert "Нова назва для «Ярмарок»?" in ask.text
    assert chat.editing() == 2
    view = chat.finish_edit("Ярмарок у Пирятині\nі ще щось", NOW)
    assert titles(tmp_path) == ["Пошта", "Ярмарок у Пирятині"]
    assert view.text.startswith("«Ярмарок у Пирятині»: у черзі №2")
    assert chat.editing() is None
    assert git.synced == ["queue: rename #2"]


def test_edit_cancelled(tmp_path):
    chat, git = make(tmp_path, "Пошта")
    chat.press("q:edit:1", NOW)
    view = chat.finish_edit("Відміна", NOW)
    assert view.text.startswith("Лишив «Пошта» як є.")
    assert titles(tmp_path) == ["Пошта"]
    assert chat.editing() is None
    assert git.synced == []


# --- in the factory ---------------------------------------------------------------------


class Bot:
    def __init__(self, batches=()):
        self.batches = list(batches)
        self.sent = []
        self.edited = []
        self.answered = []

    def get_updates(self, offset=None, timeout=50):
        updates = self.batches.pop(0) if self.batches else []
        return updates, max([u.update_id + 1 for u in updates], default=offset or 0)

    def send_message(self, text, buttons=None):
        self.sent.append((text, buttons))
        return [1]

    def edit_message(self, message_id, text, buttons=None):
        self.edited.append((message_id, text, buttons))

    def answer_button(self, callback_id, text=""):
        self.answered.append((callback_id, text))


class Intake:
    def __init__(self):
        self.seen = []
        self.showed = False

    def process(self, body, uid, now):
        self.seen.append(body)
        self.showed = body == "що там у черзі"
        return "Ось.\nЧерга:\n1. Пошта, вт 01.12" if self.showed else "Записав."


def factory(tmp_path, bot, *titles):
    chat, _ = make(tmp_path, *titles)
    intake = Intake()
    f = Factory(bot, root=tmp_path, clock=lambda: NOW, intake=intake, queue_chat=chat)
    return f, intake


def drain(f):
    while not f.jobs.empty():
        f.run_job(f.jobs.get())


def text(uid, body):
    return Update(update_id=uid, kind="text", message_id=uid, text=body)


def press(uid, data, message_id=50):
    return Update(update_id=uid, kind="button", message_id=message_id, callback_id="c", data=data)


def test_queue_command_skips_the_brain(tmp_path):
    bot = Bot([[text(1, "/queue")]])
    f, intake = factory(tmp_path, bot, "Пошта")
    f.poll_once(timeout=0)
    drain(f)
    assert intake.seen == []
    ((shown, kb),) = bot.sent
    assert shown == "Черга:\n1. Пошта, вт 01.12"
    assert kb == [[("✏ 1", "q:edit:1"), ("🗑 1", "q:del:1")]]
    assert not (tmp_path / "voice/inbox").exists()


def test_button_edits_the_pressed_message(tmp_path):
    bot = Bot([[press(2, "q:first:2")]])
    f, _ = factory(tmp_path, bot, "Пошта", "Ярмарок")
    f.poll_once(timeout=0)
    drain(f)
    assert titles(tmp_path) == ["Ярмарок", "Пошта"]
    ((message_id, shown, kb),) = bot.edited
    assert message_id == 50
    assert shown.startswith("«Ярмарок»: у черзі №1")
    assert bot.answered[0][0] == "c"
    assert bot.sent == []


def test_rename_by_the_next_message(tmp_path):
    bot = Bot([[press(3, "q:edit:1")], [text(4, "Лист від податкової")]])
    f, intake = factory(tmp_path, bot, "Пошта")
    f.poll_once(timeout=0)
    drain(f)
    f.poll_once(timeout=0)
    drain(f)
    assert intake.seen == []  # the title is not an idea
    assert titles(tmp_path) == ["Лист від податкової"]
    assert bot.sent[-1][0].startswith("«Лист від податкової»: у черзі №1")


def test_queue_by_words_gets_buttons(tmp_path):
    bot = Bot([[text(5, "що там у черзі")]])
    f, intake = factory(tmp_path, bot, "Пошта")
    f.poll_once(timeout=0)
    drain(f)
    shown, kb = bot.sent[-1]
    assert shown.startswith("Ось.")
    assert kb == [[("✏ 1", "q:edit:1"), ("🗑 1", "q:del:1")]]


def test_a_story_reply_has_no_buttons(tmp_path):
    bot = Bot([[text(6, "А було таке...")]])
    f, _ = factory(tmp_path, bot, "Пошта")
    f.poll_once(timeout=0)
    drain(f)
    assert bot.sent[-1] == ("Записав.", None)


def test_a_message_too_old_to_edit_gets_a_fresh_one(tmp_path):
    from beekeeper.factory.telegram import TelegramError

    class OldBot(Bot):
        def edit_message(self, message_id, text, buttons=None):
            raise TelegramError("editMessageText: 400 message to edit not found")

    bot = OldBot([[press(7, "q:show")]])
    f, _ = factory(tmp_path, bot, "Пошта")
    f.poll_once(timeout=0)
    drain(f)
    assert bot.sent[-1][0] == "Черга:\n1. Пошта, вт 01.12"
