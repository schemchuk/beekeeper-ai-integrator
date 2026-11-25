import { Composition } from "remotion";
import { Reel, calculateReelMetadata } from "./reel/Reel";

// One composition for every episode: the episode is data (timeline-<lang>.json passed with
// --props), never new code (ADR 004). The default props are a silent 3 s sample.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      durationInFrames={90}
      fps={30}
      width={1080}
      height={1920}
      calculateMetadata={calculateReelMetadata}
      defaultProps={{
        format: 1,
        episode: "000",
        slug: "sample",
        lang: "ua" as const,
        fps: 30,
        duration: 90,
        title: "Зразок",
        scenes: { hut: "Pylyp's hut at night" },
        lines: [
          {
            index: 0,
            who: null,
            start: 0,
            end: 60,
            shot: { scene: "hut" },
            action: null,
            speech: null,
            onscreen: [{ text: "03:12  Медунко: Добрий день 🐻", start: 0, end: 60 }],
            sfx: [],
          },
        ],
        end_card: { text: "Python · TTS · Remotion", start: 68, end: 90 },
      }}
    />
  );
};
