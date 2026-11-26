import { AbsoluteFill } from "remotion";
import { Character, Pose, hasRig } from "../characters/Character";
import { fontFamily } from "./fonts";
import { SAFE_X } from "./theme";
import type { Cover as CoverData, Timeline } from "./types";

// The cover (BRIEF cover rule, 2026-11-26): bright, so it stands out in a dark feed; a
// glowing monitor in the middle, because IT people look at a screen first; the characters
// below it; the title on top. Frame 0 of the reel and the `Cover` still are this picture.

const W = 1080;
const SCREEN = { x: 110, y: 520, w: 860, h: 560 };
const BEZEL = 30;
const REST: Pose = { mouth: 0, eyesClosed: false, head: 0, arm: 0, wings: 1 };
const CHAR_HEIGHT = 760;
const CHAR_BOTTOM = 1900;

const Honeycomb: React.FC = () => (
  <svg width={W} height={1920} style={{ position: "absolute", opacity: 0.16 }}>
    <defs>
      <pattern
        id="cover-comb"
        width="84"
        height="146"
        patternUnits="userSpaceOnUse"
      >
        <path
          d="M42 0 L84 24 L84 73 L42 97 L0 73 L0 24 Z M42 97 L42 146"
          fill="none"
          stroke="#8a5a00"
          strokeWidth="4"
        />
      </pattern>
    </defs>
    <rect width={W} height={1920} fill="url(#cover-comb)" />
  </svg>
);

const Monitor: React.FC<{ text: string }> = ({ text }) => (
  <>
    <div
      style={{
        position: "absolute",
        left: SCREEN.x - BEZEL,
        top: SCREEN.y - BEZEL,
        width: SCREEN.w + 2 * BEZEL,
        height: SCREEN.h + 2 * BEZEL,
        borderRadius: 36,
        backgroundColor: "#23262f",
        boxShadow:
          "0 0 140px 30px rgba(54, 227, 208, 0.75), 0 30px 60px rgba(0,0,0,0.35)",
      }}
    />
    <div
      style={{
        position: "absolute",
        left: SCREEN.x,
        top: SCREEN.y,
        width: SCREEN.w,
        height: SCREEN.h,
        borderRadius: 10,
        background: "linear-gradient(180deg, #0f3346, #17587a)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 56px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 72,
          fontWeight: 700,
          lineHeight: 1.3,
          color: "#d9fff8",
          textAlign: "center",
          whiteSpace: "pre-wrap",
          textShadow: "0 0 24px rgba(54, 227, 208, 0.9)",
        }}
      >
        {text}
        <span style={{ color: "#36e3d0" }}>▌</span>
      </div>
    </div>
    {/* stand */}
    <div
      style={{
        position: "absolute",
        left: W / 2 - 50,
        top: SCREEN.y + SCREEN.h + BEZEL,
        width: 100,
        height: 90,
        backgroundColor: "#23262f",
      }}
    />
    <div
      style={{
        position: "absolute",
        left: W / 2 - 190,
        top: SCREEN.y + SCREEN.h + BEZEL + 86,
        width: 380,
        height: 26,
        borderRadius: 13,
        backgroundColor: "#23262f",
      }}
    />
  </>
);

export const Cover: React.FC<{ cover: CoverData }> = ({ cover }) => {
  const who = cover.who.filter(hasRig);
  const width = (CHAR_HEIGHT * 3) / 4;
  const step = who.length > 1 ? (W - 2 * SAFE_X - width) / (who.length - 1) : 0;
  return (
    <AbsoluteFill
      style={{
        fontFamily,
        background: "linear-gradient(180deg, #fff1c2, #f5b72e)",
      }}
    >
      <Honeycomb />
      <div
        style={{
          position: "absolute",
          top: 150,
          left: SAFE_X,
          right: SAFE_X,
          textAlign: "center",
          fontSize: 92,
          fontWeight: 800,
          lineHeight: 1.1,
          color: "#2b1d05",
        }}
      >
        {cover.title}
      </div>
      <Monitor text={cover.monitor} />
      {who.map((name, i) => (
        <Character
          key={name}
          name={name}
          instance={`cover-${name}`}
          height={CHAR_HEIGHT}
          pose={REST}
          style={{
            left: who.length > 1 ? SAFE_X + i * step : (W - width) / 2,
            top: CHAR_BOTTOM - CHAR_HEIGHT,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

// The `Cover` still: same picture, rendered to cover_<lang>.png for the post thumbnail.
export const CoverStill: React.FC<Timeline> = (timeline) =>
  timeline.cover ? (
    <Cover cover={timeline.cover} />
  ) : (
    <AbsoluteFill style={{ backgroundColor: "#f5b72e" }} />
  );
