"""Check step (ADR 002 §4): does a reel meet the output contract (`docs/product.md` §8)?

MP4 with H.264 yuv420p video, 1080x1920, 30 fps, AAC 48 kHz audio, 3-90 s, under 20 MB.
A failed check stops the handoff, so every broken rule is reported, not just the first.
"""

import json
import subprocess
from fractions import Fraction
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920
FPS = 30
SAMPLE_RATE = 48000
MIN_SECONDS, MAX_SECONDS = 3.0, 90.0
MAX_BYTES = 20 * 1024 * 1024


def probe(path: Path) -> dict:
    """ffprobe the file as JSON (format + streams)."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size:"
            "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate,sample_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def problems(info: dict) -> list[str]:
    """Every way the probed file breaks the contract; empty when it passes."""
    found: list[str] = []
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    if "mp4" not in fmt.get("format_name", "").split(","):
        found.append(f"container is {fmt.get('format_name', '?')}, want mp4")

    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        found.append(f"{len(videos)} video streams, want 1")
    else:
        v = videos[0]
        if v.get("codec_name") != "h264":
            found.append(f"video codec {v.get('codec_name')}, want h264")
        if v.get("pix_fmt") != "yuv420p":
            found.append(f"pixel format {v.get('pix_fmt')}, want yuv420p")
        if (v.get("width"), v.get("height")) != (WIDTH, HEIGHT):
            found.append(f"size {v.get('width')}x{v.get('height')}, want {WIDTH}x{HEIGHT}")
        rate = Fraction(v.get("r_frame_rate", "0/1"))
        if rate != FPS:
            found.append(f"frame rate {float(rate):g} fps, want {FPS}")
    if len(audios) != 1:
        found.append(f"{len(audios)} audio streams, want 1")
    else:
        a = audios[0]
        if a.get("codec_name") != "aac":
            found.append(f"audio codec {a.get('codec_name')}, want aac")
        if int(a.get("sample_rate", 0)) != SAMPLE_RATE:
            found.append(f"sample rate {a.get('sample_rate')} Hz, want {SAMPLE_RATE}")

    seconds = float(fmt.get("duration", 0))
    if not MIN_SECONDS <= seconds <= MAX_SECONDS:
        found.append(f"length {seconds:.1f} s, want {MIN_SECONDS:g}-{MAX_SECONDS:g} s")
    size = int(fmt.get("size", 0))
    if size >= MAX_BYTES:
        found.append(f"size {size / 1024 / 1024:.1f} MB, want under {MAX_BYTES // 1024 // 1024} MB")
    return found


def check_reel(path: Path) -> tuple[list[str], dict]:
    """Problems of one reel plus the probe, so a pass can still print what it saw."""
    if not path.is_file():
        return [f"{path}: not found"], {}
    try:
        info = probe(path)
    except ValueError as e:
        return [f"{path}: {e}"], {}
    return [f"{path}: {p}" for p in problems(info)], info


def summary(info: dict) -> str:
    fmt = info.get("format", {})
    return f"{float(fmt.get('duration', 0)):.1f} s, {int(fmt.get('size', 0)) / 1024 / 1024:.1f} MB"
