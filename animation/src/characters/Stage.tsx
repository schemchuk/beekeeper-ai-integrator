import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Timeline, TimelineLine } from "../reel/types";
import { Character, Mouth, Pose, hasRig } from "./Character";
import { RIG } from "./rig";
import { DEFAULT_SLOT, GUEST_SLOT, STAGE, Slot } from "./stage-layout";

// Who stands where, line by line, decided from the timeline alone (ADR 004: an episode is data):
// - a scene's resident is the first character who speaks in it (hut: Pylyp, den: Medunko);
// - a guest (Bzynka in the hut) is on screen only for their own lines;
// - a phone close-up shows the phone, not the characters (T07 draws the phone);
// - `shot.eyes: closed` closes everyone's eyes (Medunko asleep), otherwise they blink.

const BLINK_EVERY = 100; // frames between blinks, ~3.3 s
const BLINK_LENGTH = 4;
const ENTRANCE = 18; // frames for the first entrance

type Span = { line: TimelineLine; from: number; to: number };

const spans = (t: Timeline): Span[] =>
  t.lines.map((line, i) => ({
    line,
    from: line.start,
    to: t.lines[i + 1]?.start ?? t.end_card?.start ?? t.duration,
  }));

const residents = (t: Timeline) => {
  const map: Record<string, string> = {};
  for (const line of t.lines) {
    const scene = line.shot.scene;
    if (scene && hasRig(line.who) && !(scene in map)) map[scene] = line.who;
  }
  return map;
};

const onStage = (
  line: TimelineLine,
  resident: Record<string, string>,
): string[] => {
  if ((line.shot.camera ?? "").includes("phone")) return [];
  const cast = new Set<string>();
  const home = line.shot.scene ? resident[line.shot.scene] : undefined;
  if (home) cast.add(home);
  if (hasRig(line.who)) cast.add(line.who);
  return [...cast];
};

const slotFor = (
  scene: string | undefined,
  name: string,
  isResident: boolean,
): Slot =>
  (scene && STAGE[scene]?.[name]) || (isResident ? DEFAULT_SLOT : GUEST_SLOT);

// Lip flaps at 15 fps (every second frame) look like a cartoon, not like a flicker.
const mouthAt = (line: TimelineLine, frame: number): Mouth => {
  const speech = line.speech;
  if (!speech?.mouth || frame < speech.start || frame >= speech.end) return 0;
  const k = frame - speech.start;
  return Number(speech.mouth[k - (k % 2)] ?? 0) as Mouth;
};

const seed = (name: string) =>
  [...name].reduce((a, c) => a + c.charCodeAt(0), 0);

export const Stage: React.FC<{ timeline: Timeline }> = ({ timeline }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const all = spans(timeline);
  const resident = residents(timeline);
  const current = all.find((s) => frame >= s.from && frame < s.to);
  const visible = current ? onStage(current.line, resident) : [];

  // Everyone in the episode stays mounted (each SVG loads once); off-stage ones are hidden.
  const names = [...new Set(timeline.lines.map((l) => l.who).filter(hasRig))];
  const firstSeen = Object.fromEntries(
    names.map((n) => [
      n,
      all.find((s) => onStage(s.line, resident).includes(n))?.from ?? 0,
    ]),
  );

  return (
    <AbsoluteFill>
      {names.map((name) => {
        const shown = current !== undefined && visible.includes(name);
        const line = current?.line;
        const scene = line?.shot.scene;
        const slot = slotFor(
          scene,
          name,
          scene !== undefined && resident[scene] === name,
        );
        const talking =
          shown &&
          line?.who === name &&
          line.speech !== null &&
          frame >= line.speech.start &&
          frame < line.speech.end;
        const mouth = talking && line ? mouthAt(line, frame) : 0;
        const s = seed(name);
        const t = frame / fps;

        const blink = (frame + s * 7) % BLINK_EVERY < BLINK_LENGTH;
        const pose: Pose = {
          mouth,
          eyesClosed: line?.shot.eyes === "closed" || blink,
          head: talking
            ? 2.5 * Math.sin(t * 5 + s) + mouth
            : 0.8 * Math.sin(t * 0.9 + s),
          arm: talking
            ? -6 - 6 * Math.sin(t * 3.2 + s)
            : 1.5 * Math.sin(t * 1.1 + s),
          wings: RIG[name].flies ? 0.55 + 0.45 * Math.abs(Math.sin(t * 28)) : 1,
        };

        const breathe = 1 + 0.012 * Math.sin(t * 2 * Math.PI * 0.35 + s);
        const hover = RIG[name].flies ? 18 * Math.sin(t * 2.4 + s) : 0;
        const bounce = talking ? -4 * mouth : 0;
        const enter = interpolate(
          frame - firstSeen[name],
          [0, ENTRANCE],
          [0, 1],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.back(1.4)),
          },
        );
        const width = (slot.height * 3) / 4;

        return (
          <Character
            key={name}
            name={name}
            instance={name}
            height={slot.height}
            pose={pose}
            style={{
              display: shown ? "block" : "none",
              left: slot.x - width / 2,
              top: slot.bottom - slot.height,
              transformOrigin: "50% 100%",
              transform: `translateY(${(1 - enter) * 420 + hover + bounce}px) scaleY(${breathe})`,
              opacity: Math.min(1, enter * 1.5),
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
