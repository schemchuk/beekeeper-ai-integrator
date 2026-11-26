import { Composition, Still } from "remotion";
import { CoverStill } from "./reel/Cover";
import { Reel, calculateReelMetadata } from "./reel/Reel";
import type { Timeline } from "./reel/types";

// One composition for every episode: the episode is data (timeline-<lang>.json passed with
// --props), never new code (ADR 004). The default props are a silent 3 s sample.
const SAMPLE: Timeline = {
  format: 1,
  episode: "000",
  slug: "sample",
  lang: "ua",
  fps: 30,
  duration: 90,
  title: "Зразок",
  scenes: { hut: "Pylyp's hut at night" },
  cover: {
    title: "Зразок",
    monitor: "Ваш запит збережено.",
    who: ["pylyp", "medunko"],
    start: 0,
    end: 15,
  },
  lines: [
    {
      index: 0,
      who: null,
      start: 15,
      end: 60,
      shot: { scene: "hut" },
      action: null,
      speech: null,
      onscreen: [
        { text: "03:12  Медунко: Добрий день 🐻", start: 15, end: 60 },
      ],
      sfx: [],
    },
  ],
  end_card: { text: "Python · TTS · Remotion", start: 68, end: 90 },
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Reel"
        component={Reel}
        durationInFrames={90}
        fps={30}
        width={1080}
        height={1920}
        calculateMetadata={calculateReelMetadata}
        defaultProps={SAMPLE}
      />
      <Still
        id="Cover"
        component={CoverStill}
        width={1080}
        height={1920}
        defaultProps={SAMPLE}
      />
    </>
  );
};
