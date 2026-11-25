"""Timing step (ADR 001 §5, ADR 002): wav durations + pauses -> one timeline per language.

Everything is counted in whole frames at 30 fps from a running cursor, so nothing drifts:
a line starts where the previous one ended plus a short breath and its own `pause`.
Speech is never cut: a line lasts at least as long as its wav (rounded up to a frame).
Silent shots (no `who`) last as long as it takes to read their on-screen text.
"""

import json
import math
import re
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from beekeeper.episode import Episode, Line
from beekeeper.voices import clip_key
from beekeeper.voices.cast import Voice

FORMAT = 1  # timeline JSON version, read by the Remotion project (T05)
FPS = 30
GAP = 0.25  # breath between two lines, seconds, before the line's own `pause`
READ_CPS = 17.0  # reading speed for on-screen text, characters per second (subtitle norm)
MIN_HOLD = 1.5  # shortest time any on-screen text stays up, seconds
STAGGER = 0.6  # delay between items of an on-screen list ("ложечку", "пів ложечки", ...)
END_CARD_MIN = 3.0
SFX_COUNT = re.compile(r"^(?P<name>.+?)\s+x(?P<n>\d+)$")  # "phone-buzz x3"
MOUTH_OPEN = 0.18  # frame loudness (share of the clip's loud level) that opens the mouth
MOUTH_WIDE = 0.85  # ... and that opens it wide
TARGET = re.compile(r"^\s*(?P<lo>\d+(?:\.\d+)?)\s*-\s*(?P<hi>\d+(?:\.\d+)?)\s*s?\s*$")


class TimingError(Exception):
    """Raised with every problem found, one message per row."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


@dataclass(frozen=True)
class ClipInfo:
    who: str
    file: str  # relative to the voices folder, e.g. "de/01-pylyp-<key>.wav"
    key: str
    duration: float


def frames(seconds: float) -> int:
    """Seconds -> frames, rounded up so audio is never cut (tolerant to float noise)."""
    return max(0, math.ceil(round(seconds * FPS, 6)))


def reading_time(texts: list[str]) -> float:
    return max(MIN_HOLD, sum(len(t) for t in texts) / READ_CPS)


def parse_sfx(value: str) -> tuple[str, int]:
    m = SFX_COUNT.match(value.strip())
    return (m["name"], int(m["n"])) if m else (value.strip(), 1)


def target_range(value: object) -> tuple[float, float] | None:
    """`target_length: 35-40 s` -> (35.0, 40.0); anything else -> None."""
    m = TARGET.match(str(value)) if value is not None else None
    return (float(m["lo"]), float(m["hi"])) if m else None


def mouth_levels(wav: Path, length: int) -> str:
    """One digit per frame for lip flaps: 0 closed, 1 open, 2 wide, from the wav's loudness.

    The loud level is the 90th percentile of the frame RMS, so one shout does not shut the
    mouth for the rest of the line. Frames past the end of the wav stay closed.
    """
    with wave.open(str(wav), "rb") as w:
        if w.getsampwidth() != 2:
            raise TimingError([f"{wav}: expected 16-bit PCM"])
        channels, rate = w.getnchannels(), w.getframerate()
        samples = array("h", w.readframes(w.getnframes()))
    if channels > 1:
        samples = samples[::channels]
    step = rate / FPS
    rms = []
    for k in range(length):
        chunk = samples[int(k * step) : int((k + 1) * step)]
        rms.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)) if chunk else 0.0)
    loud = sorted(rms)[int(0.9 * (len(rms) - 1))] if rms else 0.0
    if loud <= 0:
        return "0" * length
    return "".join(
        "2" if r >= MOUTH_WIDE * loud else "1" if r >= MOUTH_OPEN * loud else "0" for r in rms
    )


def load_clips(voices_dir: Path, lang: str) -> dict[int, ClipInfo]:
    """Read voices.json written by the voice step; keep one language."""
    path = voices_dir / "voices.json"
    if not path.exists():
        raise TimingError([f"{path}: not found, run `beekeeper voices` first"])
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        r["line"]: ClipInfo(r["who"], r["file"], r["key"], float(r["duration"]))
        for r in rows
        if r["lang"] == lang
    }


def check_clips(
    episode: Episode,
    clips: dict[int, ClipInfo],
    lang: str,
    voices_dir: Path,
    voices: dict[tuple[str, str], Voice] | None = None,
    root: Path | None = None,
) -> None:
    """Every spoken line needs its wav; with `voices`, also one voiced from the current text."""
    problems = []
    for i, line in enumerate(episode.lines):
        if not line.who:
            continue
        where = f"lines[{i}] {line.who} {lang}"
        clip = clips.get(i)
        if clip is None or clip.who != line.who:
            problems.append(f"{where}: no voice clip, run `beekeeper voices` first")
        elif not (voices_dir / clip.file).exists():
            problems.append(f"{where}: {clip.file} is missing, run `beekeeper voices` first")
        elif voices is not None and root is not None:
            voice = voices.get((line.who, lang))
            if voice and clip_key(line.text[lang], voice, root) != clip.key:
                problems.append(f"{where}: text or voice changed, run `beekeeper voices` first")
    if problems:
        raise TimingError(problems)


def build_timeline(
    episode: Episode,
    clips: dict[int, ClipInfo],
    lang: str,
    audio_prefix: str = "voices",
    voices_dir: Path | None = None,
) -> dict:
    """Lay out every line on the frame grid; return the JSON-ready timeline for one language.

    With `voices_dir`, every speech also gets `mouth` (see `mouth_levels`) for the lip flaps.
    """
    cursor = 0
    lines = []
    for i, line in enumerate(episode.lines):
        entry = _line(i, line, clips.get(i), lang, cursor, audio_prefix)
        if voices_dir is not None and entry["speech"]:
            speech = entry["speech"]
            wav = voices_dir / clips[i].file
            speech["mouth"] = mouth_levels(wav, speech["end"] - speech["start"])
        lines.append(entry)
        cursor = entry["end"] + frames(GAP + line.pause)

    end_card = None
    if episode.end_card:
        text = episode.end_card[lang]
        hold = frames(max(END_CARD_MIN, reading_time([text])))
        end_card = {"text": text, "start": cursor, "end": cursor + hold}
        cursor += hold
    else:
        cursor = lines[-1]["end"]  # no trailing breath after the last line

    return {
        "format": FORMAT,
        "episode": episode.id,
        "slug": episode.slug,
        "lang": lang,
        "fps": FPS,
        "duration": cursor,
        "title": episode.title[lang],
        "scenes": episode.scenes,
        "lines": lines,
        "end_card": end_card,
    }


def _line(
    i: int, line: Line, clip: ClipInfo | None, lang: str, start: int, audio_prefix: str
) -> dict:
    texts = line.onscreen.get(lang, [])
    speech = None
    length = 0
    if line.who:
        if clip is None:
            raise TimingError([f"lines[{i}] {line.who} {lang}: no voice clip"])
        length = frames(clip.duration)
        speech = {
            "text": line.text[lang],
            "audio": f"{audio_prefix}/{clip.file}",
            "start": start,
            "end": start + length,
        }
    onscreen = []
    if texts:
        stagger = frames(STAGGER)
        last_in = start + stagger * (len(texts) - 1)
        length = max(length, last_in - start + frames(reading_time(texts)))
        onscreen = [{"text": t, "start": start + k * stagger} for k, t in enumerate(texts)]
    end = start + length
    for item in onscreen:
        item["end"] = end

    sfx = []
    if line.sfx:
        name, count = parse_sfx(line.sfx)
        if count == len(onscreen):  # one buzz per message pop-in
            sfx = [{"name": name, "start": item["start"]} for item in onscreen]
        else:
            sfx = [{"name": name, "start": start + k * frames(STAGGER)} for k in range(count)]

    return {
        "index": i,
        "who": line.who,
        "start": start,
        "end": end,
        "shot": line.shot,
        "action": line.action,
        "speech": speech,
        "onscreen": onscreen,
        "sfx": sfx,
    }


def write_timeline(timeline: dict, out_dir: Path) -> Path:
    path = out_dir / f"timeline-{timeline['lang']}.json"
    path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
