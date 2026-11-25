import json
import subprocess

import pytest

from beekeeper import render as render_mod
from beekeeper.render import RenderError, command, fingerprint, render


@pytest.fixture
def setup(tmp_path):
    animation = tmp_path / "animation"
    (animation / "src").mkdir(parents=True)
    (animation / "node_modules").mkdir()
    (animation / "src" / "Reel.tsx").write_text("export {}")
    (animation / "package-lock.json").write_text("{}")
    ep_dir = tmp_path / "out" / "900-test"
    (ep_dir / "voices").mkdir(parents=True)
    (ep_dir / "voices" / "a.wav").write_bytes(b"one")
    (ep_dir / "sfx").mkdir()
    (ep_dir / "sfx" / "buzz.wav").write_bytes(b"bzz")
    timeline = {
        "lang": "de",
        "speech": [{"audio": "voices/a.wav"}],
        "sfx": [{"audio": "sfx/buzz.wav"}],
    }
    (ep_dir / "timeline-de.json").write_text(json.dumps(timeline))
    return animation, ep_dir


@pytest.fixture
def fake_remotion(monkeypatch):
    calls = []

    def run(cmd, cwd):
        calls.append((cmd, cwd))
        reel = cmd[5]
        open(reel, "wb").write(b"mp4")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(render_mod.subprocess, "run", run)
    return calls


def test_fingerprint_follows_inputs(setup):
    animation, ep_dir = setup
    tl = ep_dir / "timeline-de.json"
    base = fingerprint(tl, ep_dir, animation)
    assert fingerprint(tl, ep_dir, animation) == base
    (ep_dir / "voices" / "a.wav").write_bytes(b"two")
    after_audio = fingerprint(tl, ep_dir, animation)
    assert after_audio != base
    (animation / "src" / "Reel.tsx").write_text("export const x = 1")
    assert fingerprint(tl, ep_dir, animation) != after_audio


def test_command(setup):
    _, ep_dir = setup
    reel = ep_dir / "reel_de.mp4"
    cmd = command(ep_dir / "timeline-de.json", ep_dir, reel)
    assert cmd[:6] == ["npx", "--no-install", "remotion", "render", "Reel", str(reel.resolve())]
    assert f"--props={(ep_dir / 'timeline-de.json').resolve()}" in cmd
    assert f"--public-dir={ep_dir.resolve()}" in cmd
    assert "--pixel-format=yuv420p" in cmd


def test_render_then_skip_then_rerender(setup, fake_remotion):
    animation, ep_dir = setup
    reel, rendered = render(ep_dir, "de", animation=animation)
    assert rendered and reel.read_bytes() == b"mp4"
    assert fake_remotion[0][1] == animation
    assert render(ep_dir, "de", animation=animation) == (reel, False)
    assert render(ep_dir, "de", animation=animation, force=True) == (reel, True)
    (ep_dir / "sfx" / "buzz.wav").write_bytes(b"BZZ")
    assert render(ep_dir, "de", animation=animation) == (reel, True)
    assert len(fake_remotion) == 3


def test_missing_timeline(setup):
    animation, ep_dir = setup
    with pytest.raises(RenderError, match="run `beekeeper timing` first"):
        render(ep_dir, "ua", animation=animation)


def test_failed_render_leaves_no_stamp(setup, monkeypatch):
    animation, ep_dir = setup
    monkeypatch.setattr(
        render_mod.subprocess, "run", lambda cmd, cwd: subprocess.CompletedProcess(cmd, 1)
    )
    with pytest.raises(RenderError, match="exit 1"):
        render(ep_dir, "de", animation=animation)
    assert not (ep_dir / "reel_de.mp4.hash").exists()
