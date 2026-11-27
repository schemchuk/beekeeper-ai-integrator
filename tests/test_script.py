import shutil
from datetime import datetime
from pathlib import Path

import pytest

from beekeeper.factory.brain import BrainAuthError, BrainError
from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.queue import Queue, load_queue, save_queue
from beekeeper.factory.script import JOB, ROUNDS, Scripts, next_number
from beekeeper.factory.slots import Slots, State, load_slots

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = (REPO / "episodes/003-vechir-z-sirym/episode.yaml").read_text(encoding="utf-8")
RELEASE = datetime(2026, 12, 1, 8, 0, tzinfo=BERLIN)  # Tuesday
NIGHT = datetime(2026, 11, 28, 2, 0, tzinfo=BERLIN)  # T-3d 02:00
MORNING = datetime(2026, 11, 28, 7, 0, tzinfo=BERLIN)  # T-3d 07:00
BEFORE = datetime(2026, 11, 28, 1, 45, tzinfo=BERLIN)


def episode_yaml(number="004", slug="vovchyi-dub", release=RELEASE, **swap):
    text = TEMPLATE.replace('id: "003"', f'id: "{number}"')
    text = text.replace("slug: vechir-z-sirym", f"slug: {slug}")
    text = text.replace('release: "2026-12-01T08:00:00+01:00"', f'release: "{release.isoformat()}"')
    for old, new in swap.items():
        text = text.replace(old, new)
    return text


def answer(slug="vovchyi-dub", text=None):
    return {"slug": slug, "yaml": text or episode_yaml(slug=slug), "commit": "script: 004 test"}


class FakeBrain:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.tasks = []

    def ask(self, job, task):
        assert job == JOB
        self.tasks.append(task)
        result = self.answers.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeGit:
    def __init__(self):
        self.synced = []

    def sync(self, message, paths=None):
        self.synced.append((message, tuple(paths or ())))
        return True


@pytest.fixture
def root(tmp_path):
    (tmp_path / "characters").mkdir()
    shutil.copy(REPO / "characters/cast.yaml", tmp_path / "characters/cast.yaml")
    for old in ("001-nichnyi-kod", "002-medunko-v-splyachtsi", "003-vechir-z-sirym"):
        (tmp_path / "episodes" / old).mkdir(parents=True)
    queue, _ = Queue().add("Вовчий дуб", "bible/stories/2026-11-27-telegram-5.md", NIGHT)
    queue, _ = queue.add("Друга ідея", "chat", NIGHT)
    save_queue(queue, tmp_path / "factory/queue.yaml")
    return tmp_path


def make(root, *answers):
    brain, git = FakeBrain(*answers), FakeGit()
    sent, alerts = [], []

    def send(text):
        sent.append(text)
        return [500 + len(sent)]

    scripts = Scripts(brain, send, alerts.append, root, git, temp=root / "Desktop/temp")
    return scripts, brain, git, sent, alerts


def test_next_number(root):
    assert next_number(root, Slots()) == "004"


def test_nothing_before_the_night(root):
    scripts, brain, *_ = make(root)
    scripts.tick(BEFORE)
    assert brain.tasks == []
    assert load_slots(root / "factory/slots.yaml").items == ()


def test_night_writes_validates_and_binds(root):
    scripts, brain, git, sent, alerts = make(root, answer())
    scripts.tick(NIGHT)
    assert (root / "episodes/004-vovchyi-dub/episode.yaml").is_file()
    (slot,) = load_slots(root / "factory/slots.yaml").items
    assert slot.state == State.SCRIPTED
    assert slot.release == RELEASE
    assert slot.episode == "004-vovchyi-dub"
    assert slot.idea.title == "Вовчий дуб"
    assert [i.title for i in load_queue(root / "factory/queue.yaml").items] == ["Друга ідея"]
    assert git.synced == [("script: 004 test", ("bible", "factory", "episodes"))]
    assert "Episode number: 004" in brain.tasks[0]
    assert "Release: 2026-12-01T08:00:00+01:00 (Tuesday)" in brain.tasks[0]
    assert "Source: bible/stories/2026-11-27-telegram-5.md" in brain.tasks[0]
    assert sent == [] and alerts == []
    scripts.tick(NIGHT)  # the next tick does not write it again
    assert len(brain.tasks) == 1


def test_morning_sends_ua_de_cover_and_post(root):
    scripts, _, git, sent, _ = make(root, answer())
    scripts.tick(NIGHT)
    scripts.tick(MORNING)
    (text,) = sent
    assert text.startswith("Сценарій 004 «Вечір з Сірим» на вт 01.12 о 08:00.")
    assert "Пилип: Сезон закрито. Сім таблиць, і жодна не сходиться з іншою." in text
    assert "Isegrim: Guten Abend." in text
    assert "[на екрані: Таблиця 1 … Таблиця 7  ❌ не сходиться]" in text
    assert "Обкладинка: Пилип, Сірий; на моніторі: «7 таблиць. / Жодна не сходиться.»" in text
    assert "#Automatisierung" in text
    assert "приймаю пн 30.11 о 07:00" in text  # T-1d 07:00
    (slot,) = load_slots(root / "factory/slots.yaml").items
    assert slot.state == State.SENT
    assert slot.messages == {"script": 501}
    copy = root / "Desktop/temp/004-vovchyi-dub-script.md"
    assert "## DE" in copy.read_text(encoding="utf-8")
    assert git.synced[-1][0] == "script sent: 004-vovchyi-dub"
    scripts.tick(MORNING)
    assert len(sent) == 1


def test_woken_late_does_both_at_once(root):
    scripts, _, _, sent, _ = make(root, answer())
    scripts.tick(datetime(2026, 11, 28, 6, 50, tzinfo=BERLIN))
    assert sent == []
    scripts.tick(datetime(2026, 11, 28, 7, 20, tzinfo=BERLIN))
    assert len(sent) == 1


def test_temp_folder_is_made_every_time(root):
    scripts, _, _, sent, _ = make(root, answer())
    scripts.tick(NIGHT)
    assert not (root / "Desktop").exists()
    scripts.tick(MORNING)
    assert (root / "Desktop/temp/004-vovchyi-dub-script.md").is_file()


def test_a_broken_script_goes_back_with_its_problems(root):
    broken = episode_yaml(**{"scene: hut, camera: medium": "scene: barn, camera: medium"})
    scripts, brain, _, _, alerts = make(root, answer(text=broken), answer())
    scripts.tick(NIGHT)
    assert len(brain.tasks) == 2
    assert "'barn'" in brain.tasks[1]
    assert "Your last attempt:" in brain.tasks[1]
    assert alerts == []
    assert (root / "episodes/004-vovchyi-dub").is_dir()


def test_wrong_release_and_id_are_problems(root):
    wrong = episode_yaml(number="009", release=datetime(2026, 12, 3, 8, 0, tzinfo=BERLIN))
    scripts, brain, *_ = make(root, answer(text=wrong), answer())
    scripts.tick(NIGHT)
    assert "id must be '004'" in brain.tasks[1]
    assert "release must be '2026-12-01T08:00:00+01:00'" in brain.tasks[1]


def test_three_failed_tries_alert_and_leave_the_queue(root):
    bad = answer(slug="Vovchyi Dub")
    scripts, brain, git, _, alerts = make(root, bad, bad, BrainError("timeout"))
    scripts.tick(NIGHT)
    assert len(brain.tasks) == 3
    (alert,) = alerts
    assert alert.startswith("Сценарій на вт 01.12 не склався з 3 спроб: timeout.")
    assert "(1 з 3)" in alert
    assert len(load_queue(root / "factory/queue.yaml")) == 2
    assert load_slots(root / "factory/slots.yaml").items == ()
    assert not (root / "episodes/004-vovchyi-dub").exists()
    assert git.synced == []


def test_gives_up_after_three_rounds(root):
    errors = [BrainError("timeout")] * (3 * ROUNDS)
    scripts, brain, _, _, alerts = make(root, *errors)
    for _ in range(ROUNDS + 1):
        scripts.tick(NIGHT)
    assert len(brain.tasks) == 3 * ROUNDS
    assert len(alerts) == ROUNDS
    assert "так і не склався" in alerts[-1]


def test_logged_out_claude_is_not_a_failed_try(root):
    scripts, *_ = make(root, BrainAuthError())
    with pytest.raises(BrainAuthError):
        scripts.tick(NIGHT)


def test_too_late_for_the_slot_goes_to_the_next(root):
    # Woke up after Saturday 07:00: Tuesday is closed, the idea goes to Thursday 03.12,
    # whose night is Monday 30.11 02:00.
    thursday = datetime(2026, 12, 3, 8, 0, tzinfo=BERLIN)
    scripts, brain, *_ = make(root, answer(text=episode_yaml(release=thursday)))
    scripts.tick(datetime(2026, 11, 28, 9, 0, tzinfo=BERLIN))
    assert brain.tasks == []
    scripts.tick(datetime(2026, 11, 30, 2, 0, tzinfo=BERLIN))
    assert "Release: 2026-12-03T08:00:00+01:00" in brain.tasks[0]
    (slot,) = load_slots(root / "factory/slots.yaml").items
    assert slot.release == thursday


def test_an_undrawn_scene_is_a_problem(root):
    # declared in `scenes`, so validate passes, but the renderer has no drawing for it
    barn = episode_yaml(
        **{
            'hut: "Pylyp': 'barn: "Pylyp',
            "scene: hut,": "scene: barn,",
        }
    )
    scripts, brain, *_ = make(root, answer(text=barn), answer())
    scripts.tick(NIGHT)
    assert "scene 'barn' is not drawn" in brain.tasks[1]
