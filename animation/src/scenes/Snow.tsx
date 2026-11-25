import { random } from "remotion";

// Falling snow inside a box, as SVG circles. `frame` is the reel's absolute frame, so the
// snow keeps falling across cuts between lines of the same scene.
export const Snow: React.FC<{
  frame: number;
  box: { x: number; y: number; w: number; h: number };
  count: number;
  seed: string;
  size?: number;
}> = ({ frame, box, count, seed, size = 5 }) => (
  <g>
    {Array.from({ length: count }, (_, i) => {
      const r = (k: string) => random(`${seed}-${i}-${k}`);
      const speed = 1.2 + 2 * r("v");
      const y = box.y + ((r("y") * box.h + frame * speed) % box.h);
      const x = box.x + r("x") * box.w + 14 * Math.sin(frame / 22 + r("p") * 6);
      return (
        <circle
          key={i}
          cx={x}
          cy={y}
          r={size * (0.5 + r("s"))}
          fill="#fff"
          opacity={0.5 + 0.5 * r("o")}
        />
      );
    })}
  </g>
);
