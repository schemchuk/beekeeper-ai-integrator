# Free TTS options (research 2026-11-24)

Machine: AMD Ryzen 7 5700U, 16 threads, 14 GB RAM, **no NVIDIA GPU**. So: models that run on
CPU, or a free GPU (Colab / Hugging Face Spaces) for one-off voice work.

## Shortlist

| Model | UA | DE | Voices | Cloning | CPU | License | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Piper (have it) | 3 speakers (1 male) | many: thorsten, thorsten_emotional, karlsson, pavoque, ramona, eva_k, kerstin, mls | presets | no | very fast | GPL code, voices vary | `thorsten_emotional` has amused/angry/drunk/sleepy/whisper styles, great for cartoons |
| [HolosTTS](https://huggingface.co/patriotyk/HolosTTS) (patriotyk) | yes, best open UA | no | presets | yes, from a clip | fast (ONNX INT8) | MIT | Presets taken without owners' consent: for public use clone own voices or mix several |
| [Chatterbox Multilingual V3](https://github.com/resemble-ai/chatterbox) | no | yes | clone | yes, cross-lingual | slow but OK for 40 s | MIT, output watermarked | No longer maintained |
| [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) | yes | yes | voice design by attributes | yes | heavy | weights CC-BY-NC | Non-commercial: experiments only |
| [VoxCPM2](https://huggingface.co/openbmb/VoxCPM2) | no | yes | voice design from text description | yes | needs ~8 GB GPU | Apache-2.0 | Free Colab GPU only |
| Qwen3-TTS | no (ru yes) | yes | VoiceDesign from description | yes | 0.6B maybe on CPU | Apache-2.0 | |
| Edge TTS (online) | Ostap, Polina | many | presets | no | online | unofficial API | Fallback only, ToS grey |

## Proposal

- UA: HolosTTS. Pylyp = Volodymyr's own cloned voice; animals = mixes of preset voices
  plus pitch/tempo processing (bear lower and slower, bee higher and faster).
- DE: Piper (thorsten_emotional and friends) for animals and host; Pylyp = Volodymyr's
  voice cloned into German with Chatterbox (his real accent is part of the joke).
- Audition before choosing: same line, 3-4 candidates per character, UA and DE.
