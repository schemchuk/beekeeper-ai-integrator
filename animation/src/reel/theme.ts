// Placeholder look until the scene library (T07): one gradient per scene, one colour
// per speaker for the subtitle name tag. DE names: bible/characters.md (open ones transliterated).

export const SCENE_BG: Record<string, [string, string]> = {
  hut: ["#0f1b3d", "#2a3b6e"], // night, laptop glow
  den: ["#1d1630", "#4a3f66"], // snowy den
};
export const DEFAULT_BG: [string, string] = ["#1b1b1f", "#3a3a44"];

export const SPEAKER: Record<string, { name: Record<"de" | "ua", string>; color: string }> = {
  pylyp: { name: { ua: "Пилип", de: "Philipp" }, color: "#f2b632" },
  bzynka: { name: { ua: "Бзинька", de: "Bsinka" }, color: "#ffd84d" },
  medunko: { name: { ua: "Медунко", de: "Medunko" }, color: "#c98a4b" },
  siryi: { name: { ua: "Сірий", de: "Siryi" }, color: "#9aa5b1" },
  koliuchka: { name: { ua: "Колючка", de: "Koliuchka" }, color: "#8fbf6a" },
};

export const SAFE_X = 80;
