// What each line looks like on screen, decided from the timeline alone (ADR 004: an episode
// is data). Used by the camera, the stage and the scenes, so they always agree.

import type { Timeline, TimelineLine } from "./types";

export type Span = { line: TimelineLine; from: number; to: number };

// The scene stays up until the next line starts, so the breath between lines is not black.
export const spans = (t: Timeline): Span[] =>
  t.lines.map((line, i) => ({
    line,
    from: line.start,
    to: Math.max(
      line.start + 1,
      t.lines[i + 1]?.start ?? t.end_card?.start ?? t.duration,
    ),
  }));

export const spanAt = (all: Span[], frame: number) =>
  all.find((s) => frame >= s.from && frame < s.to);

// `shot.camera` is free text in episode.yaml; these words pick the framing:
// - "phone ..."           the phone fills the screen, nobody on stage
// - "monitor"             the laptop screen fills the frame, the speaker appears in it
// - "over-the-shoulder"   the laptop screen with code being typed, voice off screen
// - "close-up"            zoom on the scene's resident; "push-in" zooms in slowly
// - anything else         the whole scene
export type Framing = "phone" | "monitor" | "code" | "scene";

export const framing = (line: TimelineLine): Framing => {
  const camera = (line.shot.camera ?? "").toLowerCase();
  if (camera.includes("phone")) return "phone";
  if (camera.includes("monitor")) return "monitor";
  if (camera.includes("over-the-shoulder")) return "code";
  return "scene";
};

export type Zoom = { from: number; to: number };

export const zoom = (line: TimelineLine): Zoom => {
  const camera = (line.shot.camera ?? "").toLowerCase();
  if (camera.includes("push-in")) return { from: 1, to: 1.16 };
  if (camera.includes("close-up")) return { from: 1.28, to: 1.28 };
  return { from: 1, to: 1 };
};

// A scene's resident is the first character who speaks in it (hut: Pylyp, den: Medunko).
export const residents = (
  t: Timeline,
  known: (name: string | null) => name is string,
) => {
  const map: Record<string, string> = {};
  for (const line of t.lines) {
    const scene = line.shot.scene;
    if (scene && known(line.who) && !(scene in map)) map[scene] = line.who;
  }
  return map;
};
