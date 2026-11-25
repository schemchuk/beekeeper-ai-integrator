// Where characters stand on the 1080x1920 canvas: x = centre, bottom = feet, height in px.
// Faces stay above the subtitle box; tables and subtitles may cover legs.

export type Slot = { x: number; bottom: number; height: number };

export const STAGE: Record<string, Record<string, Slot>> = {
  hut: {
    pylyp: { x: 400, bottom: 1660, height: 1020 }, // behind the table, laptop on his left
  },
  den: {
    medunko: { x: 500, bottom: 1700, height: 1040 }, // on the straw, cave mouth behind
  },
};

export const DEFAULT_SLOT: Slot = { x: 540, bottom: 1640, height: 1000 };
export const GUEST_SLOT: Slot = { x: 820, bottom: 1000, height: 560 };
// Inside the laptop screen (framing "monitor"), see scenes/Laptop.tsx.
export const MONITOR_SLOT: Slot = { x: 540, bottom: 1170, height: 640 };

// Head centre of a slot (the SVG heads sit ~29% from the top), for camera zooms.
export const faceOf = (s: Slot) => ({ x: s.x, y: s.bottom - 0.71 * s.height });
