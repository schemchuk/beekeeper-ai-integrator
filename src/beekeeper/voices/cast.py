"""Voice settings per character and language from `characters/cast.yaml` (ADR 003)."""

from dataclasses import dataclass, field
from pathlib import Path

from beekeeper import yamlio

ENGINES = {"holos", "chatterbox", "piper"}


@dataclass(frozen=True)
class Voice:
    character: str
    lang: str
    engine: str
    params: dict = field(default_factory=dict)  # engine-specific: voice, ref, model, speaker...
    fx: tuple[float, float] | None = None  # (pitch ratio, tempo ratio), rubberband


class CastError(Exception):
    pass


def load_voices(path: Path) -> dict[tuple[str, str], Voice]:
    data = yamlio.load(path)
    if not isinstance(data, dict):
        raise CastError(f"{path}: expected a mapping of characters")
    voices = {}
    for char, langs in data.items():
        if not isinstance(langs, dict):
            raise CastError(f"{path}:{yamlio.line_of(langs)}: {char}: expected ua/de settings")
        for lang, raw in langs.items():
            where = f"{path}:{yamlio.line_of(raw)}: {char}.{lang}"
            if not isinstance(raw, dict) or raw.get("engine") not in ENGINES:
                raise CastError(f"{where}: engine must be one of {sorted(ENGINES)}")
            params = {k: v for k, v in raw.items() if k not in ("engine", "fx")}
            fx = raw.get("fx")
            if fx is not None:
                if not (isinstance(fx, list) and len(fx) == 2 and all(v > 0 for v in fx)):
                    raise CastError(f"{where}: fx must be [pitch, tempo], both > 0")
                fx = (float(fx[0]), float(fx[1]))
            voices[(char, lang)] = Voice(char, lang, raw["engine"], params, fx)
    return voices
