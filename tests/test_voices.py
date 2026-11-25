import json
import shutil
import subprocess
from pathlib import Path

import pytest

from beekeeper.episode import load_episode
from beekeeper.voices import clip_key, segments, voice_episode
from beekeeper.voices.cast import CastError, Voice, load_voices
from beekeeper.voices.engines import Piper

ROOT = Path(__file__).resolve().parents[1]
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

EPISODE = """\
id: "900"
slug: test
title: {ua: "Тест", de: "Test"}
lines:
  - onscreen: {ua: "03:12", de: "03:12"}
  - who: pylyp
    ua: "Ти [бзз] знаєш?"
    de: "Weißt du [bzz]?"
  - who: bee
    ua: "Автоматизуй."
    de: "Automatisier das."
"""
CAST = """\
pylyp:
  ua: {engine: holos, voice: clone, ref: ref.wav}
  de: {engine: chatterbox, ref: ref.wav, exaggeration: 0.5}
bee:
  ua: {engine: holos, voice: [Speaker_1, Speaker_2], speed: 1.1, fx: [1.35, 1.1]}
  de: {engine: piper, model: de_DE-kerstin-low, fx: [1.35, 1.1]}
"""


class FakeEngine:
    """Writes 0.2 s of tone per call instead of real speech."""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    def say(self, text, voice, dst):
        self.calls.append((voice.character, voice.lang, text))
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=300:duration=0.2:sample_rate=24000",
                str(dst),
            ],
            check=True,
        )


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "episode.yaml").write_text(EPISODE, encoding="utf-8")
    (tmp_path / "cast.yaml").write_text(CAST, encoding="utf-8")
    (tmp_path / "ref.wav").write_bytes(b"volodymyr")
    voices = load_voices(tmp_path / "cast.yaml")
    fake = FakeEngine()
    engines = {"holos": fake, "chatterbox": fake, "piper": fake}

    def run(episode_text=None):
        if episode_text:
            (tmp_path / "episode.yaml").write_text(episode_text, encoding="utf-8")
        ep = load_episode(tmp_path, {"pylyp", "bee"})
        return voice_episode(
            ep, voices, tmp_path / "out", tmp_path, engines=engines, log=lambda _: None
        )

    return tmp_path, fake, run


def test_segments_split_at_bleeps():
    assert segments("Ти [бзз] знаєш?") == ["Ти", None, "знаєш?"]
    assert segments("Автоматизуй.") == ["Автоматизуй."]
    assert segments("[bzz] Hallo") == [None, "Hallo"]


def test_load_voices_from_real_cast():
    voices = load_voices(ROOT / "characters/cast.yaml")
    assert voices[("pylyp", "de")].engine == "chatterbox"
    assert voices[("medunko", "ua")].fx == (0.78, 0.9)
    assert voices[("koliuchka", "de")].params["speaker"] == "disgusted"


def test_cast_rejects_unknown_engine(tmp_path):
    (tmp_path / "cast.yaml").write_text("x:\n  ua: {engine: espeak}\n", encoding="utf-8")
    with pytest.raises(CastError, match="engine must be one of"):
        load_voices(tmp_path / "cast.yaml")


def test_key_changes_with_text_voice_and_ref(tmp_path):
    (tmp_path / "ref.wav").write_bytes(b"a")
    v = Voice("pylyp", "de", "chatterbox", {"ref": "ref.wav"})
    k = clip_key("Hallo", v, tmp_path)
    assert clip_key("Hallo", v, tmp_path) == k
    assert clip_key("Hallo!", v, tmp_path) != k
    assert (
        clip_key(
            "Hallo", Voice("pylyp", "de", "chatterbox", {"ref": "ref.wav"}, (1.1, 1.0)), tmp_path
        )
        != k
    )
    (tmp_path / "ref.wav").write_bytes(b"b")
    assert clip_key("Hallo", v, tmp_path) != k


@needs_ffmpeg
def test_voices_are_made_once_and_cached(setup):
    tmp_path, fake, run = setup
    clips = run()
    assert [(c.line, c.lang) for c in clips] == [(1, "de"), (2, "de"), (1, "ua"), (2, "ua")]
    # the bleep line is two engine calls around a generated beep
    assert ("pylyp", "de", "Weißt du") in fake.calls and ("pylyp", "de", "?") in fake.calls
    assert all(c.duration > 0.15 for c in clips)
    pylyp_de = clips[0]
    assert pylyp_de.duration > 0.2 + 0.3  # speech + bleep
    manifest = json.loads((tmp_path / "out/voices.json").read_text())
    assert manifest[0]["file"].startswith("de/01-pylyp-")

    fake.calls.clear()
    again = run()
    assert fake.calls == [] and all(c.cached for c in again)


@needs_ffmpeg
def test_one_line_edit_revoices_one_clip(setup):
    tmp_path, fake, run = setup
    run()
    fake.calls.clear()
    clips = run(EPISODE.replace("Automatisier das.", "Automatisier es."))
    assert fake.calls == [("bee", "de", "Automatisier es.")]
    assert [c.cached for c in clips] == [True, False, True, True]
    assert len(list((tmp_path / "out/de").glob("02-*.wav"))) == 1  # stale clip removed


@needs_ffmpeg
def test_output_is_48k_mono(setup):
    tmp_path, _, run = setup
    clip = run()[1]
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=sample_rate,channels",
            "-of",
            "csv=p=0",
            str(tmp_path / "out" / clip.file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "48000,1"


def test_piper_speaker_by_name(tmp_path):
    model = tmp_path / "m.onnx"
    Path(f"{model}.json").write_text(json.dumps({"speaker_id_map": {"amused": 0, "disgusted": 2}}))
    assert Piper.speaker_id(model, "disgusted") == 2
    assert Piper.speaker_id(model, 5) == 5
    with pytest.raises(ValueError, match="no speaker 'sad'"):
        Piper.speaker_id(model, "sad")
