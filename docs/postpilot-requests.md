# Requests to postpilot

postpilot (`~/VS_Code_projects/postpilot`) distributes the reels and is the Telegram
control channel. It has its own process (interview, spec, tasks), so requests are listed
here and handed over to a postpilot session; nothing is coded there from this repo.
A copy lives in postpilot's Claude memory (`project-beekeeper-requests`).

| Date | Request | Status |
|------|---------|--------|
| 2026-11-25 | Focus on German: German audience first, Ukrainian only as a 2029 fallback. | open |
| 2026-11-25 | Keep the cross-network reach (LinkedIn, Threads, Instagram, Facebook Reels). | as is |
| 2026-11-25 | Telegram bot as the factory's control channel: ideas and tall tales in, scripts and monthly plan for review/edit/approval, chat with Volodymyr. | open |
| 2026-11-25 | He edits Ukrainian; edits must flow to the German production text (postpilot follow-up 4: Edit on own_video preview only edits DE). | open |
| 2026-11-25 | Silent approval in Telegram: monthly plan (20th sent, 24th warning, 25th morning accepted) and scripts (3 days before release, accepted the morning before, no warning). See `docs/product.md`. | open |
| 2026-11-25 | Statistics for the cartoons roughly like postpilot's. | open |
| 2026-11-25 | Manual intake stays: AI-generated (`/work ai`) and original content added by hand, as in the live run 2026-11-24. | as is |
| 2026-11-25 | The factory hands its reels to postpilot automatically; postpilot then distributes them by its own rules. Proposed mechanism: `docs/adr/005-handoff-to-postpilot.md` (Telegram `file_id` + `workflow_dispatch` of a new `factory-intake` workflow); postpilot decides in its own ADR. | open |
