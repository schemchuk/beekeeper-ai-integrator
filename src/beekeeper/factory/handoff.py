"""Handoff to postpilot by its release contract v2 (ADR 011, roadmap T33).

The factory gives postpilot a public release `reel/<episode>` on this repo with
`manifest.json`, `video.mp4`, `cover.png`, `post_de.txt` and, when needed,
`post_threads.txt`. postpilot polls the release; an optional `project-intake` dispatch asks
for an earlier scan. `factory-intake` (v1) is never dispatched.

Every limit postpilot checks at intake is checked here first, so a reel never fails there.
A second handoff of the same episode replaces the assets on the same release (a fix);
postpilot refuses that once a channel has published.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("beekeeper.factory.handoff")

REPO = "schemchuk/beekeeper-ai-integrator"
POSTPILOT = "schemchuk/postpilot"
PROJECT = "beekeeper"  # key in postpilot's config/projects.toml
INTAKE_WORKFLOW = "project-intake.yml"
STAGING = Path("work/handoff")

ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
AI_LABEL = "\n\nKI-generiertes Video / AI-generated video"  # added by postpilot, 43 chars
CAPTION_CHARS = 2200
THREADS_CHARS = 500  # the label counts here too
LIMITS = {  # asset -> max bytes (contract, inclusive)
    "manifest.json": 16_000,
    "post_de.txt": 12_000,
    "post_threads.txt": 2_000,
    "video.mp4": 100_000_000,
    "cover.png": 10_000_000,
}
MIN_SECONDS, MAX_SECONDS = 3.0, 90.0
PAST, AHEAD = timedelta(hours=1), timedelta(days=60)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# pipeline file -> release asset name
SOURCES = {
    "reel_de.mp4": "video.mp4",
    "cover_de.png": "cover.png",
    "post_de.txt": "post_de.txt",
    "post_threads.txt": "post_threads.txt",
}
REQUIRED = ("video.mp4", "cover.png", "post_de.txt")


class HandoffError(Exception):
    """The handoff cannot go ahead; `problems` says why in plain words."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class GhError(Exception):
    pass


def tag(episode: str) -> str:
    return f"reel/{episode}"


def manifest(episode: str, release_at: datetime) -> dict:
    """Exactly the v2 keys. `channels` is left out: the project entry's reel channels apply."""
    return {
        "v": 2,
        "kind": "reel",
        "id": episode,
        "release_at": release_at.isoformat(timespec="seconds"),
        "ai": True,
    }


def _text_problems(name: str, data: bytes, max_chars: int) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{name}: not UTF-8"]
    found = []
    if not text.strip():
        found.append(f"{name}: empty")
    if "\0" in text:
        found.append(f"{name}: has a NUL character")
    if len(text) > max_chars:
        found.append(f"{name}: {len(text)} characters, at most {max_chars}")
    return found


def problems(
    episode: str,
    files: dict[str, Path],
    release_at: datetime,
    now: datetime,
    duration: Callable[[Path], float],
) -> list[str]:
    """Every way the staged release would fail postpilot's intake; empty when it passes."""
    found: list[str] = []
    if not (len(episode) <= 80 and ID_RE.fullmatch(episode)):
        found.append(f"id {episode!r}: want 1-80 lowercase letters and digits in groups split by -")
    if release_at.tzinfo is None:
        found.append("release_at has no UTC offset")
    elif not now - PAST <= release_at <= now + AHEAD:
        found.append(f"release_at {release_at.isoformat()}: want from 1 hour ago to 60 days ahead")
    for name in REQUIRED:
        if name not in files:
            found.append(f"{name}: missing")
    for name, path in files.items():
        size = path.stat().st_size
        if size > LIMITS[name]:
            found.append(f"{name}: {size} bytes, at most {LIMITS[name]}")
    if "post_de.txt" in files:
        budget = CAPTION_CHARS - len(AI_LABEL)
        found += _text_problems("post_de.txt", files["post_de.txt"].read_bytes(), budget)
    if "post_threads.txt" in files:
        data = files["post_threads.txt"].read_bytes()
        found += _text_problems("post_threads.txt", data, THREADS_CHARS - len(AI_LABEL))
    if "cover.png" in files:
        with files["cover.png"].open("rb") as f:
            if f.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                found.append("cover.png: not a PNG")
    if "video.mp4" in files:
        try:
            seconds = duration(files["video.mp4"])
        except (ValueError, OSError) as e:
            found.append(f"video.mp4: {e}")
        else:
            if not MIN_SECONDS <= seconds <= MAX_SECONDS:
                found.append(f"video.mp4: {seconds:.1f} s, want {MIN_SECONDS:g}-{MAX_SECONDS:g} s")
    return found


def stage(ep_dir: Path, release_at: datetime, dest: Path) -> dict[str, Path]:
    """Copy the pipeline's files under the contract's names and write `manifest.json`."""
    episode = ep_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    files: dict[str, Path] = {}
    for source, name in SOURCES.items():
        if (ep_dir / source).is_file():
            files[name] = Path(shutil.copy2(ep_dir / source, dest / name))
    path = dest / "manifest.json"
    path.write_text(json.dumps(manifest(episode, release_at), ensure_ascii=False) + "\n")
    files["manifest.json"] = path
    return files


def probe_duration(path: Path) -> float:
    from beekeeper.check import probe

    info = probe(path)
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        raise ValueError("no video stream")
    return float(info.get("format", {}).get("duration", 0))


Run = Callable[[Sequence[str], dict | None], subprocess.CompletedProcess]


def run_gh(args: Sequence[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, **env} if env else None,
    )


@dataclass
class GitHub:
    """The few `gh` calls the handoff needs; `run` is swapped for a fake in tests."""

    run: Run = run_gh
    repo: str = REPO

    def _call(self, args: Sequence[str], env: dict | None = None) -> subprocess.CompletedProcess:
        log.debug("gh %s", " ".join(args))
        done = self.run(args, env)
        log.debug("gh exit %s; stdout: %s; stderr: %s", done.returncode,
                  (done.stdout or "").strip(), (done.stderr or "").strip())  # fmt: skip
        return done

    def _ok(self, args: Sequence[str], env: dict | None = None) -> str:
        done = self._call(args, env)
        if done.returncode != 0:
            raise GhError((done.stderr or done.stdout).strip() or f"gh {args[0]} failed")
        return done.stdout

    def assets(self, release: str) -> list[str] | None:
        """Asset names of the release, or None if there is no such release."""
        done = self._call(["release", "view", release, "--repo", self.repo, "--json", "assets"])
        if done.returncode != 0:
            if "not found" in (done.stderr or "").lower():
                return None
            raise GhError((done.stderr or done.stdout).strip() or "gh release view failed")
        return [a["name"] for a in json.loads(done.stdout).get("assets", [])]

    def create(self, release: str, title: str, files: Sequence[Path]) -> None:
        self._ok(
            ["release", "create", release, *map(str, files), "--repo", self.repo,
             "--title", title, "--notes", "Postpilot reel (release contract v2)"]
        )  # fmt: skip

    def upload(self, release: str, files: Sequence[Path]) -> None:
        self._ok(["release", "upload", release, *map(str, files), "--repo", self.repo, "--clobber"])

    def delete_asset(self, release: str, name: str) -> None:
        self._ok(["release", "delete-asset", release, name, "--repo", self.repo, "--yes"])

    def delete_release(self, release: str) -> bool:
        """Withdraw a release and its tag ("стоп", F4.3); False if there was none."""
        done = self._call(
            ["release", "delete", release, "--repo", self.repo, "--yes", "--cleanup-tag"]
        )
        if done.returncode != 0:
            if "not found" in (done.stderr or "").lower():
                return False
            raise GhError((done.stderr or done.stdout).strip() or "gh release delete failed")
        return True

    def scan(self, token: str) -> None:
        """Ask postpilot for an earlier scan of this project (optional, ADR 011 §5)."""
        self._ok(
            ["workflow", "run", INTAKE_WORKFLOW, "--repo", POSTPILOT, "-f", f"project={PROJECT}"],
            {"GH_TOKEN": token},
        )


def hand_off(
    ep_dir: Path,
    release_at: datetime,
    now: datetime,
    gh: GitHub | None = None,
    *,
    staging: Path = STAGING,
    duration: Callable[[Path], float] = probe_duration,
    token: str | None = None,
    retries: int = 3,
    pause: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Create or fix the release of one episode; returns "created" or "updated".

    Raises HandoffError with plain reasons when the reel would fail intake or GitHub keeps
    failing after `retries` tries.
    """
    gh = gh or GitHub()
    episode = ep_dir.name
    files = stage(ep_dir, release_at, staging / episode)
    for name, path in sorted(files.items()):
        data = path.read_bytes()
        log.info("asset %s: %d bytes, sha256 %s", name, len(data), hashlib.sha256(data).hexdigest())
    log.info("manifest: %s", files["manifest.json"].read_text().strip())
    found = problems(episode, files, release_at, now, duration)
    for problem in found:
        log.error("intake would reject: %s", problem)
    if found:
        raise HandoffError(found)
    release = tag(episode)
    paths = list(files.values())
    last: GhError | None = None
    for attempt in range(1, retries + 1):
        try:
            existing = gh.assets(release)
            if existing is None:
                gh.create(release, f"Reel {episode}", paths)
                outcome = "created"
            else:
                gh.upload(release, paths)
                for name in set(existing) - set(files) - {"manifest.json"}:
                    if name in SOURCES.values():  # e.g. a post_threads.txt no longer needed
                        gh.delete_asset(release, name)
                outcome = "updated"
            break
        except GhError as e:
            last = e
            log.warning("handoff %s, try %d of %d: %s", release, attempt, retries, e)
            if attempt < retries:
                sleep(pause)
    else:
        raise HandoffError([f"GitHub did not take the release {release}: {last}"])
    if token:
        try:
            gh.scan(token)
        except GhError as e:  # polling picks the release up anyway
            log.warning("postpilot scan dispatch failed: %s", e)
    log.info("handoff %s %s, release_at %s", release, outcome, release_at.isoformat())
    return outcome
