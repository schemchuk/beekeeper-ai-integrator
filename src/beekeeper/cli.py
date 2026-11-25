"""Command line entry point: `beekeeper`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from beekeeper import __version__
from beekeeper.episode import EpisodeError, load_cast, load_episode

DEFAULT_CAST = Path("characters/cast.yaml")
DEFAULT_OUT = Path("out")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beekeeper",
        description="Episode factory: episode.yaml in, DE and UA reels out.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    validate = sub.add_parser("validate", help="check an episode.yaml (or its folder)")
    validate.add_argument("episode", type=Path)
    validate.add_argument("--cast", type=Path, default=DEFAULT_CAST)
    voices = sub.add_parser("voices", help="voice every spoken line (cached per line)")
    voices.add_argument("episode", type=Path)
    voices.add_argument("--cast", type=Path, default=DEFAULT_CAST)
    voices.add_argument(
        "--lang",
        choices=["de", "ua"],
        action="append",
        help="only this language (repeatable); default both",
    )
    voices.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser


def cmd_voices(episode: Path, cast: Path, langs: list[str] | None, out: Path) -> int:
    from beekeeper.voices import voice_episode
    from beekeeper.voices.cast import load_voices

    try:
        ep = load_episode(episode, load_cast(cast))
    except EpisodeError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 1
    out_dir = out / f"{ep.id}-{ep.slug}" / "voices"
    clips = voice_episode(
        ep, load_voices(cast), out_dir, root=Path.cwd(), langs=langs or ["de", "ua"]
    )
    new = sum(1 for c in clips if not c.cached)
    print(f"ok: {len(clips)} clips ({new} new, {len(clips) - new} cached) in {out_dir}")
    return 0


def cmd_validate(episode: Path, cast: Path) -> int:
    try:
        ep = load_episode(episode, load_cast(cast))
    except EpisodeError as e:
        for problem in e.problems:
            print(problem, file=sys.stderr)
        print(f"{len(e.problems)} problem(s)", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"{e.filename}: file not found", file=sys.stderr)
        return 1
    speech = sum(1 for line in ep.lines if line.who)
    print(f"ok: {ep.id} {ep.slug}, {len(ep.lines)} lines ({speech} spoken)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args.episode, args.cast)
    if args.command == "voices":
        return cmd_voices(args.episode, args.cast, args.lang, args.out)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
