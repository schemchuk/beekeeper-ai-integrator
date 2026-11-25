"""Command line entry point: `beekeeper`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from beekeeper import __version__
from beekeeper.episode import EpisodeError, load_cast, load_episode

DEFAULT_CAST = Path("characters/cast.yaml")


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
    return parser


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
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
