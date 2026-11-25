// Where characters stand on the 1080x1920 canvas: x = centre, bottom = feet, height in px.
// Faces stay above the subtitle box; the subtitles may cover legs. Scenes (T07) may move these.

export type Slot = { x: number; bottom: number; height: number };

export const STAGE: Record<string, Record<string, Slot>> = {
  hut: {
    pylyp: { x: 430, bottom: 1640, height: 1080 },
    bzynka: { x: 820, bottom: 960, height: 520 },
  },
  den: {
    medunko: { x: 540, bottom: 1660, height: 1100 },
  },
};

export const DEFAULT_SLOT: Slot = { x: 540, bottom: 1640, height: 1080 };
export const GUEST_SLOT: Slot = { x: 820, bottom: 1000, height: 560 };
