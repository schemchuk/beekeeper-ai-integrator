"""Voice step (ADR 002, 003): one wav per spoken line and language, cached by content hash."""

import hashlib
import json
import re
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from beekeeper.episode import Episode
from beekeeper.voices import audio
from beekeeper.voices.cast import Voice
from beekeeper.voices.engines import Engine, default_engines

FORMAT = 2  # bump to re-voice everything after a change in post-processing
BLEEP = re.compile(r"\[[^\]]*\]")  # "[бзз]" in a line = Bzynka's bleep over a swear word


@dataclass(frozen=True)
class Clip:
    line: int  # index in episode.lines
    who: str
    lang: str
    file: str  # relative to the voices folder
    key: str
    duration: float
    cached: bool


def segments(text: str) -> list[str | None]:
    """Split a line at bleep markers: text parts and None for each bleep."""
    out: list[str | None] = []
    for i, part in enumerate(BLEEP.split(text)):
        if i:
            out.append(None)
        if part.strip():
            out.append(part.strip())
    return out


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clip_key(text: str, voice: Voice, root: Path) -> str:
    params = dict(voice.params)
    if "ref" in params:  # a new recording under the same name must re-voice
        params["ref"] = _file_hash(root / params["ref"])
    blob = json.dumps(
        {
            "v": FORMAT,
            "text": text,
            "lang": voice.lang,
            "engine": voice.engine,
            "params": params,
            "fx": voice.fx,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def voice_episode(
    episode: Episode,
    voices: dict[tuple[str, str], Voice],
    out_dir: Path,
    root: Path,
    langs: Iterable[str] = ("de", "ua"),
    engines: dict[str, Engine] | None = None,
    log: Callable[[str], None] = print,
) -> list[Clip]:
    """Voice every spoken line into out_dir/<lang>/; write out_dir/voices.json."""
    engines = engines or default_engines()
    clips: list[Clip] = []
    for lang in langs:
        lang_dir = out_dir / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        keep: set[str] = set()
        for i, line in enumerate(episode.lines):
            if not line.who:
                continue
            voice = voices.get((line.who, lang))
            if voice is None:
                raise KeyError(f"cast.yaml has no {lang} voice for {line.who}")
            text = line.text[lang]
            key = clip_key(text, voice, root)
            name = f"{i:02d}-{line.who}-{key}.wav"
            dst = lang_dir / name
            cached = dst.exists()
            if not cached:
                log(f"voice {lang} {i:02d} {line.who}: {text}")
                _synthesize(text, voice, dst, engines, root)
            keep.add(name)
            clips.append(
                Clip(i, line.who, lang, f"{lang}/{name}", key, audio.duration(dst), cached)
            )
        for stale in lang_dir.glob("*.wav"):
            if stale.name not in keep:
                stale.unlink()
    (out_dir / "voices.json").write_text(
        json.dumps([asdict(c) for c in clips], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return clips


def _synthesize(text: str, voice: Voice, dst: Path, engines: dict[str, Engine], root: Path) -> None:
    engine = engines[voice.engine]
    if "ref" in voice.params:
        voice = Voice(
            voice.character,
            voice.lang,
            voice.engine,
            {**voice.params, "ref": str(root / voice.params["ref"])},
            voice.fx,
        )
    with tempfile.TemporaryDirectory(dir=dst.parent, prefix=".tmp-") as tmp:
        parts = []
        for n, seg in enumerate(segments(text)):
            raw = Path(tmp) / f"{n}.raw.wav"
            done = Path(tmp) / f"{n}.wav"
            if seg is None:
                audio.bleep(done)
            else:
                engine.say(seg, voice, raw)
                audio.finish(raw, done, voice.fx)
            parts.append(done)
        partial = Path(tmp) / "line.wav"
        audio.concat(parts, partial)
        partial.replace(dst)  # only a complete clip lands in the cache
