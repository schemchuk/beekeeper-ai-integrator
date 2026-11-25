"""TTS engines behind one interface: `engine.say(text, voice, dst)` writes a wav (ADR 003).

Models are heavy, so each engine loads lazily once per process. Imports of torch, holos and
chatterbox happen only when an engine is used, so tests and CI do not need them.
"""

import json
import os
import subprocess
from functools import cache
from pathlib import Path
from typing import Protocol

from beekeeper.voices.cast import Voice

TTS_HOME = Path(os.environ.get("BEEKEEPER_TTS_HOME", Path.home() / "tts"))
PIPER_PYTHON = Path(os.environ.get("BEEKEEPER_PIPER_PYTHON", TTS_HOME / "bin" / "python"))
PIPER_MODEL_DIRS = (TTS_HOME / "reel_de", TTS_HOME / "reel", TTS_HOME)


class Engine(Protocol):
    def say(self, text: str, voice: Voice, dst: Path) -> None: ...


class Piper:
    def say(self, text: str, voice: Voice, dst: Path) -> None:
        model = self.model(voice.params["model"])
        cmd = [str(PIPER_PYTHON), "-m", "piper", "-m", str(model), "-f", str(dst)]
        speaker = voice.params.get("speaker")
        if speaker is not None:
            cmd += ["-s", str(self.speaker_id(model, speaker))]
        if voice.lang == "ua":
            text = text.lower()  # the Ukrainian Piper model drops capitals
        subprocess.run(cmd, input=text, text=True, check=True, capture_output=True)

    @staticmethod
    def model(name: str) -> Path:
        for d in PIPER_MODEL_DIRS:
            p = d / f"{name}.onnx"
            if p.exists():
                return p
        raise FileNotFoundError(
            f"Piper model {name}.onnx not in {[str(d) for d in PIPER_MODEL_DIRS]}"
        )

    @staticmethod
    def speaker_id(model: Path, speaker: int | str) -> int:
        if isinstance(speaker, int):
            return speaker
        ids = json.loads(Path(f"{model}.json").read_text()).get("speaker_id_map", {})
        if speaker not in ids:
            raise ValueError(f"{model.name}: no speaker '{speaker}', have {sorted(ids)}")
        return ids[speaker]


class Holos:
    """HolosTTS (Ukrainian). `voice: clone` + `ref`, or a list of preset names to mix."""

    SR = 24000

    @cache  # noqa: B019 - one model per process is the point
    def _model(self):
        from holos.models import HolosTTS
        from ipa_uk import ipa
        from ukrainian_word_stress import Stressifier

        return HolosTTS("patriotyk/HolosTTS", device="cpu"), Stressifier(), ipa

    @cache  # noqa: B019
    def _clone(self, ref: str):
        import torch
        from holos.models import VoiceEncoder

        enc = VoiceEncoder("patriotyk/HolosTTS", device="cpu")
        with torch.inference_mode():
            return enc(ref).squeeze()

    def say(self, text: str, voice: Voice, dst: Path) -> None:
        import soundfile as sf
        import torch

        model, stress, ipa = self._model()
        spec = voice.params.get("voice")
        if spec == "clone":
            embedding = self._clone(str(Path(voice.params["ref"]).resolve()))
        elif isinstance(spec, list) and spec:
            embedding = torch.stack([model.voices[n] for n in spec]).mean(0)
        else:
            raise ValueError(f"{voice.character}.{voice.lang}: holos voice must be clone or a list")
        with torch.inference_mode():
            audio = model.generate(
                ipa(stress(text)), voice=embedding, speed=float(voice.params.get("speed", 1.0))
            )
        sf.write(dst, audio.squeeze().cpu().numpy(), self.SR)


class Chatterbox:
    """Chatterbox Multilingual: Volodymyr's voice cloned into German from `ref`."""

    @cache  # noqa: B019
    def _model(self):
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        # Checkpoints were saved on CUDA; Chatterbox calls torch.load without map_location.
        load = torch.load
        torch.load = lambda *a, **k: load(*a, **{**k, "map_location": torch.device("cpu")})
        try:
            return ChatterboxMultilingualTTS.from_pretrained(device=torch.device("cpu"))
        finally:
            torch.load = load

    def say(self, text: str, voice: Voice, dst: Path) -> None:
        import soundfile as sf
        import torch

        model = self._model()
        with torch.inference_mode():
            wav = model.generate(
                text,
                language_id="de",
                audio_prompt_path=voice.params["ref"],
                exaggeration=float(voice.params.get("exaggeration", 0.5)),
                cfg_weight=0.5,
            )
        sf.write(dst, wav.squeeze().cpu().numpy(), model.sr)


@cache
def default_engines() -> dict[str, Engine]:
    return {"piper": Piper(), "holos": Holos(), "chatterbox": Chatterbox()}
