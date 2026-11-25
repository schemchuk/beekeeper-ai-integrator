import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../reel/fonts";
import type { OnscreenItem, TimelineLine } from "../reel/types";

// Phone close-up: the phone fills the screen and shakes on every buzz. An on-screen text like
// "03:12  Medunko: Guten Tag" is a notification on the lock screen; any other text is an
// incoming chat message. Frames here are relative to the line (inside its Sequence).

const NOTIFICATION = /^(\d{1,2}:\d{2})\s+([^:]+):\s*(.+)$/;
const BUZZ = 14; // frames of shaking after each buzz

export const PhoneCloseUp: React.FC<{ line: TimelineLine }> = ({ line }) => {
  const frame = useCurrentFrame();
  const buzzes = line.sfx
    .filter((s) => s.name === "phone-buzz")
    .map((s) => s.start - line.start);
  const shake = buzzes.some((b) => frame >= b && frame < b + BUZZ);
  const dx = shake ? 12 * Math.sin(frame * 1.9) : 0;
  const rot = shake ? 1.2 * Math.sin(frame * 2.3) : 0;
  const first = line.onscreen[0]?.text.match(NOTIFICATION);

  return (
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center", fontFamily }}
    >
      <AbsoluteFill style={{ backgroundColor: "rgba(5, 8, 20, 0.55)" }} />
      {shake ? <BuzzLines /> : null}
      <div
        style={{
          width: 780,
          height: 1520,
          borderRadius: 96,
          backgroundColor: "#111318",
          padding: 22,
          transform: `translateX(${dx}px) rotate(${rot}deg)`,
          boxShadow: "0 40px 120px rgba(0,0,0,0.6)",
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: 76,
            overflow: "hidden",
            position: "relative",
            background: first
              ? "linear-gradient(180deg, #1b2a5c 0%, #3b2f6b 60%, #e0a12a 140%)"
              : "#ece4d4",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 20,
              left: "50%",
              width: 200,
              height: 44,
              marginLeft: -100,
              borderRadius: 22,
              backgroundColor: "#000",
            }}
          />
          {first ? (
            <LockScreen
              time={first[1]}
              sender={first[2]}
              text={first[3]}
              at={line.onscreen[0].start - line.start}
            />
          ) : (
            <Chat items={line.onscreen} lineStart={line.start} />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const usePop = (at: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return {
    scale: interpolate(frame - at, [0, 0.25 * fps], [0.6, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.back(1.8)),
    }),
    opacity: interpolate(frame - at, [0, 3], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  };
};

const LockScreen: React.FC<{
  time: string;
  sender: string;
  text: string;
  at: number;
}> = ({ time, sender, text, at }) => {
  const pop = usePop(at);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div
        style={{
          marginTop: 200,
          color: "#fff",
          fontSize: 190,
          fontWeight: 700,
          letterSpacing: -4,
        }}
      >
        {time}
      </div>
      <div
        style={{
          marginTop: 120,
          width: 640,
          padding: "30px 36px",
          borderRadius: 44,
          backgroundColor: "rgba(245, 241, 230, 0.94)",
          display: "flex",
          gap: 26,
          alignItems: "center",
          transform: `scale(${pop.scale})`,
          opacity: pop.opacity,
        }}
      >
        <div
          style={{
            width: 96,
            height: 96,
            flexShrink: 0,
            borderRadius: 26,
            backgroundColor: "#28c840",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 54,
          }}
        >
          💬
        </div>
        <div style={{ color: "#1b1b1f", minWidth: 0 }}>
          <div style={{ fontSize: 40, fontWeight: 800 }}>{sender}</div>
          <div style={{ fontSize: 44, fontWeight: 400, lineHeight: 1.25 }}>
            {text}
          </div>
        </div>
      </div>
    </div>
  );
};

const Chat: React.FC<{ items: OnscreenItem[]; lineStart: number }> = ({
  items,
  lineStart,
}) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      padding: "150px 40px 60px",
      display: "flex",
      flexDirection: "column",
      gap: 26,
      justifyContent: "center",
    }}
  >
    {items.map((item, k) => (
      <Bubble key={k} item={item} at={item.start - lineStart} />
    ))}
  </div>
);

const Bubble: React.FC<{ item: OnscreenItem; at: number }> = ({ item, at }) => {
  const frame = useCurrentFrame();
  const pop = usePop(at);
  if (frame < at) return null;
  return (
    <div
      style={{
        alignSelf: "flex-start",
        maxWidth: "88%",
        padding: "26px 36px",
        borderRadius: "40px 40px 40px 10px",
        backgroundColor: "#fff",
        color: "#1b1b1f",
        fontSize: 50,
        fontWeight: 600,
        lineHeight: 1.28,
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
        transform: `scale(${pop.scale})`,
        transformOrigin: "0% 100%",
        opacity: pop.opacity,
      }}
    >
      {item.text}
    </div>
  );
};

const BuzzLines: React.FC = () => (
  <svg
    viewBox="0 0 1080 1920"
    width={1080}
    height={1920}
    style={{ position: "absolute" }}
  >
    {[-1, 1].map((side) =>
      [0, 1].map((k) => {
        const x = 540 + side * (440 + k * 40);
        return (
          <path
            key={`${side}-${k}`}
            d={`M${x} 820 Q${x + side * 30} 960 ${x} 1100`}
            stroke="#ffc44d"
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            opacity={0.9 - k * 0.35}
          />
        );
      }),
    )}
  </svg>
);
