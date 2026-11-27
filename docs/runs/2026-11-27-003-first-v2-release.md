# Run: episode 003, the first release by postpilot contract v2 (2026-11-27)

Volodymyr: "робимо зараз реліз, включаємо всі логи". No waiting for the Tuesday slot:
`release_at` = now.

| Time (Berlin) | Step | Result |
|---|---|---|
| 10:08 | `beekeeper build` 003 | DE 59.7 s, 8.4 MB; UA 49.3 s, 6.8 MB; check passed |
| 10:17 | `beekeeper handoff episodes/003-vechir-z-sirym --release-at now` | release [`reel/003-vechir-z-sirym`](https://github.com/schemchuk/beekeeper-ai-integrator/releases/tag/reel/003-vechir-z-sirym): manifest v2, video, cover, post_de, post_threads; log `work/handoff/003-vechir-z-sirym.log` |
| 10:17 | `gh workflow run project-intake.yml -f project=beekeeper` (gh login, no PAT) | run 45972482801: done in 16.9 s, no rejection |
| 10:18 | `gh workflow run publish-reels.yml` | run 45972627862, 186 s |

Channels (postpilot item `a81ef4a3`):

| Channel | Outcome | Id |
|---|---|---|
| Facebook Reels | published | 1007680545744393 |
| Instagram Reels | published | 18122258422790385 |
| YouTube Shorts | published; custom thumbnail rejected, HTTP 403 | [qD0Wu-QN9Bw](https://youtube.com/shorts/qD0Wu-QN9Bw) |
| TikTok | pending (draft in the TikTok inbox, finished by hand) | |
| LinkedIn DE | published | [urn:li:ugcPost:7532010812069249025](https://www.linkedin.com/feed/update/urn:li:ugcPost:7532010812069249025) |
| Threads | published (`post_threads.txt`) | 18123091736518367 |

Notes:
- The intake scan needs no PAT: the `gh` login may dispatch postpilot's workflows.
- YouTube thumbnail 403: usually a channel that is not verified for custom thumbnails. The
  Short shows its first frame, which is our cover anyway (T21). For postpilot / him.
- v1 (`factory-intake`) is now done for this project (ADR 011 §10); postpilot may start
  T27e2 (remove v1), which needs Volodymyr's OK on that PR.

## First numbers (LinkedIn DE post, same day, about 2 h after publishing)

Screenshot of the post analytics (activity `7532010812899643393`), 12:21 on 2026-11-27:

- 54 impressions, 47 members reached; 11% inside his network, 89% outside.
- 23 video views, 2 min 46 s in total, 7 s average on a 59.7 s reel: about 12% watched.
- 0 profile views and 0 new followers from this post so far.

Compared with 002 (14 h, see `2026-11-25-002-first-reel.md`):

| | 002 (14 h) | 003 (~2 h) |
|---|---|---|
| Impressions | 34 | 54 |
| Members reached | 8 | 47 |
| Outside network | 24% | 89% |
| Video views | 7 | 23 |
| Average watch | 37 s of 55 s | 7 s of 59.7 s |

Reading: the cover rule (T21) works, reach is up and mostly outside his network. The
problem moved to the first seconds: most viewers scroll on after about 7 s. Next lever is
the hook: a gag or a question in the first 2-3 s, a shorter cold open. Check again at 24 h
before changing anything.
