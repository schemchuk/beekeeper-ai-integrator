# Series bible

Project memory for the series. Look here before writing an episode.

| File | What is in it |
| --- | --- |
| `characters.md` | Who is who: names UA/DE, character, looks, seasonal state |
| `apiary-calendar.md` | The beekeeper's year: what happens in each season, IT parallels |
| `ideas.md` | Episode seeds with status and source |
| `stories/` | Volodymyr's stories verbatim, one file per telling, dated |
| `lore/` | Sourced folklore, spells, proverbs, laws, history (UA + DE), YAML, see `lore/README.md` |
| `../voice/volodymyr.md` | How he talks and jokes |
| `../voice/inbox/` | Unsorted drops, processed at session start |
| `../docs/voices.md` | TTS research and voice choices |

How a story is processed: save it verbatim to `stories/YYYY-MM-DD-topic.md`, pull facts
into the calendar and characters, add episode seeds to `ideas.md`, add new phrases to
`voice/volodymyr.md`. Search across all of it with `grep -ri <word> bible voice`.
