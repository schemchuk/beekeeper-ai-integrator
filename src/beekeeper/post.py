"""Post step (roadmap T11): the feed text for one language, from the `post` block.

Order follows the reach rules (2026-11-26): the hook first (all LinkedIn shows before
"mehr"), then the grain (something useful), the question that invites comments, the offer,
and the hashtags last.
"""

from pathlib import Path

from beekeeper.episode import Episode


def post_text(episode: Episode, lang: str) -> str:
    if episode.post is None:
        raise ValueError(f"episode {episode.id} has no post block")
    parts = episode.post.parts
    blocks = [parts[k][lang].strip() for k in ("hook", "grain", "question", "offer")]
    blocks.append(" ".join(f"#{tag}" for tag in episode.post.hashtags))
    return "\n\n".join(blocks) + "\n"


def post_path(ep_dir: Path, lang: str) -> Path:
    return ep_dir / f"post_{lang}.txt"


def write_post(episode: Episode, ep_dir: Path, lang: str) -> Path:
    ep_dir.mkdir(parents=True, exist_ok=True)
    path = post_path(ep_dir, lang)
    path.write_text(post_text(episode, lang), encoding="utf-8")
    return path
