// Inter from @fontsource, bundled with the project: renders work offline.
import { loadFont } from "@remotion/fonts";
import cyr400 from "@fontsource/inter/files/inter-cyrillic-400-normal.woff2";
import cyr700 from "@fontsource/inter/files/inter-cyrillic-700-normal.woff2";
import cyr800 from "@fontsource/inter/files/inter-cyrillic-800-normal.woff2";
import lat400 from "@fontsource/inter/files/inter-latin-400-normal.woff2";
import lat700 from "@fontsource/inter/files/inter-latin-700-normal.woff2";
import lat800 from "@fontsource/inter/files/inter-latin-800-normal.woff2";

export const fontFamily = "Inter";

const CYRILLIC = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116";
const LATIN =
  "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD";

const faces: [string, string, string][] = [
  [cyr400, "400", CYRILLIC],
  [cyr700, "700", CYRILLIC],
  [cyr800, "800", CYRILLIC],
  [lat400, "400", LATIN],
  [lat700, "700", LATIN],
  [lat800, "800", LATIN],
];

for (const [url, weight, unicodeRange] of faces) {
  loadFont({ family: fontFamily, url, weight, unicodeRange });
}
