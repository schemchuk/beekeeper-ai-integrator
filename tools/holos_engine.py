"""HolosTTS (Ukrainian) candidates for the audition.

Preset voices are unnamed; we sort them by median pitch, then mix two neighbours per animal
so no single real speaker is recognizable (the model author's advice for public use).
Pylyp is cloned from Volodymyr's own recordings.
"""

import subprocess
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

SR = 24000


def run(render, lines, ref: Path, fx) -> None:
    from holos.models import HolosTTS, VoiceEncoder
    from ipa_uk import ipa
    from ukrainian_word_stress import Stressifier

    fx_bee, fx_bear, fx_wolf, fx_hedgehog = fx
    model = HolosTTS("patriotyk/HolosTTS", device="cpu")
    stress = Stressifier()

    def say(text: str, voice, dst: Path, speed: float = 1.0) -> None:
        with torch.inference_mode():
            audio = model.generate(ipa(stress(text)), voice=voice, speed=speed)
        sf.write(dst, audio.squeeze().cpu().numpy(), SR)

    # Rank anonymous presets by pitch.
    probe = ipa(stress("Добрий день, як справи на пасіці?"))
    pitch = {}
    for name in model.list_voices():
        if not name.startswith("Speaker_"):
            continue  # named presets are real people: skip
        with torch.inference_mode():
            audio = model.generate(probe, voice=name).squeeze().cpu().numpy()
        f0 = librosa.yin(audio, fmin=60, fmax=400, sr=SR)
        pitch[name] = float(np.median(f0))
    ranked = sorted(pitch, key=pitch.get)
    print("pitch ranking:", [(n, round(pitch[n])) for n in ranked])
    low, high = ranked[:8], ranked[-6:]

    def mix(*names):
        return torch.stack([model.voices[n] for n in names]).mean(0)

    # Pylyp: Volodymyr's own voice.
    enc = VoiceEncoder("patriotyk/HolosTTS", device="cpu")
    samples = sorted(ref.parent.glob("volodymyr_*.wav"))
    with torch.inference_mode():
        clones = [enc(str(p)).squeeze() for p in samples]
    clone_mix = torch.stack(clones).mean(0)
    for i, c in enumerate(clones, 1):
        render("pylyp", "ua", f"holos-clone-sample{i}", lambda t, d, c=c: say(t, c, d), None)
    render("pylyp", "ua", "holos-clone-both", lambda t, d: say(t, clone_mix, d), None)

    cands = [
        ("medunko", "holos-mix-low01-bear", mix(low[0], low[1]), fx_bear, 0.9),
        ("medunko", "holos-low0-bear", model.voices[low[0]], fx_bear, 0.9),
        ("siryi", "holos-mix-low23-wolf", mix(low[2], low[3]), fx_wolf, 1.0),
        ("siryi", "holos-mix-low45-wolf", mix(low[4], low[5]), fx_wolf, 1.0),
        ("koliuchka", "holos-mix-low67-hedgehog", mix(low[6], low[7]), fx_hedgehog, 1.1),
        ("bzynka", "holos-mix-high01-bee", mix(high[-1], high[-2]), fx_bee, 1.1),
        ("bzynka", "holos-mix-high23-bee", mix(high[-3], high[-4]), fx_bee, 1.1),
        ("bzynka", "holos-high0-plain", model.voices[high[-1]], None, 1.15),
    ]
    for char, label, voice, f, speed in cands:
        render(char, "ua", label, lambda t, d, v=voice, s=speed: say(t, v, d, s), f)
