import json
import math
import wave
from array import array
from pathlib import Path

import pytest

from beekeeper import timing
from beekeeper.cli import main
from beekeeper.episode import load_episode
from beekeeper.timing import (
    FPS,
    ClipInfo,
    TimingError,
    build_timeline,
    check_clips,
    frames,
    load_clips,
    mouth_levels,
    parse_sfx,
    target_range,
)
from blocks import COVER_POST

EPISODE = (
    """\
id: "900"
slug: test
title: {ua: "Тест", de: "Test"}
"""
    + COVER_POST
    + """\
target_length: 3-5 s
lines:
  - onscreen: {ua: "03:12", de: "03:12"}
    sfx: phone-buzz
  - who: pylyp
    ua: "Ти знаєш?"
    de: "Weißt du?"
    pause: 0.5
  - onscreen:
      ua: ["раз", "два", "три"]
      de: ["eins", "zwei", "drei"]
    sfx: phone-buzz x3
  - who: bee
    ua: "Автоматизуй."
    de: "Automatisier das."
    onscreen: {ua: "довгий текст на екрані, який читається довше за репліку", de: "x"}
end_card: {ua: "Кінець", de: "Ende"}
"""
)


@pytest.fixture
def episode(tmp_path):
    (tmp_path / "episode.yaml").write_text(EPISODE, encoding="utf-8")
    return load_episode(tmp_path, {"pylyp", "bee"})


def clips(lang="ua", pylyp=1.0, bee=0.5):
    return {
        1: ClipInfo("pylyp", f"{lang}/01-pylyp-k1.wav", "k1", pylyp),
        3: ClipInfo("bee", f"{lang}/03-bee-k3.wav", "k3", bee),
    }


def test_frames_round_up_and_ignore_float_noise():
    assert frames(1.0) == 30
    assert frames(1.01) == 31  # never cut the end of a wav
    assert frames(0.1 * 3) == 9  # 0.30000000000000004 s is still 9 frames
    assert frames(0) == 0


def test_parse_sfx_and_target():
    assert parse_sfx("phone-buzz x3") == ("phone-buzz", 3)
    assert parse_sfx("keyboard") == ("keyboard", 1)
    assert target_range("35-40 s") == (35.0, 40.0)
    assert target_range(None) is None
    assert target_range("short") is None


def test_lines_follow_wav_lengths_gaps_and_pauses(episode):
    tl = build_timeline(episode, clips(pylyp=1.0), "ua")
    l0, l1, l2, l3 = tl["lines"]
    gap = frames(timing.GAP)

    cover = tl["cover"]
    assert (cover["start"], cover["end"]) == (0, frames(timing.COVER_SECONDS))
    assert cover["monitor"] == "Ваш запит збережено."
    assert cover["title"] == "Тест" and cover["who"] == ["pylyp"]
    assert l0["start"] == cover["end"]  # the hook comes right after the cover
    assert l0["end"] == l0["start"] + frames(
        timing.MIN_HOLD
    )  # short on-screen text holds the minimum
    assert l1["start"] == l0["end"] + gap
    assert l1["speech"]["start"] == l1["start"]
    assert l1["end"] - l1["start"] == 30  # exactly the 1.0 s wav
    assert l1["speech"]["audio"] == "voices/ua/01-pylyp-k1.wav"
    assert l2["start"] == l1["end"] + frames(timing.GAP + 0.5)  # its own pause adds up
    assert tl["end_card"]["start"] == l3["end"] + gap
    assert tl["duration"] == tl["end_card"]["end"]
    assert tl["fps"] == FPS and tl["lang"] == "ua" and tl["title"] == "Тест"


def test_one_line_edit_shifts_only_later_lines(episode):
    short = build_timeline(episode, clips(pylyp=1.0), "ua")
    long = build_timeline(episode, clips(pylyp=2.0), "ua")
    assert long["lines"][0] == short["lines"][0]
    assert long["lines"][1]["end"] - short["lines"][1]["end"] == 30
    assert long["lines"][3]["start"] - short["lines"][3]["start"] == 30
    assert long["duration"] - short["duration"] == 30


def test_onscreen_list_pops_in_with_one_sfx_each(episode):
    line = build_timeline(episode, clips(), "de")["lines"][2]
    starts = [item["start"] for item in line["onscreen"]]
    step = frames(timing.STAGGER)
    assert starts == [line["start"], line["start"] + step, line["start"] + 2 * step]
    assert all(item["end"] == line["end"] for item in line["onscreen"])
    assert [s["start"] for s in line["sfx"]] == starts
    assert {s["name"] for s in line["sfx"]} == {"phone-buzz"}
    assert line["end"] - starts[-1] >= frames(timing.MIN_HOLD)  # the last one is readable


def test_long_onscreen_text_outlasts_short_speech(episode):
    line = build_timeline(episode, clips(bee=0.5), "ua")["lines"][3]
    assert line["speech"]["end"] - line["speech"]["start"] == 15
    text = line["onscreen"][0]["text"]
    assert line["end"] - line["start"] == frames(len(text) / timing.READ_CPS)


def test_without_end_card_the_reel_ends_with_the_last_line(episode):
    from dataclasses import replace

    tl = build_timeline(replace(episode, end_card={}), clips(), "ua")
    assert tl["end_card"] is None
    assert tl["duration"] == tl["lines"][-1]["end"]


def test_check_clips_reports_missing_and_stale(episode, tmp_path):
    voices_dir = tmp_path / "voices"
    (voices_dir / "ua").mkdir(parents=True)
    (voices_dir / "ua/01-pylyp-k1.wav").write_bytes(b"")
    with pytest.raises(TimingError) as e:
        check_clips(episode, {1: clips()[1]}, "ua", voices_dir)
    assert e.value.problems == ["lines[3] bee ua: no voice clip, run `beekeeper voices` first"]

    with pytest.raises(TimingError) as e:
        check_clips(episode, clips(), "ua", voices_dir)
    assert "03-bee-k3.wav is missing" in e.value.problems[0]


def test_load_clips_keeps_one_language(tmp_path):
    rows = [
        {"line": 1, "who": "pylyp", "lang": "de", "file": "de/a.wav", "key": "a", "duration": 1},
        {"line": 1, "who": "pylyp", "lang": "ua", "file": "ua/b.wav", "key": "b", "duration": 2},
    ]
    (tmp_path / "voices.json").write_text(json.dumps(rows), encoding="utf-8")
    assert load_clips(tmp_path, "ua") == {1: ClipInfo("pylyp", "ua/b.wav", "b", 2.0)}
    with pytest.raises(TimingError, match="run `beekeeper voices` first"):
        load_clips(tmp_path / "nowhere", "ua")


def test_cli_timing_without_voices_fails_readably(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    code = main(
        [
            "timing",
            str(root / "episodes/002-medunko-v-splyachtsi"),
            "--cast",
            str(root / "characters/cast.yaml"),
            "--out",
            str(tmp_path),
            "--lang",
            "de",
        ]
    )
    assert code == 1
    assert "run `beekeeper voices` first" in capsys.readouterr().err


def write_wav(path, seconds_and_amp, rate=48000):
    """Sine tone in segments: [(seconds, amplitude 0..1), ...], 16-bit mono."""
    samples = array("h")
    for seconds, amp in seconds_and_amp:
        for n in range(int(seconds * rate)):
            samples.append(int(amp * 30000 * math.sin(2 * math.pi * 220 * n / rate)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


def test_mouth_follows_loudness_and_closes_after_the_wav(tmp_path):
    wav = tmp_path / "a.wav"
    write_wav(wav, [(0.2, 0.0), (0.2, 0.3), (0.2, 1.0)])  # silence, quiet, loud
    levels = mouth_levels(wav, frames(0.6) + 3)
    assert levels == "0" * 6 + "1" * 6 + "2" * 6 + "000"


def test_silent_wav_keeps_the_mouth_closed(tmp_path):
    wav = tmp_path / "s.wav"
    write_wav(wav, [(0.1, 0.0)])
    assert mouth_levels(wav, 3) == "000"


def test_timeline_speech_gets_one_mouth_digit_per_frame(episode, tmp_path):
    write_wav(tmp_path / "ua/01-pylyp-k1.wav", [(0.5, 0.0), (0.5, 1.0)])
    write_wav(tmp_path / "ua/03-bee-k3.wav", [(0.5, 1.0)])
    tl = build_timeline(episode, clips(), "ua", voices_dir=tmp_path)
    for line in tl["lines"]:
        speech = line["speech"]
        if speech:
            assert len(speech["mouth"]) == speech["end"] - speech["start"]
    pylyp = tl["lines"][1]["speech"]["mouth"]
    assert set(pylyp[:15]) == {"0"} and "2" in pylyp[15:]
    assert "mouth" not in build_timeline(episode, clips(), "ua")["lines"][1]["speech"]


def test_sfx_events_point_at_their_wav(episode):
    assert timing.sfx_names(episode) == {"phone-buzz"}
    tl = build_timeline(episode, clips(), "ua", sfx_audio={"phone-buzz": "sfx/phone-buzz.wav"})
    events = [e for line in tl["lines"] for e in line["sfx"]]
    assert len(events) == 4 and all(e["audio"] == "sfx/phone-buzz.wav" for e in events)
