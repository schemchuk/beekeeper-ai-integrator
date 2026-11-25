# Characters

Draft, agreed with Volodymyr on 2026-11-24. Looks are not final.

Premise (Volodymyr's words, keep them): "я жив так далеко і уособлено, що вовк мені почту
носив, а ведмідь казав «Добрий день»". Pylyp lived so far out in the forest that the wolf
delivered his mail and the bear said "Good day". Now he is an IT admin in Germany, and the forest friends drop by.

| Character | UA | DE | Role (draft) |
| --- | --- | --- | --- |
| Pylyp | Пилип | Philipp | Beekeeper, 57, retrained as sysadmin/automation engineer in Germany. Volodymyr's alter ego. Back in Ukraine a well-known beekeeper: honey and bee products, honey drinks, fairs (selling his wife's handmade too), queen rearing and selection, instrumental insemination of queens. Never begs for work: a gentleman looking for the right match, who may agree to automate a client's routine and leave them the blooming field (2026-11-25). |
| Bee | Бзинька | Bsinka | His sidekick and toughest code reviewer. Original look, nothing like other famous cartoon bees. |
| Bear | Медунко | (open) | Polite neighbour, always begs Pylyp for honey; says "Добрий день". Introduced from the start. Winter: asleep in his den, sucking his paw. |
| Wolf | Сірий | (open) | Old, cunning wolf ("старий та хитрий вовчара"). The forest postman, now brings rejection letters. Visits Pylyp on quiet evenings. |
| Hedgehog | Колючка | (open) | The apiary's sanitary officer, guards it from rodents too. Unsociable, but always comes out when Pylyp works at the apiary. Pylyp treats him to cut-out drone brood. Winter: asleep. |
| Host | Ведуча | Moderatorin | Interviewer from episode 001. |

The bee was first going to be "Майя"; renamed to Бзинька on 2026-11-24 to avoid any link
to the German "Die Biene Maja".

Сірий: Volodymyr named the old wolf from the cartoon "Жив-був пес" (1982) as his prototype.
We take only the temperament (old, sly, worldly, warm underneath). Our wolf gets his own
look, voice and lines; no quotes, songs or designs from that film.

Recurring villains: the letter "Wir haben Ihr Profil für zukünftige Stellen gespeichert",
the Jobcenter, "relevante Berufserfahrung in Deutschland", Kubernetes.

## Looks, sketch v1 (2026-11-24)

Files: `characters/*.svg`, model sheet via `python3 tools/model_sheet.py` → `out/model_sheet.png`.
Every SVG has groups `eyes-open/eyes-closed`, `mouth-closed/-open/-wide`, `brows`, `head`,
`arm-front/-back`, `legs` so Remotion can animate them.

- Pylyp (v2, from Volodymyr's photo): round face, bald on top, short grey hair on the sides,
  clean-shaven, light brows, calm stern look; grey sweater with a dark knitted front panel
  over a light collared shirt; straw hat with a red-black band, translucent cyan veil, pink
  cyber monocle.
- Бзинька: round honey bee with a pink visor, cyan LED antennae, headset mic (the reviewer).
- Медунко: big brown bear, winter nightcap with pompom, cyan scarf, paw raised for "Добрий день".
- Сірий: lean old wolf, postman cap with an envelope badge, mailbag with a letter, notched ear,
  grey bushy brow, sly half-closed eye.
- Колючка: hedgehog with honey-tipped spines, cyan honeycomb-cross badge (not a red cross),
  holds a piece of drone brood comb.
