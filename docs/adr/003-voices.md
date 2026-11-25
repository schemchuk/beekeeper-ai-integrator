# 003. Voices: HolosTTS (UA), Chatterbox + Piper (DE)

Status: ACCEPTED (Volodymyr, 2026-11-25); the cast itself was chosen by Volodymyr on 2026-11-24.

## Context

Research and audition: `docs/voices.md`, `out/audition/`, `out/cast.html`. Constraints: free,
CPU, licenses that allow publishing. HolosTTS preset voices were taken without their owners'
consent, so they must not be used as they are.

## Decision

1. Engines per language, settings per character in `characters/cast.yaml`:
   - UA: HolosTTS. Pylyp is cloned from Volodymyr's own recording; animals are mixes of two
     preset voices plus pitch/tempo (`fx`), so no single real person's voice is reproduced.
   - DE: Pylyp is Volodymyr's voice cloned into German with Chatterbox (his accent is part of
     the character); animals use Piper voices with the same `fx`.
2. Post-processing with ffmpeg rubberband (`fx`), loudness normalised per line, 48 kHz.
3. The engines sit behind one small interface (`synthesize(text, voice) -> wav`), so an engine
   can be swapped per character in `cast.yaml` without code changes.
4. Every reel carries the AI label in postpilot (voices and picture are generated).

## Consequences

- Chatterbox output is watermarked by its authors; fine, the reel is labelled AI anyway.
- Chatterbox is no longer maintained; the interface in 3 keeps a replacement cheap.
- New characters need an audition before they get a line.
