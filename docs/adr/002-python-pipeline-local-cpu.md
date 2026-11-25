# 002. Python pipeline, run locally on CPU

Status: ACCEPTED (Volodymyr, 2026-11-25)

## Context

The machine is a Ryzen 7 5700U, 14 GB RAM, no NVIDIA GPU (`docs/product.md` §8). The TTS
engines already installed (HolosTTS, Chatterbox, Piper) are Python. Budget: free first.
CLAUDE.md prefers Python for the pipeline.

## Decision

1. The pipeline is a Python package with one CLI, `beekeeper build episodes/NNN-slug`,
   steps: `voices -> timing -> render -> check`. Each step can run alone and skips work whose
   inputs did not change (hash of the line text + voice settings), so a one-line edit
   re-voices one line.
2. Runs on Volodymyr's laptop, CPU only. No cloud render, no paid service.
3. Animation is the one Node/JS part (ADR 004); Python calls it as a subprocess and passes
   a generated JSON (lines, timings, wav paths, scene).
4. `check` validates the reel against the output contract: MP4 H.264 yuv420p, 1080x1920,
   30 fps, AAC 48 kHz, 3-90 s, under 20 MB (`docs/product.md` §8). A failed check stops the
   handoff.

## Consequences

- The laptop must be on when an episode is built (the day before release, ADR 005).
- Chatterbox is slow on CPU; caching per line keeps rebuilds short.
- Tests: unit tests for timing and the YAML schema; a short smoke episode for the full build.
