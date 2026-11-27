import json
from datetime import datetime
from pathlib import Path

import pytest

from beekeeper.factory.brain import Brain, BrainAuthError, BrainError, Job, Run, check
from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.intake import JOB as INTAKE_JOB
from beekeeper.factory.review import JOB as EDIT_JOB
from beekeeper.factory.script import JOB as SCRIPT_JOB
from beekeeper.factory.service import Factory
from beekeeper.factory.style import JOB, SECTION, Style
from beekeeper.factory.telegram import Update
from test_factory_service import FakeBot, FakeEars, FakeIntake, FakeWall, drain, voice_note

REPO = Path(__file__).resolve().parent.parent
DAY = datetime(2026, 11, 27, 21, 15, tzinfo=BERLIN)
MORNING = datetime(2026, 11, 28, 7, 0, tzinfo=BERLIN)
VOICE_FILE = "# Volodymyr's voice\n\n## Phrases collected\n\n- \"зв'язок з бджолами по вай-фаю\"\n"

PEAR = "Груша на вербі родить, коли бухгалтер спить"
OLD = "зв'язок з бджолами по вай-фаю"


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


def phrases(*pairs, commit="voice: the pear"):
    return {"phrases": [{"quote": q, "note": n} for q, n in pairs], "commit": commit}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "voice").mkdir()
    (tmp_path / "voice/volodymyr.md").write_text(VOICE_FILE, encoding="utf-8")
    return tmp_path


def make(root, *answers):
    sent, git = [], FakeGit()
    style = Style(FakeBrain(*answers), send=sent.append, root=root, git=git)
    return style, sent, git


def test_a_sample_day_adds_a_phrase(root):
    style, sent, git = make(
        root,
        phrases(
            (f"«{PEAR}»", "never: when the books are done"),
            (OLD, "already there"),
            ("Вигадана фраза, якої він не казав", "made up"),
        ),
    )
    style.record(f"Ну що, {PEAR}. Покажи чергу.", DAY)
    style.record("/start", DAY)
    style.record(f"Ще раз: {OLD}", DAY, source="voice")
    assert style.tick(MORNING) == 1
    text = (root / "voice/volodymyr.md").read_text(encoding="utf-8")
    assert SECTION in text
    assert f'- "{PEAR}" (never: when the books are done; Telegram, 2026-11-27)' in text
    assert text.count(OLD) == 1 and "Вигадана" not in text
    assert git.synced == [("voice: the pear", ("voice/volodymyr.md",))]
    assert sent == [f"Записав у твій словничок:\n«{PEAR}»: never: when the books are done"]
    task = style.brain.tasks[0]
    assert "Day: 2026-11-27" in task and "voice" in task and "/start" not in task
    assert not (root / "work/factory/said/2026-11-27.md").exists()  # learnt, so removed


def test_waits_for_the_morning_and_for_the_day_to_end(root):
    style, sent, _ = make(root)
    style.record(PEAR, DAY)
    assert style.tick(datetime(2026, 11, 28, 6, 45, tzinfo=BERLIN)) == 0  # before 07:00
    assert style.tick(datetime(2026, 11, 27, 23, 0, tzinfo=BERLIN)) == 0  # same day
    assert style.brain.tasks == [] and sent == []


def test_an_ordinary_day_says_nothing(root):
    style, sent, git = make(root, phrases())
    style.record("Покажи чергу.", DAY)
    assert style.tick(MORNING) == 0
    assert sent == [] and git.synced == []
    assert (root / "voice/volodymyr.md").read_text(encoding="utf-8") == VOICE_FILE
    assert not (root / "work/factory/said/2026-11-27.md").exists()


def test_a_failed_job_keeps_the_log_for_the_next_tick(root):
    style, sent, _ = make(root, BrainError("timeout"), phrases((PEAR, "joke")))
    style.record(PEAR, DAY)
    assert style.tick(MORNING) == 0
    assert (root / "work/factory/said/2026-11-27.md").exists()
    assert style.tick(MORNING) == 1


def test_logged_out_goes_up_to_the_alert(root):
    style, _, _ = make(root, BrainAuthError())
    style.record(PEAR, DAY)
    with pytest.raises(BrainAuthError):
        style.tick(MORNING)


def test_factory_logs_texts_and_voice_notes(tmp_path):
    style, _, _ = make(tmp_path)
    clock = lambda: DAY  # noqa: E731
    bot = FakeBot([[Update(update_id=7, kind="text", text=PEAR), voice_note(caption="на четвер")]])
    factory = Factory(
        bot,
        root=tmp_path,
        clock=clock,
        wall=FakeWall(),
        intake=FakeIntake(),
        transcriber=FakeEars("Медунко прокинувся."),
        style=style,
    )
    factory.poll_once(timeout=0)
    drain(factory)
    log = (tmp_path / "work/factory/said/2026-11-27.md").read_text(encoding="utf-8")
    assert "## 21:15 text\n\n" + PEAR in log
    assert "## 21:15 voice\n\nМедунко прокинувся.\n\nна четвер" in log


def test_replies_carry_his_voice_file_in_the_prompt(tmp_path):
    for job in (INTAKE_JOB, SCRIPT_JOB, EDIT_JOB, JOB):
        assert job.voice, job.name
    calls = []

    def runner(args, stdin, cwd, timeout):
        calls.append(stdin)
        body = {"type": "result", "subtype": "success", "is_error": False, "result": ""}
        body["structured_output"] = {"phrases": [], "commit": "voice: none"}
        return Run(0, json.dumps(body))

    (tmp_path / "prompts").mkdir()
    for name in ("style.md", "style.schema.json"):
        (tmp_path / "prompts" / name).write_text((REPO / "prompts" / name).read_text())
    (tmp_path / "voice").mkdir()
    (tmp_path / "voice/volodymyr.md").write_text(VOICE_FILE, encoding="utf-8")
    Brain(root=tmp_path, runner=runner).ask(JOB, "Day: 2026-11-27")
    prompt = (REPO / "prompts/style.md").read_text(encoding="utf-8").rstrip()
    assert calls[0].startswith(prompt)
    assert OLD in calls[0] and calls[0].index(OLD) < calls[0].index("Day: 2026-11-27")
    calls.clear()
    Brain(root=tmp_path, runner=runner).ask(Job("style"), "Day: 2026-11-27")
    assert OLD not in calls[0]  # a job without voice=True does not get it


def test_style_schema():
    schema = json.loads((REPO / "prompts/style.schema.json").read_text())
    assert check(phrases((PEAR, "joke")), schema) == []
    assert check({"phrases": [{"quote": PEAR}], "commit": "x"}, schema)
