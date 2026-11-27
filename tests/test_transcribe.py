import sys

import pytest

from beekeeper.factory.transcribe import TranscribeError, Whisper, clean

FAKE = """#!{python}
import sys
from pathlib import Path
args = sys.argv[1:]
audio = Path(args[0])
out = Path(args[args.index("--output_dir") + 1])
assert args[args.index("--language") + 1] == "uk"
assert args[args.index("--device") + 1] == "cpu"
mode = audio.read_text()
if mode == "fail":
    print("RuntimeError: model broke", file=sys.stderr)
    sys.exit(1)
if mode != "none":
    (out / (audio.stem + ".txt")).write_text(mode, encoding="utf-8")
"""


@pytest.fixture
def fake_whisper(tmp_path):
    path = tmp_path / "whisper"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(0o755)
    return str(path)


def note(tmp_path, content):
    audio = tmp_path / "note.ogg"
    audio.write_text(content, encoding="utf-8")
    return audio


def test_text_comes_back_in_one_paragraph(tmp_path, fake_whisper):
    audio = note(tmp_path, "А було таке:\n ведмідь заліз у вулик\nі заснув.\n")
    heard = Whisper(fake_whisper).transcribe(audio, 5)
    assert heard == "А було таке: ведмідь заліз у вулик і заснув."


def test_a_failing_whisper_says_why(tmp_path, fake_whisper):
    with pytest.raises(TranscribeError, match="model broke"):
        Whisper(fake_whisper).transcribe(note(tmp_path, "fail"))


def test_silence_is_an_error(tmp_path, fake_whisper):
    with pytest.raises(TranscribeError, match="нічого не розчув"):
        Whisper(fake_whisper).transcribe(note(tmp_path, "  \n"))


def test_no_text_file_is_an_error(tmp_path, fake_whisper):
    with pytest.raises(TranscribeError, match="не залишив"):
        Whisper(fake_whisper).transcribe(note(tmp_path, "none"))


def test_missing_whisper(tmp_path):
    with pytest.raises(TranscribeError, match="не знайдено"):
        Whisper(str(tmp_path / "nope")).transcribe(note(tmp_path, "x"))


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("FACTORY_WHISPER_MODEL", "large-v3")
    assert Whisper("whisper").model == "large-v3"
    monkeypatch.delenv("FACTORY_WHISPER_MODEL")
    assert Whisper("whisper").model == "medium"


def test_clean():
    assert clean(" a\n b  c ") == "a b c"
