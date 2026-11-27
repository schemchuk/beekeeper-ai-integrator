import json

import httpx
import pytest

from beekeeper.factory.telegram import (
    MAX_TEXT,
    Config,
    Telegram,
    TelegramError,
    keyboard,
    load_config,
    load_env,
    parse_update,
    split_text,
)

TOKEN = "123:SECRET-token"
CHAT = 4242
STRANGER = 999


class FakeTelegram:
    """A fake Bot API: records calls, answers from a per-method queue."""

    def __init__(self):
        self.calls = []
        self.answers = {}

    def answer(self, method, *responses):
        self.answers.setdefault(method, []).extend(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert TOKEN in path
        if path.startswith("/file/"):
            self.calls.append(("file", path))
            return httpx.Response(200, content=b"OGG")
        method = path.rsplit("/", 1)[1]
        kind = request.headers.get("content-type", "")
        body = json.loads(request.content) if kind.startswith("application/json") else None
        self.calls.append((method, body if body is not None else request.content))
        queued = self.answers.get(method)
        if queued:
            status, payload = queued.pop(0)
            return httpx.Response(status, json=payload)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.calls)}})


@pytest.fixture
def fake():
    return FakeTelegram()


@pytest.fixture
def bot(fake):
    sleeps = []
    client = Telegram(Config(TOKEN, CHAT), transport=httpx.MockTransport(fake), sleep=sleeps.append)
    client.sleeps = sleeps
    yield client
    client.close()


def msg(update_id, chat=CHAT, **fields):
    return {
        "update_id": update_id,
        "message": {"message_id": update_id * 10, "chat": {"id": chat}, **fields},
    }


# --- config ---------------------------------------------------------------------------


def test_config_from_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# secrets\nFACTORY_BOT_TOKEN='abc'\n\nFACTORY_CHAT_ID=42\n")
    assert load_env(env) == {"FACTORY_BOT_TOKEN": "abc", "FACTORY_CHAT_ID": "42"}
    assert load_config(env, environ={}) == Config("abc", 42)


def test_environment_wins_over_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("FACTORY_BOT_TOKEN=file\nFACTORY_CHAT_ID=1\n")
    config = load_config(env, environ={"FACTORY_BOT_TOKEN": "env"})
    assert config == Config("env", 1)


def test_missing_or_bad_config(tmp_path):
    with pytest.raises(TelegramError, match="FACTORY_BOT_TOKEN"):
        load_config(tmp_path / "none", environ={})
    with pytest.raises(TelegramError, match="number"):
        load_config(tmp_path / "none", environ={"FACTORY_BOT_TOKEN": "t", "FACTORY_CHAT_ID": "x"})


# --- parsing --------------------------------------------------------------------------


def test_parse_text_voice_and_button():
    text = parse_update(msg(1, text="а було таке"), CHAT)
    assert (text.kind, text.text, text.message_id) == ("text", "а було таке", 10)

    voice = parse_update(msg(2, voice={"file_id": "F", "duration": 7}), CHAT)
    assert (voice.kind, voice.file_id, voice.duration) == ("voice", "F", 7)

    press = {
        "update_id": 3,
        "callback_query": {
            "id": "cb1",
            "data": "q:up:5",
            "message": {"message_id": 77, "chat": {"id": CHAT}},
        },
    }
    button = parse_update(press, CHAT)
    assert (button.kind, button.callback_id, button.data, button.message_id) == (
        "button",
        "cb1",
        "q:up:5",
        77,
    )


def test_parse_reply_to():
    answer = parse_update(msg(4, text="заміни фінал", reply_to_message={"message_id": 501}), CHAT)
    assert answer.reply_to == 501
    spoken = parse_update(
        msg(5, voice={"file_id": "F"}, reply_to_message={"message_id": 502}), CHAT
    )
    assert spoken.reply_to == 502
    assert parse_update(msg(6, text="просто так"), CHAT).reply_to is None


def test_parse_drops_strangers_and_unknown_kinds():
    assert parse_update(msg(1, chat=STRANGER, text="hi"), CHAT) is None
    assert parse_update(msg(2, sticker={"file_id": "S"}), CHAT) is None
    assert parse_update({"update_id": 3, "edited_message": {}}, CHAT) is None
    assert parse_update({"message": {}}, CHAT) is None


# --- splitting and buttons ------------------------------------------------------------


def test_short_text_is_one_piece():
    assert split_text("привіт") == ["привіт"]


def test_long_text_splits_at_paragraphs():
    para = "слово " * 500  # 3000 characters
    pieces = split_text(f"{para}\n\n{para}\n\n{para}")
    assert len(pieces) == 3
    assert all(len(p) <= MAX_TEXT for p in pieces)


def test_text_without_breaks_still_splits():
    pieces = split_text("x" * (MAX_TEXT + 10))
    assert [len(p) for p in pieces] == [MAX_TEXT, 10]


def test_empty_text_refused():
    with pytest.raises(TelegramError):
        split_text("")


def test_keyboard_checks_callback_data():
    assert keyboard([[("Вгору", "q:up:1"), ("Першою", "q:first:1")]]) == {
        "inline_keyboard": [
            [
                {"text": "Вгору", "callback_data": "q:up:1"},
                {"text": "Першою", "callback_data": "q:first:1"},
            ]
        ]
    }
    with pytest.raises(TelegramError):
        keyboard([[("x", "я" * 33)]])  # 66 bytes
    with pytest.raises(TelegramError):
        keyboard([[("", "q")]])


# --- calls ----------------------------------------------------------------------------


def test_get_updates_filters_chat_and_moves_offset(bot, fake):
    fake.answer(
        "getUpdates",
        (200, {"ok": True, "result": [msg(5, text="так"), msg(6, chat=STRANGER, text="spam")]}),
    )
    updates, offset = bot.get_updates(offset=5, timeout=0)
    assert [u.text for u in updates] == ["так"]
    assert offset == 7  # past the stranger's update too
    method, body = fake.calls[0]
    assert method == "getUpdates"
    assert body["offset"] == 5
    assert body["allowed_updates"] == ["message", "callback_query"]


def test_no_updates_keeps_offset(bot, fake):
    fake.answer("getUpdates", (200, {"ok": True, "result": []}))
    assert bot.get_updates(offset=3, timeout=0) == ([], 3)


def test_send_message_with_buttons_on_last_piece(bot, fake):
    para = "слово " * 500
    ids = bot.send_message(f"{para}\n\n{para}", buttons=[[("Погоджую", "ok")]])
    assert len(ids) == 2
    first, last = (body for _, body in fake.calls)
    assert first["chat_id"] == CHAT and "reply_markup" not in first
    assert last["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "ok"


def test_send_video_and_photo(bot, fake, tmp_path):
    reel = tmp_path / "reel_de.mp4"
    reel.write_bytes(b"MP4DATA")
    cover = tmp_path / "cover_de.png"
    cover.write_bytes(b"PNGDATA")
    assert bot.send_video(reel, caption="Ролик 003") == 1
    assert bot.send_photo(cover) == 2
    (m1, body1), (m2, body2) = fake.calls
    assert m1 == "sendVideo" and b"MP4DATA" in body1 and "Ролик 003".encode() in body1
    assert m2 == "sendPhoto" and b"PNGDATA" in body2


def test_send_file_checks(bot, tmp_path):
    with pytest.raises(TelegramError, match="no such file"):
        bot.send_video(tmp_path / "none.mp4")
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    with pytest.raises(TelegramError, match="caption"):
        bot.send_photo(f, caption="x" * 1025)


def test_download_voice(bot, fake, tmp_path):
    fake.answer("getFile", (200, {"ok": True, "result": {"file_path": "voice/file_1.oga"}}))
    target = bot.download("F", tmp_path / "work" / "v.oga")
    assert target.read_bytes() == b"OGG"
    assert fake.calls[-1] == ("file", f"/file/bot{TOKEN}/voice/file_1.oga")


def test_answer_button(bot, fake):
    bot.answer_button("cb1", "Готово")
    assert fake.calls == [("answerCallbackQuery", {"callback_query_id": "cb1", "text": "Готово"})]


def test_waits_once_on_too_many_requests(bot, fake, tmp_path):
    fake.answer(
        "sendVideo",
        (429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}}),
    )
    reel = tmp_path / "r.mp4"
    reel.write_bytes(b"MP4DATA")
    bot.send_video(reel)
    assert bot.sleeps == [3.0]
    assert [m for m, _ in fake.calls] == ["sendVideo", "sendVideo"]
    assert b"MP4DATA" in fake.calls[1][1]


def test_api_error_has_no_token(bot, fake):
    fake.answer("sendMessage", (400, {"ok": False, "description": "Bad Request: chat not found"}))
    with pytest.raises(TelegramError, match="chat not found") as e:
        bot.send_message("hi")
    assert "SECRET" not in str(e.value)


def test_network_error_has_no_token():
    def boom(request):
        raise httpx.ConnectError(f"cannot reach {request.url}")

    with Telegram(Config(TOKEN, CHAT), transport=httpx.MockTransport(boom)) as bot:
        with pytest.raises(TelegramError, match="ConnectError") as e:
            bot.send_message("hi")
    assert "SECRET" not in str(e.value)


def test_edit_message(bot, fake):
    bot.edit_message(77, "Черга:\n1. Пошта", buttons=[[("✏ 1", "q:edit:1")]])
    ((method, body),) = fake.calls
    assert method == "editMessageText"
    assert body["chat_id"] == CHAT
    assert body["message_id"] == 77
    assert body["reply_markup"] == {
        "inline_keyboard": [[{"text": "✏ 1", "callback_data": "q:edit:1"}]]
    }


def test_edit_that_changes_nothing_is_fine(bot, fake):
    fake.answer(
        "editMessageText",
        (400, {"ok": False, "description": "Bad Request: message is not modified"}),
    )
    bot.edit_message(77, "Черга порожня.")


def test_edit_of_a_gone_message_fails(bot, fake):
    fake.answer(
        "editMessageText",
        (400, {"ok": False, "description": "Bad Request: message to edit not found"}),
    )
    with pytest.raises(TelegramError, match="not found"):
        bot.edit_message(77, "Черга порожня.")


def test_set_commands(bot, fake):
    bot.set_commands([("queue", "Черга ідей")])
    assert fake.calls == [
        ("setMyCommands", {"commands": [{"command": "queue", "description": "Черга ідей"}]})
    ]
