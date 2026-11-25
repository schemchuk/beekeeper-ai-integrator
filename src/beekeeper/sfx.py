"""Sound effects, synthesized: no downloaded samples, no licences, same bytes on every run.

Each effect is a function that returns 16-bit mono samples at 48 kHz. `write_sfx` writes the
ones an episode uses to `out/NNN-slug/sfx/<name>.wav`, which the timeline points at.
"""

import math
import random
import wave
from array import array
from collections.abc import Callable
from pathlib import Path

RATE = 48000
PEAK = 0.35  # effects sit under the voices (voices are normalized louder by the voice step)


def _envelope(n: int, total: int, attack: int, release: int) -> float:
    if n < attack:
        return n / attack
    if n > total - release:
        return max(0.0, (total - n) / release)
    return 1.0


def phone_buzz() -> list[float]:
    """Two short pulses of a vibration motor rattling on a wooden table."""
    out: list[float] = []
    pulse, gap = int(0.16 * RATE), int(0.07 * RATE)
    for _ in range(2):
        for n in range(pulse):
            t = n / RATE
            hum = sum(math.sin(2 * math.pi * 165 * k * t) / k for k in (1, 3, 5, 7))
            rattle = 0.6 + 0.4 * math.sin(2 * math.pi * 31 * t)
            out.append(hum * rattle * _envelope(n, pulse, RATE // 200, RATE // 40))
        out.extend([0.0] * gap)
    return out


def keyboard() -> list[float]:
    """1.6 s of fast typing: short clicks at uneven intervals, now and then a heavier key."""
    rng = random.Random(7)
    total = int(1.6 * RATE)
    out = [0.0] * total
    pos = 0
    while pos < total:
        heavy = rng.random() < 0.12
        length = int((0.03 if heavy else 0.015) * RATE)
        gain = rng.uniform(0.5, 1.0) * (1.4 if heavy else 1.0)
        prev = 0.0
        for n in range(min(length, total - pos)):
            noise = rng.uniform(-1, 1)
            click = noise - 0.85 * prev  # crude high-pass: a tick, not a hiss
            prev = noise
            out[pos + n] += gain * click * math.exp(-n / (length / 5))
        pos += int(rng.uniform(0.06, 0.14) * RATE)
    return out


LIBRARY: dict[str, Callable[[], list[float]]] = {
    "phone-buzz": phone_buzz,
    "keyboard": keyboard,
}


def to_pcm(samples: list[float]) -> array:
    peak = max((abs(s) for s in samples), default=0.0) or 1.0
    return array("h", (int(32767 * PEAK * s / peak) for s in samples))


def write_sfx(names: set[str], out_dir: Path) -> dict[str, str]:
    """Write each named effect; return name -> path relative to `out_dir`.

    Unknown names raise KeyError with the list of known ones.
    """
    unknown = sorted(names - LIBRARY.keys())
    if unknown:
        raise KeyError(f"unknown sfx {', '.join(unknown)}; known: {', '.join(sorted(LIBRARY))}")
    folder = out_dir / "sfx"
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in sorted(names):
        path = folder / f"{name}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(to_pcm(LIBRARY[name]()).tobytes())
        paths[name] = f"sfx/{name}.wav"
    return paths
