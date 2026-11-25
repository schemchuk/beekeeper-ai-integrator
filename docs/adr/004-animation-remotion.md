# 004. Animation and assembly with Remotion

Status: PROPOSED (2026-11-25); Remotion was agreed with Volodymyr on 2026-11-24.

## Context

The old reels used a static PNG with subtitles. The characters exist as SVG
(`characters/*.svg`). We need lip/pose changes, simple moves and burned-in subtitles, rendered
for free on CPU, in the same way for every episode.

## Decision

1. Remotion (React) renders the picture, subtitles and audio into the final MP4 in one go,
   locally (`npx remotion render`), 1080x1920, 30 fps.
2. Characters and scenes are React components built from the SVG parts; an episode is data
   (the JSON from ADR 002), not new code. A new scene is a new component in a scene library.
3. Subtitles are drawn by Remotion from the timings (Inter font), one language per render:
   two renders per episode, DE and UA, same picture.
4. Remotion's license: free for individuals and small teams; Volodymyr qualifies. Check again
   before any company use.

## Consequences

- Node and Chromium are needed locally (already installed with the Remotion skills).
- Rendering on CPU takes minutes per reel; acceptable for two episodes a week.
- Picture quality is limited by the SVG art; better art later does not change the pipeline.
