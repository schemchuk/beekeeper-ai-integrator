# Lore base

Raw material for episodes: folk beliefs, spells, proverbs, tall tales, laws, history and
old literature about bees and beekeepers, UA and DE. Volodymyr's own stories stay in
`../stories/` (they are the best material). This folder is what the internet adds around them.

The base is machine-readable on purpose: the idea generator (roadmap step 3) will pick
entries by season, language and character and turn them into script options.

## Files

| File | Contents |
| --- | --- |
| `ua-folk.yaml` | Ukrainian beekeepers' spells, rituals, beliefs, weather signs, proverbs, calendar days |
| `de-folk.yaml` | German bee blessings, Sprichwörter, customs, Eulenspiegel, the BGB swarm law, Zeidler |
| `history.yaml` | Verified curiosities: Prokopovych, mad honey wars, skeps, telling the bees, frame hive race |
| `literature.yaml` | Old public-domain fables and stories (Hlibov, Skovoroda, Grimm, Busch, Storm) |

## Entry format

```yaml
- id: ua-spell-pike-head          # unique, prefix = file
  kind: spell                     # spell | ritual | belief | sign | proverb | tale | law | fact | fable | custom
  lang: ua                        # language of the original text
  text: "…"                       # verbatim only when public domain (folk, pre-1900, statute); else omit
  gist: "…"                       # one-line English summary, always present
  season: spring                  # winter | spring | summer | autumn | any; may also hold a date
  source:
    title: "…"
    url: "…"
    cite: "…"                     # original collection if the page quotes one
  rights: public-domain           # public-domain | paraphrase-only | check
  it_parallel: "…"                # the automation / IT angle, if obvious
  gag_seed: "…"                   # one-line hook for an episode, not a script
  characters: [pylyp, bzynka]     # who it suits
  status: raw                     # raw → seeded (moved to ideas.md) → used (episode id)
```

## Rules

- Never invent folklore. Every entry has a source; doubtful items get `rights: check` and a note.
- Verbatim text only for folk texts, pre-1900 authors, and statutes (German laws are not
  copyrighted, § 5 UrhG). Modern articles, Wikipedia and authors who died less than 70 years
  ago: paraphrase in `gist`, link the source. Ostap Vyshnia (d. 1956) becomes public domain
  on 2027-01-01; until then only references.
- Pylyp's dignity rule applies to gag seeds too (`../stories/2026-11-25-positioning.md`):
  the begging is done by Medunko, never by Pylyp.
- Old-calendar dates: Ukrainian churches moved to the New Julian calendar in 2023, so a
  feast "17 March (old 30 March)" is written with both dates.
