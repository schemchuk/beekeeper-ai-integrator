import { Snow } from "./Snow";
import type { SceneProps } from "./types";

// Medunko's den under the snow: dark cave, snowy night through the mouth, a straw bed.
// While `shot.eyes` is closed, "Z" letters float up: he is asleep, even when he talks.

const W = 1080;
const H = 1920;

export const DenBack: React.FC<SceneProps> = ({ frame }) => (
  <svg
    viewBox={`0 0 ${W} ${H}`}
    width={W}
    height={H}
    style={{ position: "absolute" }}
  >
    <defs>
      <radialGradient id="den-rock" cx="0.5" cy="0.55" r="0.75">
        <stop offset="0" stopColor="#3a2d52" />
        <stop offset="1" stopColor="#120c1f" />
      </radialGradient>
      <linearGradient id="den-night" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#070c22" />
        <stop offset="1" stopColor="#22336a" />
      </linearGradient>
      <clipPath id="den-mouth">
        <path d="M600 860 Q610 430 820 400 Q1020 410 1040 860 Z" />
      </clipPath>
    </defs>
    <rect width={W} height={H} fill="url(#den-rock)" />
    {/* cave mouth: night, stars, snow */}
    <g clipPath="url(#den-mouth)">
      <rect x="590" y="390" width="460" height="480" fill="url(#den-night)" />
      {[
        [700, 470],
        [930, 500],
        [860, 450],
        [760, 560],
      ].map(([x, y]) => (
        <circle key={`${x}`} cx={x} cy={y} r="3" fill="#fff" opacity="0.8" />
      ))}
      <Snow
        frame={frame}
        box={{ x: 590, y: 380, w: 460, h: 500 }}
        count={36}
        seed="den"
        size={4}
      />
      <path
        d="M590 860 Q700 770 830 800 Q950 820 1050 770 V870 H590 Z"
        fill="#e8eefc"
      />
    </g>
    <path
      d="M600 860 Q610 430 820 400 Q1020 410 1040 860"
      fill="none"
      stroke="#e8eefc"
      strokeWidth="18"
    />
    {/* icicles */}
    {[690, 750, 820, 890, 960].map((x, i) => (
      <path
        key={x}
        d={`M${x - 12} ${425 - (i % 2) * 8} L${x} ${480 + (i % 3) * 18} L${x + 12} ${425 - (i % 2) * 8} Z`}
        fill="#cfe6ff"
        opacity="0.9"
      />
    ))}
    {/* rock bumps */}
    <path d="M0 0 H1080 V200 Q820 260 600 180 Q300 90 0 220 Z" fill="#0d0817" />
    <path
      d="M0 900 Q120 760 60 560 Q0 400 0 300 Z"
      fill="#0d0817"
      opacity="0.8"
    />
    {/* straw bed */}
    <ellipse cx="520" cy="1700" rx="470" ry="120" fill="#8c6a22" />
    <ellipse cx="520" cy="1680" rx="430" ry="90" fill="#b48a2e" />
  </svg>
);

export const DenFront: React.FC<SceneProps> = ({ frame, line }) => (
  <svg
    viewBox={`0 0 ${W} ${H}`}
    width={W}
    height={H}
    style={{ position: "absolute" }}
  >
    {/* straw sticking out in front of his feet */}
    {Array.from({ length: 22 }, (_, i) => {
      const x = 110 + i * 38;
      const tilt = ((i * 37) % 50) - 25;
      return (
        <path
          key={i}
          d={`M${x} 1790 L${x + tilt} ${1700 + ((i * 53) % 40)}`}
          stroke="#d9b54a"
          strokeWidth="6"
          strokeLinecap="round"
        />
      );
    })}
    {line.shot.eyes === "closed" ? <Zzz frame={frame} /> : null}
  </svg>
);

const Zzz: React.FC<{ frame: number }> = ({ frame }) => (
  <g>
    {[0, 1, 2].map((k) => {
      const t = ((frame + k * 25) % 75) / 75;
      return (
        <text
          key={k}
          x={760 + 60 * t + 10 * Math.sin(t * 6)}
          y={760 - 220 * t}
          fontSize={48 + 30 * t}
          fontWeight={800}
          fill="#cfe6ff"
          opacity={t < 0.15 ? t / 0.15 : 1 - (t - 0.15) / 0.85}
        >
          Z
        </text>
      );
    })}
  </g>
);
