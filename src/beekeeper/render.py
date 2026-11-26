"""Render step (ADR 002 §3, ADR 004): Remotion turns `timeline-<lang>.json` into `reel_<lang>.mp4`
and the cover still `cover_<lang>.png` (the thumbnail, BRIEF cover rule).

Python calls the Remotion CLI in `animation/` as a subprocess, with the episode's out folder
as the public dir (the audio paths in the timeline are relative to it). A render is slow on
CPU, so it is skipped when nothing it reads changed: the timeline, the audio files the
timeline names, and the animation sources. The fingerprint sits next to the reel.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ANIMATION = Path("animation")
COMPOSITION = "Reel"
COVER_COMPOSITION = "Cover"
# Inputs of the animation project besides `src/`: a dependency bump changes the picture too.
ANIMATION_FILES = ("package-lock.json", "remotion.config.ts")


class RenderError(Exception):
    pass


def reel_path(ep_dir: Path, lang: str) -> Path:
    return ep_dir / f"reel_{lang}.mp4"


def cover_path(ep_dir: Path, lang: str) -> Path:
    return ep_dir / f"cover_{lang}.png"


def fingerprint(timeline_path: Path, ep_dir: Path, animation: Path) -> str:
    h = hashlib.sha256()

    def add(path: Path, name: str) -> None:
        h.update(name.encode() + b"\0")
        h.update(path.read_bytes() if path.is_file() else b"<missing>")
        h.update(b"\0")

    add(timeline_path, "timeline")
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    for audio in sorted(_audio_paths(timeline)):
        add(ep_dir / audio, f"audio:{audio}")
    for name in ANIMATION_FILES:
        add(animation / name, f"animation:{name}")
    src = animation / "src"
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        add(path, f"animation:{path.relative_to(animation).as_posix()}")
    return h.hexdigest()


def _audio_paths(node: object) -> set[str]:
    """Every `audio` value anywhere in the timeline (speech lines, sfx events)."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "audio" and isinstance(value, str):
                found.add(value)
            else:
                found |= _audio_paths(value)
    elif isinstance(node, list):
        for item in node:
            found |= _audio_paths(item)
    return found


def command(timeline_path: Path, ep_dir: Path, reel: Path) -> list[str]:
    return [
        "npx",
        "--no-install",
        "remotion",
        "render",
        COMPOSITION,
        str(reel.resolve()),
        f"--props={timeline_path.resolve()}",
        f"--public-dir={ep_dir.resolve()}",
        "--codec=h264",
        "--pixel-format=yuv420p",
        "--audio-codec=aac",
        "--sample-rate=48000",
    ]


def cover_command(timeline_path: Path, ep_dir: Path, cover: Path) -> list[str]:
    return [
        "npx",
        "--no-install",
        "remotion",
        "still",
        COVER_COMPOSITION,
        str(cover.resolve()),
        f"--props={timeline_path.resolve()}",
        f"--public-dir={ep_dir.resolve()}",
        "--image-format=png",
    ]


def render(
    ep_dir: Path, lang: str, animation: Path = ANIMATION, force: bool = False
) -> tuple[Path, bool]:
    """Render one language; returns the reel path and whether it was rendered (not cached)."""
    return _render(ep_dir, lang, animation, force, reel_path(ep_dir, lang), command, "render")


def render_cover(
    ep_dir: Path, lang: str, animation: Path = ANIMATION, force: bool = False
) -> tuple[Path, bool]:
    """Render the cover still of one language, cached like the reel."""
    out = cover_path(ep_dir, lang)
    return _render(ep_dir, lang, animation, force, out, cover_command, "still")


def _render(ep_dir, lang, animation, force, out, make_command, what) -> tuple[Path, bool]:
    timeline_path = ep_dir / f"timeline-{lang}.json"
    if not timeline_path.is_file():
        raise RenderError(f"{timeline_path}: not found, run `beekeeper timing` first")
    if not (animation / "node_modules").is_dir():
        raise RenderError(f"{animation}/node_modules missing, run `npm ci` in {animation}")
    stamp = out.with_suffix(out.suffix + ".hash")
    digest = fingerprint(timeline_path, ep_dir, animation)
    if not force and out.is_file() and stamp.is_file() and stamp.read_text().strip() == digest:
        return out, False

    stamp.unlink(missing_ok=True)
    sys.stdout.flush()  # our earlier lines first, then Remotion's progress
    result = subprocess.run(make_command(timeline_path, ep_dir, out), cwd=animation)
    if result.returncode != 0 or not out.is_file():
        raise RenderError(f"remotion {what} failed for {lang} (exit {result.returncode})")
    stamp.write_text(digest + "\n")
    return out, True
