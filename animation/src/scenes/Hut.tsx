import { Snow } from "./Snow";
import type { SceneProps } from "./types";

// Pylyp's hut at night: snow outside the window, honey on the shelf, laptop glowing and the
// phone on the table. Back = behind the characters, Front = the table in front of Pylyp.

const W = 1080;
const H = 1920;
const TABLE_TOP = 1390;

export const HutBack: React.FC<SceneProps> = ({ frame }) => (
  <svg
    viewBox={`0 0 ${W} ${H}`}
    width={W}
    height={H}
    style={{ position: "absolute" }}
  >
    <defs>
      <linearGradient id="hut-wall" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#141c3c" />
        <stop offset="1" stopColor="#25315f" />
      </linearGradient>
      <linearGradient id="hut-sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#060b1f" />
        <stop offset="1" stopColor="#1a2a5a" />
      </linearGradient>
      <radialGradient id="hut-glow" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#36e3d0" stopOpacity="0.32" />
        <stop offset="1" stopColor="#36e3d0" stopOpacity="0" />
      </radialGradient>
      <clipPath id="hut-window">
        <rect x="110" y="250" width="340" height="420" rx="8" />
      </clipPath>
    </defs>
    <rect width={W} height={H} fill="url(#hut-wall)" />
    {/* log wall */}
    {Array.from({ length: 12 }, (_, i) => (
      <path
        key={i}
        d={`M0 ${140 + i * 115} H${W}`}
        stroke="#0d1430"
        strokeWidth="5"
        opacity="0.55"
      />
    ))}
    {/* window with night sky, moon and snow */}
    <g clipPath="url(#hut-window)">
      <rect x="110" y="250" width="340" height="420" fill="url(#hut-sky)" />
      <circle cx="370" cy="330" r="42" fill="#f3ecc8" />
      <circle cx="355" cy="320" r="42" fill="#0b1430" opacity="0.15" />
      <path
        d="M110 630 Q190 590 280 618 Q360 640 450 600 V670 H110 Z"
        fill="#e8eefc"
      />
      <Snow
        frame={frame}
        box={{ x: 110, y: 230, w: 340, h: 460 }}
        count={40}
        seed="hut"
        size={4}
      />
    </g>
    <rect
      x="110"
      y="250"
      width="340"
      height="420"
      rx="8"
      fill="none"
      stroke="#5a3d22"
      strokeWidth="22"
    />
    <path d="M280 250 V670 M110 460 H450" stroke="#5a3d22" strokeWidth="12" />
    <path
      d="M86 690 H474"
      stroke="#6e4a2a"
      strokeWidth="22"
      strokeLinecap="round"
    />
    {/* shelf with honey jars */}
    <path
      d="M640 600 H1010"
      stroke="#6e4a2a"
      strokeWidth="18"
      strokeLinecap="round"
    />
    {[690, 790, 890].map((x, i) => (
      <g key={x}>
        <rect
          x={x - 34}
          y={500 + i * 6}
          width="68"
          height={92 - i * 6}
          rx="12"
          fill="#e0a12a"
        />
        <rect
          x={x - 36}
          y={492 + i * 6}
          width="72"
          height="18"
          rx="4"
          fill="#c8202e"
        />
        <rect
          x={x - 20}
          y={530 + i * 6}
          width="40"
          height="30"
          rx="4"
          fill="#f5e6b8"
          opacity="0.85"
        />
      </g>
    ))}
    {/* laptop glow on the wall */}
    <ellipse cx="840" cy="1240" rx="360" ry="300" fill="url(#hut-glow)" />
  </svg>
);

export const HutFront: React.FC<SceneProps> = () => (
  <svg
    viewBox={`0 0 ${W} ${H}`}
    width={W}
    height={H}
    style={{ position: "absolute" }}
  >
    {/* laptop, screen towards Pylyp: we see its back with the lid logo and the screen glow */}
    <path d="M700 1170 L1000 1150 L1010 1386 L690 1386 Z" fill="#2a2d36" />
    <path
      d="M700 1170 L1000 1150"
      stroke="#36e3d0"
      strokeWidth="5"
      opacity="0.8"
    />
    <circle cx="850" cy="1270" r="22" fill="#ffc44d" opacity="0.85" />
    <path d="M660 1384 H1040 L1020 1398 H680 Z" fill="#3c404b" />
    {/* phone lying on the table */}
    <rect x="470" y="1372" width="120" height="20" rx="8" fill="#15161c" />
    <rect
      x="482"
      y="1375"
      width="96"
      height="6"
      rx="3"
      fill="#2f6dd8"
      opacity="0.6"
    />
    {/* table */}
    <rect x="0" y={TABLE_TOP} width={W} height="34" fill="#8a5a33" />
    <rect
      x="0"
      y={TABLE_TOP + 34}
      width={W}
      height={H - TABLE_TOP - 34}
      fill="#5c3b20"
    />
    {Array.from({ length: 6 }, (_, i) => (
      <path
        key={i}
        d={`M0 ${TABLE_TOP + 110 + i * 85} H${W}`}
        stroke="#4a2f19"
        strokeWidth="4"
      />
    ))}
  </svg>
);
