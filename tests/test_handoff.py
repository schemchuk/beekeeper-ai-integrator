import json
import subprocess
from datetime import datetime, timedelta

import pytest

from beekeeper.episode import load_episode
from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.handoff import (
    GitHub,
    HandoffError,
    hand_off,
    manifest,
    problems,
    stage,
    tag,
)
from beekeeper.post import threads_text, write_threads
from blocks import COVER_POST

NOW = datetime(2026, 11, 27, 10, 0, tzinfo=BERLIN)
SLOT = datetime(2026, 12, 1, 8, 0, tzinfo=BERLIN)
EPISODE = "003-test-reel"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def make_ep(tmp_path, post="Ein kurzer Post.\n", threads=None):
    ep_dir = tmp_path / "out" / EPISODE
    ep_dir.mkdir(parents=True)
    (ep_dir / "reel_de.mp4").write_bytes(b"mp4")
    (ep_dir / "cover_de.png").write_bytes(PNG)
    (ep_dir / "post_de.txt").write_text(post, encoding="utf-8")
    if threads is not None:
        (ep_dir / "post_threads.txt").write_text(threads, encoding="utf-8")
    return ep_dir


class FakeGh:
    """Records gh calls; `releases` maps tag -> asset names; `fail` fails the first n calls."""

    def __init__(self, releases=None, fail=0):
        self.releases = releases or {}
        self.fail = fail
        self.calls = []

    def __call__(self, args, env):
        self.calls.append((list(args), env))
        if self.fail:
            self.fail -= 1
            return subprocess.CompletedProcess(args, 1, "", "HTTP 502")
        cmd = args[:2]
        if cmd == ["release", "view"]:
            names = self.releases.get(args[2])
            if names is None:
                return subprocess.CompletedProcess(args, 1, "", "release not found")
            return subprocess.CompletedProcess(
                args, 0, json.dumps({"assets": [{"name": n} for n in names]}), ""
            )
        if cmd == ["release", "create"]:
            self.releases[args[2]] = [a.rsplit("/", 1)[-1] for a in args[3:] if "/" in a]
        return subprocess.CompletedProcess(args, 0, "", "")

    def commands(self):
        return [" ".join(a[:2]) for a, _ in self.calls]


def run(ep_dir, tmp_path, fake, **kw):
    kw.setdefault("duration", lambda p: 45.0)
    kw.setdefault("sleep", lambda s: None)
    return hand_off(ep_dir, SLOT, NOW, GitHub(run=fake), staging=tmp_path / "stage", **kw)


def test_manifest_has_exactly_the_v2_keys():
    m = manifest(EPISODE, SLOT)
    assert m == {
        "v": 2,
        "kind": "reel",
        "id": EPISODE,
        "release_at": "2026-12-01T08:00:00+01:00",
        "ai": True,
    }
    assert tag(EPISODE) == "reel/003-test-reel"


def test_stage_renames_to_contract_names(tmp_path):
    files = stage(make_ep(tmp_path), SLOT, tmp_path / "stage")
    assert sorted(files) == ["cover.png", "manifest.json", "post_de.txt", "video.mp4"]
    data = json.loads(files["manifest.json"].read_text())
    assert data["v"] == 2 and data["id"] == EPISODE


def test_first_handoff_creates_the_release(tmp_path):
    fake = FakeGh()
    assert run(make_ep(tmp_path), tmp_path, fake) == "created"
    args, _ = fake.calls[-1]
    assert args[:3] == ["release", "create", "reel/003-test-reel"]
    names = sorted(a.rsplit("/", 1)[-1] for a in args if "/" in a and a.startswith("/"))
    assert names == ["cover.png", "manifest.json", "post_de.txt", "video.mp4"]
    assert not any("factory-intake" in " ".join(a) for a, _ in fake.calls)


def test_second_handoff_replaces_assets_on_the_same_release(tmp_path):
    names = ["manifest.json", "video.mp4", "cover.png", "post_de.txt", "post_threads.txt"]
    fake = FakeGh({"reel/003-test-reel": names})
    assert run(make_ep(tmp_path), tmp_path, fake) == "updated"
    assert "release create" not in fake.commands()
    upload = next(a for a, _ in fake.calls if a[:2] == ["release", "upload"])
    assert "--clobber" in upload
    delete = next(a for a, _ in fake.calls if a[:2] == ["release", "delete-asset"])
    assert delete[3] == "post_threads.txt"


def test_scan_dispatch_only_with_token(tmp_path):
    fake = FakeGh()
    run(make_ep(tmp_path), tmp_path, fake)
    assert "workflow run" not in fake.commands()
    fake = FakeGh()
    run(make_ep(tmp_path / "b"), tmp_path / "b", fake, token="t0k")
    args, env = fake.calls[-1]
    assert args == [
        "workflow", "run", "project-intake.yml", "--repo", "schemchuk/postpilot",
        "-f", "project=beekeeper",
    ]  # fmt: skip
    assert env == {"GH_TOKEN": "t0k"}


def test_github_failure_is_retried_then_alerts(tmp_path):
    fake = FakeGh(fail=1)
    assert run(make_ep(tmp_path), tmp_path, fake) == "created"
    fake = FakeGh(fail=99)
    with pytest.raises(HandoffError, match="GitHub did not take"):
        run(make_ep(tmp_path / "b"), tmp_path / "b", fake)
    assert fake.commands().count("release view") == 3


@pytest.mark.parametrize(
    ("post", "threads", "seconds", "release_at", "want"),
    [
        ("x" * 2158, None, 45.0, SLOT, "post_de.txt: 2158 characters, at most 2157"),
        ("  \n", None, 45.0, SLOT, "post_de.txt: empty"),
        ("ok", "y" * 501, 45.0, SLOT, "post_threads.txt: 501 characters"),
        ("ok", None, 95.0, SLOT, "video.mp4: 95.0 s"),
        ("ok", None, 45.0, NOW + timedelta(days=61), "want from 1 hour ago to 60 days ahead"),
        ("ok", None, 45.0, NOW - timedelta(hours=2), "want from 1 hour ago to 60 days ahead"),
        ("ok", None, 45.0, datetime(2026, 12, 1, 8), "no UTC offset"),
    ],
)
def test_limits_are_checked_before_the_release(tmp_path, post, threads, seconds, release_at, want):
    files = stage(make_ep(tmp_path, post, threads), SLOT, tmp_path / "stage")
    found = problems(EPISODE, files, release_at, NOW, lambda p: seconds)
    assert any(want in f for f in found), found


def test_a_bad_reel_never_reaches_github(tmp_path):
    fake = FakeGh()
    with pytest.raises(HandoffError):
        run(make_ep(tmp_path, "x" * 3000), tmp_path, fake)
    assert fake.calls == []


def test_bad_id_and_cover_are_refused(tmp_path):
    files = stage(make_ep(tmp_path), SLOT, tmp_path / "stage")
    files["cover.png"].write_bytes(b"GIF89a")
    found = problems("003_Bad", files, SLOT, NOW, lambda p: 45.0)
    assert any("id '003_Bad'" in f for f in found)
    assert "cover.png: not a PNG" in found


def _episode(tmp_path, grain):
    text = (
        'id: "900"\nslug: test\ntitle: {ua: "Тест", de: "Test"}\n'
        + COVER_POST.replace("Autoantwort: 20 Zeilen Python.", grain)
        + 'lines:\n  - who: pylyp\n    ua: "Привіт"\n    de: "Hallo"\n'
    )
    (tmp_path / "episode.yaml").write_text(text, encoding="utf-8")
    return load_episode(tmp_path, {"pylyp"})


def test_threads_text_only_when_the_post_is_long(tmp_path):
    short = _episode(tmp_path, "Kurz.")
    assert threads_text(short) is None
    assert write_threads(short, tmp_path / "out") is None
    long = _episode(tmp_path, "Lang. " * 100)
    text = threads_text(long)
    assert len(text) <= 500
    assert text.startswith("Wie viele Mails") and "#Automatisierung" in text
    assert write_threads(long, tmp_path / "out").read_text(encoding="utf-8") == text
