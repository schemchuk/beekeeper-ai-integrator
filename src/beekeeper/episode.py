"""Episode file (ADR 001): load `episode.yaml`, validate it, return plain dataclasses."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from beekeeper import yamlio

LANGS = ("ua", "de")
TOP_KEYS = {
    "id",
    "slug",
    "title",
    "season",
    "target_length",
    "release",
    "seed",
    "scenes",
    "lines",
    "end_card",
    "cover",
    "post",
}
LINE_KEYS = {"who", "ua", "de", "shot", "onscreen", "sfx", "action", "note", "pause"}
SHOT_KEYS = {"scene", "camera", "action", "at", "eyes"}
EYES = {"open", "closed"}  # shot.eyes: everyone on screen (closed = asleep)

# Cover (BRIEF cover rule): frame 0 and the thumbnail. A glowing monitor with an IT pain,
# one to three characters, the title.
COVER_KEYS = {"who", "monitor"}
COVER_MAX_WHO = 3
MONITOR_MAX = 80  # characters per language, readable on a phone-sized thumbnail

# Post text for the feed (roadmap T11). LinkedIn shows about two lines before "mehr".
POST_PARTS = ("hook", "grain", "question", "offer")
POST_KEYS = {*POST_PARTS, "hashtags"}
HOOK_MAX = 150
HASHTAGS = (3, 5)
HASHTAG = re.compile(r"^[^\s#]+$")
# The hook sells the pain, not the format: no "Neuer Zeichentrickfilm".
HOOK_FORBIDDEN = re.compile(r"zeichentrick|cartoon|мульт", re.IGNORECASE)
# He offers, never begs (feedback: dignity); his biography stays implied (docs/product.md).
POST_FORBIDDEN = {
    "asks for a job (offer help instead)": re.compile(
        r"шукаю\s+роботу|візьміть\s+мене|найміть|suche\s+(?:eine[n]?\s+)?(?:job|arbeit|stelle)"
        r"|bewerb|hire\s+me|looking\s+for\s+a\s+job",
        re.IGNORECASE,
    ),
    "states his biography (keep it implied)": re.compile(
        r"\d+\s*(?:вулик|бджолосім|bienenv[öo]lk|bienenst[öo]ck|hives?\b)", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class Line:
    who: str | None
    text: dict[str, str]  # empty when the line has no speech
    onscreen: dict[str, list[str]]  # empty when nothing is shown as text
    shot: dict[str, str] = field(default_factory=dict)
    sfx: str | None = None
    action: str | None = None
    pause: float = 0.0


@dataclass(frozen=True)
class Cover:
    who: list[str]
    monitor: dict[str, str]


@dataclass(frozen=True)
class Post:
    parts: dict[str, dict[str, str]]  # hook/grain/question/offer -> {ua, de}
    hashtags: list[str]


@dataclass(frozen=True)
class Episode:
    id: str
    slug: str
    title: dict[str, str]
    lines: list[Line]
    scenes: dict[str, str] = field(default_factory=dict)
    end_card: dict[str, str] = field(default_factory=dict)
    cover: Cover | None = None
    post: Post | None = None
    extra: dict[str, object] = field(default_factory=dict)  # season, target_length, release, seed


class EpisodeError(Exception):
    """Raised with every problem found, one `file:line: message` per row."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def episode_file(path: Path) -> Path:
    return path / "episode.yaml" if path.is_dir() else path


def load_cast(path: Path) -> set[str]:
    data = yamlio.load(path)
    if not isinstance(data, dict):
        raise EpisodeError([f"{path}: expected a mapping of characters"])
    return set(data)


def load_episode(path: Path, cast: set[str]) -> Episode:
    path = episode_file(path)
    try:
        data = yamlio.load(path)
    except FileNotFoundError:
        raise EpisodeError([f"{path}: file not found"]) from None
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"{path}:{mark.line + 1}" if mark else str(path)
        raise EpisodeError([f"{where}: invalid YAML: {getattr(e, 'problem', e)}"]) from None
    return _Checker(path, cast).episode(data)


class _Checker:
    def __init__(self, path: Path, cast: set[str]):
        self.path = path
        self.cast = cast
        self.problems: list[str] = []

    def err(self, node: object, where: str, msg: str, line: int = 0) -> None:
        self.problems.append(f"{self.path}:{line or yamlio.line_of(node) or 1}: {where}: {msg}")

    def episode(self, data: object) -> Episode:
        if not isinstance(data, dict):
            raise EpisodeError([f"{self.path}:1: top level must be a mapping"])
        for key in sorted(set(data) - TOP_KEYS):
            self.err(data, key, "unknown key")
        for key in ("id", "slug"):
            if not isinstance(data.get(key), str) or not data.get(key):
                self.err(data, key, "required text")
        title = self.pair(data, "title", data.get("title"), required=True)
        scenes = data.get("scenes", {})
        if not isinstance(scenes, dict) or not all(isinstance(v, str) for v in scenes.values()):
            self.err(data, "scenes", "must map a scene name to a description")
            scenes = {}
        end_card = self.pair(data, "end_card", data.get("end_card"), required=False)
        cover = self.cover(data)
        post = self.post(data)
        raw_lines = data.get("lines")
        lines: list[Line] = []
        if not isinstance(raw_lines, list) or not raw_lines:
            self.err(data, "lines", "required, a non-empty list")
        else:
            for i, raw in enumerate(raw_lines):
                line = self.line(f"lines[{i}]", raw, raw_lines, scenes)
                if line:
                    lines.append(line)
        if self.problems:
            raise EpisodeError(self.problems)
        extra = {k: data[k] for k in ("season", "target_length", "release", "seed") if k in data}
        return Episode(
            id=str(data["id"]),
            slug=data["slug"],
            title=title,
            lines=lines,
            scenes=dict(scenes),
            end_card=end_card,
            cover=cover,
            post=post,
            extra=extra,
        )

    def cover(self, data: dict) -> Cover | None:
        raw = data.get("cover")
        if not isinstance(raw, dict):
            self.err(data, "cover", "required: who (characters) and monitor (ua, de)")
            return None
        for key in sorted(set(raw) - COVER_KEYS):
            self.err(raw, f"cover.{key}", "unknown key")
        who = raw.get("who")
        who = [who] if isinstance(who, str) else who
        if not isinstance(who, list) or not 1 <= len(who) <= COVER_MAX_WHO:
            self.err(raw, "cover.who", f"required: 1-{COVER_MAX_WHO} characters")
            who = []
        for name in who:
            if name not in self.cast:
                self.err(raw, "cover.who", f"'{name}' is not in cast.yaml")
        monitor = self.pair(raw, "cover.monitor", raw.get("monitor"), required=True)
        for lang, text in monitor.items():
            if len(text) > MONITOR_MAX:
                self.err(raw, f"cover.monitor.{lang}", f"{len(text)} characters, max {MONITOR_MAX}")
        return Cover(who=[str(n) for n in who], monitor=monitor)

    def post(self, data: dict) -> Post | None:
        raw = data.get("post")
        if not isinstance(raw, dict):
            self.err(data, "post", f"required: {', '.join(POST_PARTS)}, hashtags")
            return None
        for key in sorted(set(raw) - POST_KEYS):
            self.err(raw, f"post.{key}", "unknown key")
        parts = {k: self.pair(raw, f"post.{k}", raw.get(k), required=True) for k in POST_PARTS}
        for lang, hook in parts["hook"].items():
            where = f"post.hook.{lang}"
            if len(hook) > HOOK_MAX or "\n" in hook.strip():
                self.err(raw, where, f"one line, max {HOOK_MAX} characters (shown before 'mehr')")
            if HOOK_FORBIDDEN.search(hook):
                self.err(raw, where, "name the reader's pain, not the format (no 'cartoon')")
        for lang, question in parts["question"].items():
            if not question.rstrip().endswith("?"):
                self.err(raw, f"post.question.{lang}", "must be a question (ends with ?)")
        for part, texts in parts.items():
            for lang, text in texts.items():
                for why, pattern in POST_FORBIDDEN.items():
                    if pattern.search(text):
                        self.err(raw, f"post.{part}.{lang}", why)
        tags = raw.get("hashtags")
        lo, hi = HASHTAGS
        if not isinstance(tags, list) or not lo <= len(tags) <= hi:
            self.err(raw, "post.hashtags", f"required: {lo}-{hi} hashtags")
            tags = []
        for tag in tags:
            if not isinstance(tag, str) or not HASHTAG.match(tag):
                self.err(raw, "post.hashtags", f"'{tag}': one word, without '#'")
        return Post(parts=parts, hashtags=[str(t) for t in tags])

    def pair(self, parent: object, where: str, value: object, required: bool) -> dict[str, str]:
        if value is None and not required:
            return {}
        if not isinstance(value, dict):
            self.err(parent, where, "required: ua and de texts")
            return {}
        anchor = value if yamlio.line_of(value) else parent
        out = {}
        for lang in LANGS:
            text = value.get(lang)
            if not isinstance(text, str) or not text.strip():
                self.err(anchor, f"{where}.{lang}", "required text")
            else:
                out[lang] = text
        for key in sorted(set(value) - set(LANGS)):
            self.err(anchor, f"{where}.{key}", "unknown language (use ua, de)")
        return out

    def line(self, where: str, raw: object, parent: object, scenes: dict) -> Line | None:
        if not isinstance(raw, dict):
            self.err(parent, where, "must be a mapping")
            return None
        for key in sorted(set(raw) - LINE_KEYS):
            self.err(raw, f"{where}.{key}", "unknown key")

        who = raw.get("who")
        text: dict[str, str] = {}
        if who is not None:
            if who not in self.cast:
                self.err(raw, f"{where}.who", f"'{who}' is not in cast.yaml")
            text = self.pair(raw, where, {k: raw.get(k) for k in LANGS}, required=True)
        elif any(k in raw for k in LANGS):
            self.err(raw, where, "speech (ua/de) needs a speaker in 'who'")

        onscreen: dict[str, list[str]] = {}
        if "onscreen" in raw:
            onscreen = self.onscreen(f"{where}.onscreen", raw["onscreen"], raw)
        if who is None and "onscreen" not in raw:
            self.err(raw, where, "needs speech (who + ua + de) or onscreen text")

        shot = raw.get("shot", {})
        if not isinstance(shot, dict):
            self.err(raw, f"{where}.shot", "must be a mapping")
            shot = {}
        for key in sorted(set(shot) - SHOT_KEYS):
            self.err(shot, f"{where}.shot.{key}", "unknown key")
        scene = shot.get("scene")
        if scene is not None and scenes and scene not in scenes:
            self.err(shot, f"{where}.shot.scene", f"'{scene}' is not in scenes")
        if shot.get("eyes", "open") not in EYES:
            self.err(shot, f"{where}.shot.eyes", "must be open or closed")

        pause = raw.get("pause", 0)
        if isinstance(pause, bool) or not isinstance(pause, int | float) or pause < 0:
            self.err(raw, f"{where}.pause", "must be seconds, 0 or more")
            pause = 0
        for key in ("sfx", "action", "note"):
            if key in raw and not isinstance(raw[key], str):
                self.err(raw, f"{where}.{key}", "must be text")

        return Line(
            who=who,
            text=text,
            onscreen=onscreen,
            shot={k: str(v) for k, v in shot.items()},
            sfx=raw.get("sfx"),
            action=raw.get("action"),
            pause=float(pause),
        )

    def onscreen(self, where: str, value: object, parent: object) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            self.err(parent, where, "required: ua and de texts")
            return {}
        out: dict[str, list[str]] = {}
        for lang in LANGS:
            item = value.get(lang)
            items = [item] if isinstance(item, str) else item
            if (
                not isinstance(items, list)
                or not items
                or not all(isinstance(t, str) and t.strip() for t in items)
            ):
                self.err(value, f"{where}.{lang}", "required: text or list of texts")
            else:
                out[lang] = list(items)
        if len(out) == 2 and len(out["ua"]) != len(out["de"]):
            self.err(value, where, "ua and de need the same number of texts")
        for key in sorted(set(value) - set(LANGS)):
            self.err(value, f"{where}.{key}", "unknown language (use ua, de)")
        return out
