"""Command line entry point: `beekeeper`."""

import argparse
import os
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
    post = sub.add_parser("post", help="feed text from the post block: post_<lang>.txt")
    _episode_args(post)
    build = sub.add_parser("build", help="voices -> timing -> render -> post -> check")
    _episode_args(build)
    build.add_argument("--force", action="store_true", help="render even if nothing changed")
    handoff = sub.add_parser(
        "handoff", help="give the DE reel to postpilot: release reel/<episode> (contract v2)"
    )
    handoff.add_argument("episode", type=Path)
    handoff.add_argument("--cast", type=Path, default=DEFAULT_CAST)
    handoff.add_argument("--out", type=Path, default=DEFAULT_OUT)
    handoff.add_argument(
        "--release-at",
        required=True,
        help="ISO 8601 with offset, e.g. 2026-12-01T08:00:00+01:00 (Berlin), or now",
    )
    sub.add_parser("factory", help="run the factory bot (systemd user service, docs/factory.md)")
    clean = sub.add_parser("temp-clean", help="empty ~/Desktop/temp (weekly timer, F7.2)")
    clean.add_argument("--dir", type=Path, default=None, help="folder to empty")
    clean.add_argument("--dry-run", action="store_true", help="only list what would go")
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
    from beekeeper.render import RenderError, render, render_cover

    ep_dir = _episode_dir(episode, cast, out)
    if ep_dir is None:
        return 1
    for lang in langs or ["de", "ua"]:
        for step in (render, render_cover):
            try:
                path, rendered = step(ep_dir, lang, force=force)
            except RenderError as e:
                print(e, file=sys.stderr)
                return 1
            print(f"ok: {lang} {'rendered' if rendered else 'unchanged'} -> {path}")
    return 0


def cmd_post(episode: Path, cast: Path, langs: list[str] | None, out: Path) -> int:
    from beekeeper.post import write_post, write_threads

    try:
        ep = load_episode(episode, load_cast(cast))
    except EpisodeError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 1
    for lang in langs or ["de", "ua"]:
        path = write_post(ep, out / f"{ep.id}-{ep.slug}", lang)
        print(f"ok: {lang} post -> {path}")
        if lang == "de":
            threads = write_threads(ep, out / f"{ep.id}-{ep.slug}")
            if threads:
                print(f"ok: de threads post -> {threads}")
    return 0


def cmd_handoff(episode: Path, cast: Path, out: Path, release_at: str) -> int:
    from datetime import datetime

    from beekeeper.factory.calendar import BERLIN
    from beekeeper.factory.handoff import HandoffError, hand_off, tag
    from beekeeper.factory.telegram import load_env

    ep_dir = _episode_dir(episode, cast, out)
    if ep_dir is None:
        return 1
    try:
        now = datetime.now(BERLIN).replace(microsecond=0)
        when = now if release_at == "now" else datetime.fromisoformat(release_at)
    except ValueError:
        print(f"--release-at {release_at!r}: not an ISO 8601 datetime", file=sys.stderr)
        return 1
    import logging

    log_file = Path("work/handoff") / f"{ep_dir.name}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )
    print(f"log: {log_file}")
    token = os.environ.get("POSTPILOT_DISPATCH_TOKEN") or load_env().get("POSTPILOT_DISPATCH_TOKEN")
    try:
        outcome = hand_off(ep_dir, when, now, token=token)
    except HandoffError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 1
    print(f"ok: {tag(ep_dir.name)} {outcome}, release_at {when.isoformat()}")
    return 0


def cmd_check(episode: Path, cast: Path, langs: list[str] | None, out: Path) -> int:
    from beekeeper.check import check_cover, check_reel, summary
    from beekeeper.render import cover_path, reel_path

    ep_dir = _episode_dir(episode, cast, out)
    if ep_dir is None:
        return 1
    status = 0
    for lang in langs or ["de", "ua"]:
        reel = reel_path(ep_dir, lang)
        found, info = check_reel(reel)
        found += check_cover(cover_path(ep_dir, lang))
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
        lambda: cmd_post(episode, cast, langs, out),
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


def cmd_temp_clean(folder: Path | None, dry_run: bool) -> int:
    from beekeeper.tempclean import TEMP, clean

    folder = folder or TEMP
    gone = clean(folder, dry_run=dry_run)
    verb = "would delete" if dry_run else "deleted"
    for path in gone:
        print(f"{verb}: {path}")
    print(f"{folder}: {verb} {len(gone)} item(s)")
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
    if args.command == "post":
        return cmd_post(args.episode, args.cast, args.lang, args.out)
    if args.command == "build":
        return cmd_build(args.episode, args.cast, args.lang, args.out, args.force)
    if args.command == "handoff":
        return cmd_handoff(args.episode, args.cast, args.out, args.release_at)
    if args.command == "factory":
        from beekeeper.factory.service import main as factory_main

        return factory_main()
    if args.command == "temp-clean":
        return cmd_temp_clean(args.dir, args.dry_run)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
