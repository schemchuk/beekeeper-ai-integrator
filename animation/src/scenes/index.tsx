import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { hasRig } from "../characters/Character";
import { slotFor } from "../characters/Stage";
import { faceOf } from "../characters/stage-layout";
import { Span, framing, residents, spanAt, spans, zoom } from "../reel/shots";
import { DEFAULT_BG } from "../reel/theme";
import type { Timeline } from "../reel/types";
import { DenBack, DenFront } from "./Den";
import { HutBack, HutFront } from "./Hut";
import { LaptopBack, LaptopFront } from "./Laptop";
import type { Scene, SceneProps } from "./types";

// Scene library: `shot.scene` in episode.yaml -> drawing. A new scene is a new entry here
// (ADR 004); an unknown scene falls back to a plain gradient.
export const SCENES: Record<string, Scene> = {
  hut: { Back: HutBack, Front: HutFront },
  den: { Back: DenBack, Front: DenFront },
};

const Plain: React.FC<SceneProps> = () => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(180deg, ${DEFAULT_BG[0]}, ${DEFAULT_BG[1]})`,
    }}
  />
);

// One layer of one line's picture. Inside a Sequence, so the absolute frame is rebuilt.
export const ShotLayer: React.FC<{ span: Span; layer: "back" | "front" }> = ({
  span,
  layer,
}) => {
  const frame = useCurrentFrame() + span.from;
  const props: SceneProps = {
    frame,
    line: span.line,
    from: span.from,
    to: span.to,
  };
  const kind = framing(span.line);
  if (kind === "monitor" || kind === "code") {
    const mode = kind;
    return layer === "back" ? (
      <LaptopBack {...props} mode={mode} />
    ) : (
      <LaptopFront {...props} mode={mode} />
    );
  }
  const scene = SCENES[span.line.shot.scene ?? ""];
  if (kind === "phone") {
    // The phone covers the screen; the scene stays behind it, out of focus.
    if (layer === "front" || !scene)
      return layer === "back" ? <Plain {...props} /> : null;
    return (
      <AbsoluteFill style={{ filter: "blur(18px)", transform: "scale(1.08)" }}>
        <scene.Back {...props} />
        {scene.Front ? <scene.Front {...props} /> : null}
      </AbsoluteFill>
    );
  }
  if (layer === "back")
    return scene ? <scene.Back {...props} /> : <Plain {...props} />;
  return scene?.Front ? <scene.Front {...props} /> : null;
};

// Zooms the scene and the characters together on the resident's face ("close-up",
// "slow push-in"); subtitles and the phone stay outside, so they never scale.
export const Camera: React.FC<{
  timeline: Timeline;
  children: React.ReactNode;
}> = ({ timeline, children }) => {
  const frame = useCurrentFrame();
  const span = spanAt(spans(timeline), frame);
  let transform = "none";
  let origin = "50% 50%";
  if (span && framing(span.line) === "scene") {
    const { from, to } = zoom(span.line);
    const scale = interpolate(frame, [span.from, span.to], [from, to], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    const scene = span.line.shot.scene;
    const who = scene ? residents(timeline, hasRig)[scene] : undefined;
    if (who && scale !== 1) {
      const face = faceOf(slotFor(span.line, who, true));
      origin = `${face.x}px ${face.y}px`;
      transform = `scale(${scale})`;
    }
  }
  return (
    <AbsoluteFill
      style={{ transform, transformOrigin: origin, overflow: "hidden" }}
    >
      {children}
    </AbsoluteFill>
  );
};
