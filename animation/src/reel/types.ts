// Shape of out/NNN-slug/timeline-<lang>.json (format 1), written by `beekeeper timing`.
// All times are frames at `fps`; audio paths are relative to the episode out folder,
// which is passed to Remotion as the public dir.

export type Speech = {
  text: string;
  audio: string;
  start: number;
  end: number;
  mouth?: string; // one digit per frame: 0 closed, 1 open, 2 wide (from the wav loudness)
};

export type OnscreenItem = {
  text: string;
  start: number;
  end: number;
};

export type SfxEvent = {
  name: string;
  start: number;
  audio?: string; // e.g. "sfx/phone-buzz.wav", synthesized by `beekeeper timing`
};

export type TimelineLine = {
  index: number;
  who: string | null;
  start: number;
  end: number;
  shot: Record<string, string>;
  action: string | null;
  speech: Speech | null;
  onscreen: OnscreenItem[];
  sfx: SfxEvent[];
};

export type Timeline = {
  format: number;
  episode: string;
  slug: string;
  lang: "de" | "ua";
  fps: number;
  duration: number;
  title: string;
  scenes: Record<string, string>;
  lines: TimelineLine[];
  end_card: { text: string; start: number; end: number } | null;
};
