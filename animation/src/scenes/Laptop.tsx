import { Easing, interpolate } from "remotion";
import { fontFamily } from "../reel/fonts";
import type { SceneProps } from "./types";

// The laptop screen filling the frame. "monitor": an empty video-call screen the speaker
// appears in (the stage draws Bzynka inside it). "code": over Pylyp's shoulder, code typed
// fast, then a green deploy tick.

const W = 1080;
const H = 1920;
const SCREEN = { x: 70, y: 420, w: 940, h: 820 };

const CODE = [
  "@bot.on_message",
  "def honey_request(msg):",
  "    queue.save(msg, season=2027)",
  "    return reply('thanks_for_interest')",
  "",
  "$ deploy --prod",
];

export const LaptopBack: React.FC<
  SceneProps & { mode: "monitor" | "code" }
> = ({ mode }) => (
  <svg
    viewBox={`0 0 ${W} ${H}`}
    width={W}
    height={H}
    style={{ position: "absolute" }}
  >
    <defs>
      <linearGradient id="lap-screen" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={mode === "code" ? "#0b1220" : "#0f2a3a"} />
        <stop offset="1" stopColor={mode === "code" ? "#111a2e" : "#13405a"} />
      </linearGradient>
    </defs>
    <rect width={W} height={H} fill="#0c0f1c" />
    <rect
      x={SCREEN.x - 34}
      y={SCREEN.y - 34}
      width={SCREEN.w + 68}
      height={SCREEN.h + 68}
      rx="40"
      fill="#23262f"
    />
    <rect
      x={SCREEN.x}
      y={SCREEN.y}
      width={SCREEN.w}
      height={SCREEN.h}
      rx="10"
      fill="url(#lap-screen)"
    />
    <circle cx={W / 2} cy={SCREEN.y - 17} r="6" fill="#3a3e4a" />
    {/* title bar */}
    <rect
      x={SCREEN.x}
      y={SCREEN.y}
      width={SCREEN.w}
      height="54"
      fill="#000"
      opacity="0.35"
    />
    {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
      <circle
        key={c}
        cx={SCREEN.x + 36 + i * 34}
        cy={SCREEN.y + 27}
        r="10"
        fill={c}
      />
    ))}
    {mode === "monitor" ? (
      <g opacity="0.25" stroke="#36e3d0" strokeWidth="2">
        {Array.from({ length: 9 }, (_, i) => (
          <path
            key={i}
            d={`M${SCREEN.x} ${SCREEN.y + 100 + i * 85} H${SCREEN.x + SCREEN.w}`}
          />
        ))}
      </g>
    ) : null}
    {/* keyboard deck below the screen */}
    <path
      d={`M20 ${SCREEN.y + SCREEN.h + 40} H1060 L1080 1920 H0 Z`}
      fill="#2d313c"
    />
  </svg>
);

export const LaptopFront: React.FC<
  SceneProps & { mode: "monitor" | "code" }
> = ({ mode, frame, from, to }) => {
  if (mode === "monitor") {
    return (
      <div
        style={{
          position: "absolute",
          left: SCREEN.x + 30,
          top: SCREEN.y + 74,
          fontFamily,
          fontSize: 34,
          fontWeight: 700,
          color: "#ff4f6d",
        }}
      >
        ● LIVE
      </div>
    );
  }
  const length = Math.max(1, to - from);
  const typed = interpolate(frame - from, [0, 0.6 * length], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const total = CODE.reduce((n, l) => n + l.length, 0);
  let budget = Math.floor(typed * total);
  const shown = CODE.map((l) => {
    const part = l.slice(0, Math.max(0, budget));
    budget -= l.length;
    return part;
  });
  const tick = interpolate(
    frame - from,
    [0.62 * length, 0.75 * length],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.back(2)),
    },
  );
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: SCREEN.x + 40,
          top: SCREEN.y + 90,
          fontFamily: "monospace",
          fontSize: 34,
          lineHeight: 1.5,
          color: "#c8f7ef",
          whiteSpace: "pre",
        }}
      >
        {shown.map((l, i) => (
          <div
            key={i}
            style={{ color: CODE[i].startsWith("$") ? "#ffc44d" : undefined }}
          >
            {l || " "}
          </div>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        style={{ position: "absolute" }}
      >
        <g transform={`translate(${W / 2} ${SCREEN.y + 610}) scale(${tick})`}>
          <circle r="120" fill="#28c840" />
          <path
            d="M-55 0 L-15 42 L60 -45"
            stroke="#fff"
            strokeWidth="26"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
        {/* Pylyp's shoulder and hat brim: the camera is behind him */}
        <ellipse cx="150" cy="1880" rx="360" ry="300" fill="#8f939c" />
        <ellipse cx="160" cy="1610" rx="250" ry="44" fill="#cfb878" />
        <path d="M30 1600 Q160 1440 290 1600 Z" fill="#e5d19a" />
      </svg>
    </>
  );
};
