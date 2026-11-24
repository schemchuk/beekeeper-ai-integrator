"""Chatterbox Multilingual: Volodymyr's voice cloned into German (and UA-accented German)."""

from pathlib import Path

import soundfile as sf
import torch


def run(render, lines, ref: Path) -> None:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    # Checkpoints were saved on CUDA; Chatterbox calls torch.load without map_location.
    _load = torch.load
    torch.load = lambda *a, **k: _load(*a, **{**k, "map_location": torch.device("cpu")})
    model = ChatterboxMultilingualTTS.from_pretrained(device=torch.device("cpu"))

    def say(text: str, dst: Path, prompt: Path, exaggeration: float) -> None:
        with torch.inference_mode():
            wav = model.generate(text, language_id="de", audio_prompt_path=str(prompt),
                                 exaggeration=exaggeration, cfg_weight=0.5)
        sf.write(dst, wav.squeeze().cpu().numpy(), model.sr)

    samples = sorted(ref.parent.glob("volodymyr_*.wav"))
    for i, prompt in enumerate(samples, 1):
        render("pylyp", "de", f"chatterbox-clone-sample{i}",
               lambda t, d, p=prompt: say(t, d, p, 0.5), None)
    render("pylyp", "de", "chatterbox-clone-sample2-expressive",
           lambda t, d: say(t, d, samples[-1], 0.8), None)
