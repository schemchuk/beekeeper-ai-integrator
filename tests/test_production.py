import subprocess
from datetime import datetime

import pytest

from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.handoff import GitHub, HandoffError
from beekeeper.factory.production import (
    NOTHING_TO_STOP,
    ROUNDS,
    Production,
    is_stop,
    run_build,
)
from beekeeper.factory.queue import load_queue
from beekeeper.factory.review import Review
from beekeeper.factory.slots import State, load_slots
from test_script import MORNING, NIGHT, FakeGit, answer, make, make_root

EPISODE = "004-vovchyi-dub"
RELEASE = datetime(2026, 12, 1, 8, 0, tzinfo=BERLIN)
ACCEPTED_AT = datetime(2026, 11, 30, 7, 0, tzinfo=BERLIN)
LATER = datetime(2026, 11, 30, 7, 15, tzinfo=BERLIN)


@pytest.fixture
def accepted(tmp_path):
    """Slot 004 written, sent and accepted in silence."""
    root = make_root(tmp_path)
    scripts, *_ = make(root, answer())
    scripts.tick(NIGHT)
    scripts.tick(MORNING)
    Review(None, lambda text: [1], root, FakeGit()).tick(ACCEPTED_AT)
    return root


class FakeBuild:
    def __init__(self, *results):
        self.results = list(results) or [(True, "")]
        self.calls = []

    def __call__(self, episode, root):
        self.calls.append(episode.as_posix())
        ok, detail = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if ok:
            out = root / "out" / episode.name
            out.mkdir(parents=True, exist_ok=True)
            (out / "reel_de.mp4").write_bytes(b"mp4 de")
            (out / "reel_ua.mp4").write_bytes(b"mp4 ua")
        return ok, detail


class FakeHandoff:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, ep_dir, release_at, now):
        self.calls.append((ep_dir.name, release_at))
        if self.error:
            raise self.error
        return "created"


class FakeGh:
    def __init__(self, code=0, stderr=""):
        self.calls = []
        self.code, self.stderr = code, stderr

    def __call__(self, args, env):
        self.calls.append(list(args))
        return subprocess.CompletedProcess(args, self.code, "", self.stderr)


def production(root, build=None, handoff=None, gh=None):
    videos, alerts, git = [], [], FakeGit()

    def send_video(path, caption):
        videos.append((path.relative_to(root).as_posix(), caption))
        return 700 + len(videos)

    p = Production(
        send_video,
        alerts.append,
        root,
        git,
        build=build or FakeBuild(),
        handoff=handoff or FakeHandoff(),
        github=GitHub(run=gh or FakeGh()),
    )
    return p, videos, alerts, git


def slot_of(root):
    (slot,) = load_slots(root / "factory/slots.yaml").items
    return slot


def test_accepted_is_built_sent_and_handed_off(accepted):
    build, handoff = FakeBuild(), FakeHandoff()
    p, videos, alerts, git = production(accepted, build, handoff)
    p.tick(LATER)
    assert build.calls == [f"episodes/{EPISODE}"]
    assert videos == [
        (
            f"out/{EPISODE}/reel_de.mp4",
            "Ролик 004 «Вечір з Сірим» готовий, вийде вт 01.12 о 08:00. «Стоп» до виходу зупинить.",
        )
    ]
    assert handoff.calls == [(EPISODE, RELEASE)]
    slot = slot_of(accepted)
    assert slot.state == State.HANDED_OFF
    assert slot.messages["reel"] == 701
    assert slot.times["built"] == LATER
    assert [m for m, _ in git.synced] == [f"slot built: {EPISODE}", f"slot handed_off: {EPISODE}"]
    assert alerts == []
    p.tick(LATER)  # nothing twice
    assert len(build.calls) == 1 and len(videos) == 1 and len(handoff.calls) == 1


def test_released_after_the_release_time(accepted):
    p, *_ = production(accepted)
    p.tick(LATER)
    p.tick(datetime(2026, 12, 1, 7, 45, tzinfo=BERLIN))
    assert slot_of(accepted).state == State.HANDED_OFF
    p.tick(datetime(2026, 12, 1, 8, 0, tzinfo=BERLIN))
    assert slot_of(accepted).state == State.RELEASED


def test_nothing_before_acceptance(tmp_path):
    root = make_root(tmp_path)
    scripts, *_ = make(root, answer())
    scripts.tick(NIGHT)
    scripts.tick(MORNING)
    build = FakeBuild()
    p, videos, *_ = production(root, build)
    p.tick(LATER)
    assert build.calls == [] and videos == []
    assert slot_of(root).state == State.SENT


def test_a_failed_build_alerts_and_tries_again(accepted):
    build = FakeBuild((False, "render: ffmpeg died"), (True, ""))
    p, videos, alerts, git = production(accepted, build)
    p.tick(LATER)
    assert slot_of(accepted).state == State.ACCEPTED
    assert alerts == [
        f"Зібрати ролик {EPISODE} не вдалося: render: ffmpeg died. "
        "Спробую ще раз за чверть години (1 з 3)."
    ]
    assert videos == [] and git.synced == []
    p.tick(LATER)
    assert slot_of(accepted).state == State.HANDED_OFF


def test_build_gives_up_after_three_rounds(accepted):
    build = FakeBuild((False, "boom"))
    p, _, alerts, _ = production(accepted, build)
    for _ in range(ROUNDS + 2):
        p.tick(LATER)
    assert len(build.calls) == ROUNDS
    assert "так і не вдалося" in alerts[-1]


def test_a_build_without_the_reel_is_a_failure(accepted):
    p, videos, alerts, _ = production(accepted, build=lambda episode, root: (True, ""))
    p.tick(LATER)
    assert videos == []
    assert "нема out/004-vovchyi-dub/reel_de.mp4" in alerts[0]


def test_a_failed_handoff_keeps_built_and_alerts(accepted):
    handoff = FakeHandoff(HandoffError(["video.mp4: 70.0 s, want 3-60 s"]))
    p, videos, alerts, _ = production(accepted, handoff=handoff)
    p.tick(LATER)
    assert slot_of(accepted).state == State.BUILT
    assert len(videos) == 1
    assert alerts[0].startswith(f"Віддати postpilot {EPISODE} не вдалося: video.mp4: 70.0 s")
    handoff.error = None
    p.tick(LATER)
    assert slot_of(accepted).state == State.HANDED_OFF
    assert len(videos) == 1  # the reel is not sent again


# --- "стоп" -------------------------------------------------------------------------


def test_stop_words():
    for word in ("стоп", "Стоп!", "stop", "/stop", "зупини"):
        assert is_stop(word), word
    assert not is_stop("стоп, а що там з чергою?")


def test_stop_withdraws_the_release_and_returns_the_idea(accepted):
    gh = FakeGh()
    p, *_ = production(accepted, gh=gh)
    p.tick(LATER)
    reply = p.stop(LATER)
    assert reply == (f"Зупинив {EPISODE} на вт 01.12, реліз прибрав. Ідея знову перша в черзі.")
    assert gh.calls == [
        ["release", "delete", f"reel/{EPISODE}", "--repo", "schemchuk/beekeeper-ai-integrator",
         "--yes", "--cleanup-tag"]
    ]  # fmt: skip
    assert slot_of(accepted).state == State.STOPPED
    assert load_queue(accepted / "factory/queue.yaml").items[0].title == "Вовчий дуб"
    assert p.stop(LATER) == NOTHING_TO_STOP


def test_stop_before_the_build_needs_no_github(accepted):
    gh = FakeGh()
    p, *_ = production(accepted, gh=gh)
    assert p.stop(LATER) == f"Зупинив {EPISODE} на вт 01.12. Ідея знову перша в черзі."
    assert gh.calls == []
    build = FakeBuild()
    p.build = build
    p.tick(LATER)
    assert build.calls == []  # a stopped slot is never built


def test_a_failed_withdrawal_does_not_stop(accepted):
    p, *_ = production(accepted, gh=FakeGh(1, "HTTP 502"))
    p.tick(LATER)
    assert p.stop(LATER).startswith(f"Не зміг прибрати реліз reel/{EPISODE}: HTTP 502.")
    assert slot_of(accepted).state == State.HANDED_OFF


def test_a_gone_release_still_stops(accepted):
    p, *_ = production(accepted, gh=FakeGh(1, "release not found"))
    p.tick(LATER)
    assert p.stop(LATER) == f"Зупинив {EPISODE} на вт 01.12. Ідея знову перша в черзі."


def test_too_late_to_stop(accepted):
    p, *_ = production(accepted)
    p.tick(LATER)
    assert p.stop(datetime(2026, 12, 1, 8, 5, tzinfo=BERLIN)) == NOTHING_TO_STOP


def test_run_build_reports_the_last_line(tmp_path):
    ok, detail = run_build(tmp_path / "missing", tmp_path)
    assert not ok and detail
