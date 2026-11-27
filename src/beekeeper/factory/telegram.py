"""Telegram Bot API client for the factory bot (docs/architecture.md §2, ADR 006).

Plain `httpx`, no bot framework. The client serves exactly one chat (`FACTORY_CHAT_ID`):
updates from any other chat are dropped, and every send goes to that chat. The HTTP layer
is injectable (`httpx.MockTransport` in the tests), so CI never calls Telegram.

The bot token is part of every URL; it never appears in an error message.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://api.telegram.org"
ENV_FILE = Path(".env")
MAX_TEXT = 4096  # Telegram's limit for one message
MAX_CAPTION = 1024
MAX_CALLBACK_DATA = 64  # bytes

# One button: (label, callback data). Buttons are rows of these.
Button = tuple[str, str]
Buttons = Sequence[Sequence[Button]]


class TelegramError(RuntimeError):
    """A failed Bot API call or a broken configuration."""


@dataclass(frozen=True)
class Config:
    token: str
    chat_id: int


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """`KEY=value` lines of a .env file ({} if it does not exist). Quotes are stripped."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_config(path: Path = ENV_FILE, environ: dict[str, str] | None = None) -> Config:
    """Token and chat id from the environment, falling back to the .env file."""
    environ = os.environ if environ is None else environ
    file_values = load_env(path)

    def get(name: str) -> str:
        value = environ.get(name) or file_values.get(name)
        if not value:
            raise TelegramError(f"{name} is not set (environment or {path})")
        return value

    token = get("FACTORY_BOT_TOKEN")
    raw_chat = get("FACTORY_CHAT_ID")
    try:
        chat_id = int(raw_chat)
    except ValueError as e:
        raise TelegramError("FACTORY_CHAT_ID must be a number") from e
    return Config(token=token, chat_id=chat_id)


@dataclass(frozen=True)
class Update:
    """One incoming event from his chat, reduced to what the router needs."""

    update_id: int
    kind: str  # "text", "voice" or "button"
    message_id: int | None = None
    text: str = ""  # message text, or the caption of a voice note
    file_id: str = ""  # voice notes
    duration: int = 0  # voice notes, seconds
    callback_id: str = ""  # button presses: answer it with answer_button()
    data: str = ""  # button presses: the callback data


def parse_update(raw: dict, chat_id: int) -> Update | None:
    """An `Update`, or None for anything outside his chat or of a kind the bot ignores."""
    update_id = raw.get("update_id")
    if not isinstance(update_id, int):
        return None

    callback = raw.get("callback_query")
    if isinstance(callback, dict):
        message = callback.get("message") or {}
        if _chat_of(message) != chat_id:
            return None
        return Update(
            update_id=update_id,
            kind="button",
            message_id=message.get("message_id"),
            callback_id=str(callback.get("id", "")),
            data=str(callback.get("data", "")),
        )

    message = raw.get("message")
    if not isinstance(message, dict) or _chat_of(message) != chat_id:
        return None
    voice = message.get("voice") or message.get("audio")
    if isinstance(voice, dict) and voice.get("file_id"):
        return Update(
            update_id=update_id,
            kind="voice",
            message_id=message.get("message_id"),
            text=message.get("caption", ""),
            file_id=voice["file_id"],
            duration=int(voice.get("duration", 0)),
        )
    if isinstance(message.get("text"), str):
        return Update(
            update_id=update_id,
            kind="text",
            message_id=message.get("message_id"),
            text=message["text"],
        )
    return None


def _chat_of(message: dict) -> int | None:
    chat = message.get("chat")
    return chat.get("id") if isinstance(chat, dict) else None


def split_text(text: str, limit: int = MAX_TEXT) -> list[str]:
    """Pieces of at most `limit` characters, cut at a blank line, a line end or a space."""
    if not text:
        raise TelegramError("empty message")
    pieces = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        cut = max(window.rfind("\n\n"), 0) or max(window.rfind("\n"), 0) or window.rfind(" ")
        if cut <= 0:
            cut = limit
        pieces.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        pieces.append(rest)
    return pieces


def keyboard(buttons: Buttons) -> dict:
    rows = []
    for row in buttons:
        cells = []
        for label, data in row:
            if not label:
                raise TelegramError("a button needs a label")
            if not data or len(data.encode()) > MAX_CALLBACK_DATA:
                raise TelegramError(f"button data must be 1-{MAX_CALLBACK_DATA} bytes: {data!r}")
            cells.append({"text": label, "callback_data": data})
        rows.append(cells)
    return {"inline_keyboard": rows}


class Telegram:
    """The factory bot, bound to his chat."""

    def __init__(
        self,
        config: Config,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._sleep = sleep
        # Long polls wait up to their own timeout; the read timeout leaves room for that.
        self._http = httpx.Client(transport=transport, timeout=httpx.Timeout(10.0, read=70.0))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Telegram:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- incoming -------------------------------------------------------------------

    def get_updates(self, offset: int | None = None, timeout: int = 50) -> tuple[list[Update], int]:
        """Updates from his chat and the next offset to ask with.

        The next offset moves past every update Telegram sent, including the dropped ones,
        so a stranger's message is not delivered again.
        """
        params: dict = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        raw_updates = self._call("getUpdates", json=params)
        next_offset = offset or 0
        updates = []
        for raw in raw_updates:
            if isinstance(raw.get("update_id"), int):
                next_offset = max(next_offset, raw["update_id"] + 1)
            update = parse_update(raw, self.config.chat_id)
            if update is not None:
                updates.append(update)
        return updates, next_offset

    def download(self, file_id: str, target: Path) -> Path:
        """Save a file he sent (a voice note) to `target`."""
        info = self._call("getFile", json={"file_id": file_id})
        file_path = info.get("file_path")
        if not file_path:
            raise TelegramError("getFile: no file_path in the answer")
        url = f"{API}/file/bot{self.config.token}/{file_path}"
        try:
            response = self._http.get(url)
        except httpx.HTTPError as e:
            raise TelegramError(f"download failed: {type(e).__name__}") from None
        if response.status_code != 200:
            raise TelegramError(f"download failed: HTTP {response.status_code}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target

    # --- outgoing -------------------------------------------------------------------

    def send_message(self, text: str, buttons: Buttons | None = None) -> list[int]:
        """Send `text` (split if too long); buttons go under the last piece. Message ids."""
        pieces = split_text(text)
        ids = []
        for i, piece in enumerate(pieces):
            payload: dict = {"chat_id": self.config.chat_id, "text": piece}
            if buttons and i == len(pieces) - 1:
                payload["reply_markup"] = keyboard(buttons)
            ids.append(self._call("sendMessage", json=payload)["message_id"])
        return ids

    def edit_message(self, message_id: int, text: str, buttons: Buttons | None = None) -> None:
        """Replace the text and buttons of a message the bot sent (a live queue view).

        Telegram refuses an edit that changes nothing; that is not an error here.
        """
        payload: dict = {
            "chat_id": self.config.chat_id,
            "message_id": message_id,
            "text": split_text(text)[0],
            "reply_markup": keyboard(buttons or []),
        }
        try:
            self._call("editMessageText", json=payload)
        except TelegramError as e:
            if "message is not modified" not in str(e):
                raise

    def set_commands(self, commands: Sequence[tuple[str, str]]) -> None:
        """The command menu next to his input field: (command, description) pairs."""
        menu = [{"command": c, "description": d} for c, d in commands]
        self._call("setMyCommands", json={"commands": menu})

    def send_video(self, path: Path, caption: str = "") -> int:
        return self._send_file("sendVideo", "video", path, caption)

    def send_photo(self, path: Path, caption: str = "") -> int:
        return self._send_file("sendPhoto", "photo", path, caption)

    def answer_button(self, callback_id: str, text: str = "") -> None:
        """Stop the spinner on a pressed button (optionally with a short toast)."""
        payload: dict = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]
        self._call("answerCallbackQuery", json=payload)

    def _send_file(self, method: str, field: str, path: Path, caption: str) -> int:
        if len(caption) > MAX_CAPTION:
            raise TelegramError(f"caption longer than {MAX_CAPTION} characters")
        if not path.is_file():
            raise TelegramError(f"{method}: no such file {path}")
        data = {"chat_id": str(self.config.chat_id)}
        if caption:
            data["caption"] = caption
        # Bytes, not an open file: a retry after 429 sends them again from the start.
        result = self._call(method, data=data, files={field: (path.name, path.read_bytes())})
        return result["message_id"]

    # --- transport ------------------------------------------------------------------

    def _call(self, method: str, **kwargs: object) -> object:
        """POST one Bot API method; waits once if Telegram says "too many requests"."""
        url = f"{API}/bot{self.config.token}/{method}"
        for attempt in range(2):
            try:
                response = self._http.post(url, **kwargs)
            except httpx.HTTPError as e:
                # The exception text carries the URL, and with it the token.
                raise TelegramError(f"{method}: {type(e).__name__}") from None
            try:
                body = response.json()
            except ValueError:
                raise TelegramError(f"{method}: HTTP {response.status_code}, not JSON") from None
            if body.get("ok"):
                return body.get("result")
            retry_after = (body.get("parameters") or {}).get("retry_after")
            if response.status_code == 429 and retry_after and attempt == 0:
                self._sleep(float(retry_after))
                continue
            description = body.get("description", "no description")
            raise TelegramError(f"{method}: {response.status_code} {description}")
        raise TelegramError(f"{method}: too many requests")  # pragma: no cover


def smoke_test() -> None:
    """By hand, with his bot: `python -m beekeeper.factory.telegram`."""
    config = load_config()
    with Telegram(config) as bot:
        me = bot._call("getMe")
        print(f"bot: @{me.get('username')}")
        bot.send_message(
            "Фабрика на зв'язку. Це перевірка клієнта (T24).",
            buttons=[[("Чую", "smoke:ok")]],
        )
        print("message sent; press the button in Telegram, waiting up to 60 s ...")
        offset = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            updates, offset = bot.get_updates(offset, timeout=20)
            for update in updates:
                print(f"got {update.kind}: {update.data or update.text!r}")
                if update.kind == "button":
                    bot.answer_button(update.callback_id, "Працює")
                    bot.get_updates(offset, timeout=0)  # confirm, so it is not resent
                    return
        print("no button press seen")


if __name__ == "__main__":
    smoke_test()
