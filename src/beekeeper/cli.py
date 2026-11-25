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
    timing = sub.add_parser("timing", help="lay out lines in frames: timeline-<lang>.json")
    timing.add_argument("episode", type=Path)
    timing.add_argument("--cast", type=Path, default=DEFAULT_CAST)
    timing.add_argument(
        "--lang",
        choices=["de", "ua"],
        action="append",
        help="only this language (repeatable); default both",
    )
    timing.add_argument("--out", type=Path, default=DEFAULT_OUT)
    render = sub.add_parser("render", help="Remotion: timeline-<lang>.json -> reel_<lang>.mp4")
    _episode_args(render)
    render.add_argument("--force", action="store_true", help="render even if nothing changed")
    check = sub.add_parser("check", help="check reel_<lang>.mp4 against the output contract")
    _episode_args(check)
    build = sub.add_parser("build", help="voices -> timing -> render -> check")
    _episode_args(build)
    build.add_argument("--force", action="store_true", help="render even if nothing changed")
    return parser


def _episode_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("episode", type=Path)
    p.add_argument("--cast", type=Path, default=DEFAULT_CAST)
    p.add_argument(
        "--lang",
        choices=["de", "ua"],
        action="append",
        help="only this language (repeatable); default both",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)


def _episode_dir(episode: Path, cast: Path, out: Path) -> Path | None:
    try:
        ep = load_episode(episode, load_cast(cast))
    except EpisodeError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return None
    return out / f"{ep.id}-{ep.slug}"


def cmd_render(
    episode: Path, cast: Path, langs: list[str] | None, out: Path, force: bool = False
) -> int:
    from beekeeper.render import RenderError, render

    ep_dir = _episode_dir(episode, cast, out)
    if ep_dir is None:
        return 1
    for lang in langs or ["de", "ua"]:
        try:
            reel, rendered = render(ep_dir, lang, force=force)
        except RenderError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"ok: {lang} {'rendered' if rendered else 'unchanged'} -> {reel}")
    return 0


def cmd_check(episode: Path, cast: Path, langs: list[str] | None, out: Path) -> int:
    from beekeeper.check import check_reel, summary
    from beekeeper.render import reel_path

    ep_dir = _episode_dir(episode, cast, out)
    if ep_dir is None:
        return 1
    status = 0
    for lang in langs or ["de", "ua"]:
        reel = reel_path(ep_dir, lang)
        found, info = check_reel(reel)
        if found:
            print("\n".join(found), file=sys.stderr)
            status = 1
        else:
            print(f"ok: {lang} {summary(info)} -> {reel}")
    return status


def cmd_build(
    episode: Path, cast: Path, langs: list[str] | None, out: Path, force: bool = False
) -> int:
    steps = (
        lambda: cmd_voices(episode, cast, langs, out),
        lambda: cmd_timing(episode, cast, langs, out),
        lambda: cmd_render(episode, cast, langs, out, force),
        lambda: cmd_check(episode, cast, langs, out),
    )
    for step in steps:
        status = step()
        if status != 0:
            return status
    return 0


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


def cmd_timing(episode: Path, cast: Path, langs: list[str] | None, out: Path) -> int:
    from beekeeper import timing
    from beekeeper.sfx import write_sfx
    from beekeeper.voices.cast import load_voices

    try:
        ep = load_episode(episode, load_cast(cast))
    except EpisodeError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 1
    ep_dir = out / f"{ep.id}-{ep.slug}"
    voices = load_voices(cast)
    target = timing.target_range(ep.extra.get("target_length"))
    try:
        sfx_audio = write_sfx(timing.sfx_names(ep), ep_dir)
    except KeyError as e:
        print(f"{episode}: {e.args[0]}", file=sys.stderr)
        return 1
    status = 0
    for lang in langs or ["de", "ua"]:
        try:
            clips = timing.load_clips(ep_dir / "voices", lang)
            timing.check_clips(ep, clips, lang, ep_dir / "voices", voices, Path.cwd())
        except timing.TimingError as e:
            print("\n".join(e.problems), file=sys.stderr)
            status = 1
            continue
        tl = timing.build_timeline(
            ep, clips, lang, voices_dir=ep_dir / "voices", sfx_audio=sfx_audio
        )
        path = timing.write_timeline(tl, ep_dir)
        seconds = tl["duration"] / tl["fps"]
        note = ""
        if target and not target[0] <= seconds <= target[1]:
            note = f"  (target {target[0]:g}-{target[1]:g} s)"
        print(f"ok: {lang} {seconds:.1f} s, {tl['duration']} frames -> {path}{note}")
    return status


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
    if args.command == "timing":
        return cmd_timing(args.episode, args.cast, args.lang, args.out)
    if args.command == "render":
        return cmd_render(args.episode, args.cast, args.lang, args.out, args.force)
    if args.command == "check":
        return cmd_check(args.episode, args.cast, args.lang, args.out)
    if args.command == "build":
        return cmd_build(args.episode, args.cast, args.lang, args.out, args.force)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
