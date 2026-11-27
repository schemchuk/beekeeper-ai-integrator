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
