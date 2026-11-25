// How each character from characters/*.svg moves. Points are in the SVG's 300x400 viewBox.
// Every SVG has the same part ids: head, arm-front, eyes-open/-closed, mouth-closed/-open/-wide
// (hat and wings where the character has them), so one component animates them all.

import bzynka from "../../../characters/bzynka.svg";
import koliuchka from "../../../characters/koliuchka.svg";
import medunko from "../../../characters/medunko.svg";
import pylyp from "../../../characters/pylyp.svg";
import siryi from "../../../characters/siryi.svg";

export type Rig = {
  svg: string; // bundled url of the SVG
  neck: [number, number]; // head (and hat) turns around this point
  shoulder: [number, number]; // arm-front swings around this point while talking
  flies?: boolean; // hovers and flaps its wings instead of standing
};

export const RIG: Record<string, Rig> = {
  pylyp: { svg: pylyp, neck: [150, 172], shoulder: [196, 196] },
  medunko: { svg: medunko, neck: [150, 196], shoulder: [226, 236] },
  bzynka: { svg: bzynka, neck: [170, 226], shoulder: [160, 238], flies: true },
  siryi: { svg: siryi, neck: [150, 172], shoulder: [182, 186] },
  koliuchka: { svg: koliuchka, neck: [196, 330], shoulder: [190, 340] },
};

export const VIEWBOX = { width: 300, height: 400 };
