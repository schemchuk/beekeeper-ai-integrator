"""ffmpeg post-processing: pitch/tempo (rubberband), loudness, 48 kHz mono; durations."""

import shutil
import subprocess
from pathlib import Path

SAMPLE_RATE = 48000
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"
# Cut silence at both ends so timing follows the speech, not the engine's padding.
_TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
TRIM = f"{_TRIM},areverse,{_TRIM},areverse"
BLEEP_SECONDS = 0.35


def _ffmpeg(*args: str) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def finish(src: Path, dst: Path, fx: tuple[float, float] | None) -> None:
    """Trim silence, apply fx, normalise loudness, write 48 kHz mono 16-bit wav to dst."""
    filters = [TRIM]
    if fx:
        filters.append(f"rubberband=pitch={fx[0]}:tempo={fx[1]}")
    filters.append(LOUDNESS)
    _ffmpeg(
        "-i",
        str(src),
        "-af",
        ",".join(filters),
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(dst),
    )


def bleep(dst: Path, seconds: float = BLEEP_SECONDS) -> None:
    """A censor beep (1 kHz) used for `[...]` markers in a line."""
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=1000:duration={seconds}:sample_rate={SAMPLE_RATE}",
        "-af",
        "volume=0.3",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(dst),
    )


def concat(parts: list[Path], dst: Path) -> None:
    """Join wav parts (any rate) into one 48 kHz mono wav."""
    if len(parts) == 1:
        _ffmpeg(
            "-i", str(parts[0]), "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)
        )
        return
    inputs = [arg for p in parts for arg in ("-i", str(p))]
    streams = "".join(
        f"[{i}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=mono[a{i}];"
        for i in range(len(parts))
    )
    joined = "".join(f"[a{i}]" for i in range(len(parts)))
    _ffmpeg(
        *inputs,
        "-filter_complex",
        f"{streams}{joined}concat=n={len(parts)}:v=0:a=1[out]",
        "-map",
        "[out]",
        "-c:a",
        "pcm_s16le",
        str(dst),
    )


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout.strip())
