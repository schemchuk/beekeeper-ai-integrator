"""Voice notes to text with local whisper (ADR 010).

The openai-whisper CLI on the laptop (`~/.local/bin/whisper`), model `medium`, language
`uk`, CPU. One run per note, in a temporary output folder; the text file it writes is read
back and the folder removed. CI never runs whisper: tests pass a fake.

`FACTORY_WHISPER` and `FACTORY_WHISPER_MODEL` override the binary and the model (e.g.
`large-v3` if `medium` proves weak on his dialect).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

log = logging.getLogger("beekeeper.factory.transcribe")

MODEL = "medium"
LANGUAGE = "uk"
MIN_TIMEOUT = 15 * 60  # seconds; the model alone takes a while to load
PER_SECOND = 20  # seconds allowed per second of audio; medium ran ~9x on a busy laptop


class TranscribeError(Exception):
    """Whisper is missing, failed or heard nothing; the audio is kept."""


class Transcriber(Protocol):
    def transcribe(self, audio: Path, duration: int = 0) -> str: ...


def find_whisper() -> str:
    configured = os.environ.get("FACTORY_WHISPER")
    if configured:
        return configured
    found = shutil.which("whisper")
    if found:
        return found
    local = Path.home() / ".local/bin/whisper"
    return str(local)


def clean(text: str) -> str:
    """One paragraph: whisper breaks lines by segment, not by sense."""
    return " ".join(text.split())


class Whisper:
    def __init__(
        self, binary: str | None = None, model: str | None = None, language: str = LANGUAGE
    ) -> None:
        self.binary = binary or find_whisper()
        self.model = model or os.environ.get("FACTORY_WHISPER_MODEL") or MODEL
        self.language = language

    def command(self, audio: Path, out_dir: Path) -> list[str]:
        return [
            self.binary,
            str(audio),
            "--model", self.model,
            "--language", self.language,
            "--task", "transcribe",
            "--device", "cpu",
            "--fp16", "False",
            "--output_format", "txt",
            "--output_dir", str(out_dir),
            "--verbose", "False",
        ]  # fmt: skip

    def transcribe(self, audio: Path, duration: int = 0) -> str:
        timeout = max(MIN_TIMEOUT, duration * PER_SECOND)
        with tempfile.TemporaryDirectory(prefix="whisper-") as tmp:
            out_dir = Path(tmp)
            log.info("whisper %s (%s, %ss)", audio.name, self.model, duration)
            try:
                result = subprocess.run(
                    self.command(audio, out_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except FileNotFoundError:
                raise TranscribeError(f"whisper не знайдено ({self.binary})") from None
            except subprocess.TimeoutExpired:
                raise TranscribeError(f"whisper не впорався за {timeout // 60} хв") from None
            if result.returncode != 0:
                tail = (result.stderr or "").strip().splitlines()[-1:] or ["no output"]
                raise TranscribeError(f"whisper впав: {tail[0][:200]}")
            out = out_dir / f"{audio.stem}.txt"
            if not out.exists():
                raise TranscribeError("whisper не залишив тексту")
            text = clean(out.read_text(encoding="utf-8"))
        if not text:
            raise TranscribeError("у голосовому нічого не розчув")
        return text
