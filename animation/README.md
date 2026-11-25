# animation

Remotion project (ADR 004) that turns one `timeline-<lang>.json` from `beekeeper timing`
into a 1080x1920, 30 fps reel. One composition, `Reel`, serves every episode: the episode is
data, passed with `--props`; the episode's `out/` folder is the public dir, so the audio
paths in the timeline resolve as they are.

```zsh
npm ci
EP=../out/002-medunko-v-splyachtsi

# preview in Remotion Studio
npx remotion studio --props=$EP/timeline-de.json --public-dir=$EP

# render one language
npx remotion render Reel $EP/reel_de.mp4 --props=$EP/timeline-de.json --public-dir=$EP

# checks
npm run lint
```

`beekeeper build` will call the render for both languages (T08).

- `src/reel/Reel.tsx`: scenes, speech audio, subtitles, on-screen messages, end card.
- `src/reel/types.ts`: the timeline format (keep in step with `src/beekeeper/timing.py`).
- `src/reel/theme.ts`: placeholder scene colours and speaker names until T06-T07.
- Inter is bundled from `@fontsource/inter`, so renders work offline.
