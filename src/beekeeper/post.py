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


THREADS_CHARS = 500  # postpilot's Threads limit (release contract v2)


def threads_text(episode: Episode) -> str | None:
    """A short German text for Threads when the full post is over 500 characters.

    Hook, question and hashtags; the hook and hashtags alone if that is still too long.
    None when the full post fits (postpilot then uses `post_de.txt` on Threads too).
    """
    full = post_text(episode, "de")
    if len(full) <= THREADS_CHARS:
        return None
    parts = episode.post.parts
    tags = " ".join(f"#{tag}" for tag in episode.post.hashtags)
    for keys in (("hook", "question"), ("hook",)):
        text = "\n\n".join([*(parts[k]["de"].strip() for k in keys), tags]) + "\n"
        if len(text) <= THREADS_CHARS:
            return text
    return parts["hook"]["de"].strip()[: THREADS_CHARS - 1] + "\n"


def threads_path(ep_dir: Path) -> Path:
    return ep_dir / "post_threads.txt"


def write_threads(episode: Episode, ep_dir: Path) -> Path | None:
    """Write `post_threads.txt` when needed, remove a stale one otherwise."""
    path = threads_path(ep_dir)
    text = threads_text(episode)
    if text is None:
        path.unlink(missing_ok=True)
        return None
    ep_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def post_path(ep_dir: Path, lang: str) -> Path:
    return ep_dir / f"post_{lang}.txt"


def write_post(episode: Episode, ep_dir: Path, lang: str) -> Path:
    ep_dir.mkdir(parents=True, exist_ok=True)
    path = post_path(ep_dir, lang)
    path.write_text(post_text(episode, lang), encoding="utf-8")
    return path
