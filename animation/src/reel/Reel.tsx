import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Stage } from "../characters/Stage";
import { fontFamily } from "./fonts";
import { DEFAULT_BG, SAFE_X, SCENE_BG, SPEAKER } from "./theme";
import type { OnscreenItem, Speech, Timeline, TimelineLine } from "./types";

export const calculateReelMetadata: CalculateMetadataFunction<Timeline> = ({ props }) => ({
  durationInFrames: Math.max(1, props.duration),
  fps: props.fps,
  defaultOutName: `reel_${props.lang}`,
});

// The scene stays up until the next line starts, so the breath between lines is not black.
const sceneSpans = (t: Timeline) =>
  t.lines.map((line, i) => {
    const next = t.lines[i + 1]?.start ?? t.end_card?.start ?? t.duration;
    return { line, from: line.start, duration: Math.max(1, next - line.start) };
  });

export const Reel: React.FC<Timeline> = (timeline) => {
  const { lang } = timeline;
  return (
    <AbsoluteFill style={{ fontFamily, backgroundColor: DEFAULT_BG[0] }}>
      {sceneSpans(timeline).map(({ line, from, duration }) => (
        <Sequence key={line.index} from={from} durationInFrames={duration} name={`line ${line.index}`}>
          <SceneBackground scene={line.shot.scene} />
        </Sequence>
      ))}
      <Stage timeline={timeline} />
      {sceneSpans(timeline)
        .filter(({ line }) => line.onscreen.length > 0)
        .map(({ line, from, duration }) => (
          <Sequence key={`messages-${line.index}`} from={from} durationInFrames={duration} name={`messages ${line.index}`}>
            <Messages line={line} />
          </Sequence>
        ))}
      {timeline.lines
        .filter((line): line is TimelineLine & { speech: Speech } => line.speech !== null)
        .map(({ index, who, speech }) => (
          <Sequence
            key={`speech-${index}`}
            from={speech.start}
            durationInFrames={speech.end - speech.start}
            name={`${who} ${index}`}
          >
            <Audio src={staticFile(speech.audio)} />
            <Subtitle who={who ?? ""} text={speech.text} lang={lang} />
          </Sequence>
        ))}
      {timeline.end_card ? (
        <Sequence
          from={timeline.end_card.start}
          durationInFrames={timeline.end_card.end - timeline.end_card.start}
          name="end card"
        >
          <EndCard text={timeline.end_card.text} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};

const SceneBackground: React.FC<{ scene?: string }> = ({ scene }) => {
  const [top, bottom] = (scene && SCENE_BG[scene]) || DEFAULT_BG;
  return <AbsoluteFill style={{ background: `linear-gradient(180deg, ${top}, ${bottom})` }} />;
};

// "[бзз]" in a line is Bsinka's bleep: shown as a highlighted marker, not as plain text.
const withBleeps = (text: string) =>
  text.split(/(\[[^\]]*\])/).map((part, i) =>
    part.startsWith("[") ? (
      <span key={i} style={{ color: SPEAKER.bzynka.color }}>
        {part}
      </span>
    ) : (
      part
    ),
  );

const Subtitle: React.FC<{ who: string; text: string; lang: "de" | "ua" }> = ({ who, text, lang }) => {
  const frame = useCurrentFrame();
  const speaker = SPEAKER[who];
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 460 }}>
      <div
        style={{
          margin: `0 ${SAFE_X}px`,
          padding: "28px 40px",
          borderRadius: 32,
          backgroundColor: "rgba(0, 0, 0, 0.62)",
          textAlign: "center",
          opacity: interpolate(frame, [0, 4], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div style={{ color: speaker?.color ?? "#fff", fontSize: 40, fontWeight: 800, marginBottom: 8 }}>
          {speaker?.name[lang] ?? who}
        </div>
        <div style={{ color: "#fff", fontSize: 58, fontWeight: 700, lineHeight: 1.25 }}>
          {withBleeps(text)}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Messages: React.FC<{ line: TimelineLine }> = ({ line }) => (
  <AbsoluteFill
    style={{ justifyContent: "center", alignItems: "center", gap: 28, padding: `0 ${SAFE_X}px` }}
  >
    {line.onscreen.map((item, k) => (
      <Sequence key={k} from={item.start - line.start} layout="none">
        <Bubble item={item} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

const Bubble: React.FC<{ item: OnscreenItem }> = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div
      style={{
        maxWidth: "100%",
        padding: "30px 44px",
        borderRadius: 40,
        backgroundColor: "#f5f1e6",
        color: "#1b1b1f",
        fontSize: 56,
        fontWeight: 700,
        lineHeight: 1.3,
        textAlign: "center",
        scale: interpolate(frame, [0, 0.25 * fps], [0.6, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.spring({ damping: 12 }),
          output: "perceptual-scale",
        }),
        opacity: interpolate(frame, [0, 3], [0, 1], { extrapolateRight: "clamp" }),
      }}
    >
      {item.text}
    </div>
  );
};

const EndCard: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #1b1407, #3d2c0a)",
        justifyContent: "center",
        alignItems: "center",
        padding: `0 ${SAFE_X + 20}px`,
      }}
    >
      <div
        style={{
          color: "#f2b632",
          fontSize: 64,
          fontWeight: 800,
          lineHeight: 1.3,
          textAlign: "center",
          opacity: interpolate(frame, [0, 0.5 * fps], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
