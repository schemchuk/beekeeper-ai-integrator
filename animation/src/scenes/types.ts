import type { TimelineLine } from "../reel/types";

export type SceneProps = {
  frame: number; // absolute frame of the reel (snow and loops keep going across cuts)
  line: TimelineLine;
  from: number; // first frame of this line's span
  to: number; // first frame after it
};

export type Scene = {
  Back: React.FC<SceneProps>; // behind the characters
  Front?: React.FC<SceneProps>; // in front of them (tables, the straw bed edge)
};
