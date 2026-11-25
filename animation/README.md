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

Usually you do not call Remotion by hand: `beekeeper render` (or the whole
`beekeeper build`) runs the same render for both languages and skips it when the timeline,
its audio files and `animation/src` did not change (fingerprint in `reel_<lang>.mp4.hash`).

- `src/reel/Reel.tsx`: layers of the reel: camera (scene + characters), phone, speech audio
  and subtitles, sfx, end card.
- `src/reel/shots.ts`: what `shot.camera` means: `phone ...` = phone close-up, `monitor` =
  the laptop screen with the speaker in it, `over-the-shoulder` = code typed on the laptop,
  `close-up` / `push-in` = zoom on the scene's resident, anything else = the whole scene.
- `src/scenes/`: scene library (T07). `index.tsx` maps `shot.scene` to a drawing (`hut`,
  `den`), each with a back layer and a front layer around the characters; `Phone.tsx` and
  `Laptop.tsx` are the device close-ups. A new scene = a new file + one line in `SCENES`.
- `src/characters/`: characters from `characters/*.svg` (T06). `rig.ts` says where each
  head and arm pivots; `Stage.tsx` decides who is on screen per line (scene resident + the
  speaker, nobody in a phone close-up), blinks, breathing, first entrance, and lip flaps from
  `speech.mouth` in the timeline; `stage-layout.ts` holds the positions per scene. A new
  character needs an SVG with the usual part ids and one line in `rig.ts`.
- `src/reel/types.ts`: the timeline format (keep in step with `src/beekeeper/timing.py`).
- `src/reel/theme.ts`: speaker names and colours, fallback background.
- Sound effects (`phone-buzz`, `keyboard`) are synthesized by `beekeeper timing` into the
  episode's `sfx/` folder (`src/beekeeper/sfx.py`), no downloaded samples.
- Inter is bundled from `@fontsource/inter`, so renders work offline.
