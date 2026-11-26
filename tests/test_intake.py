import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from beekeeper.factory.brain import Brain, BrainError, Run
from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.gitsync import GitSync
from beekeeper.factory.intake import JOB, Intake, show_queue
from beekeeper.factory.queue import Queue, load_queue, save_queue
from beekeeper.factory.slots import Slots

REPO = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 26, 12, 30, tzinfo=BERLIN)  # Thursday
TALE = "А було таке: ведмідь заліз у вулик і заснув.\nА бджоли йому колискову."


def answer(
    kind="story", reply="Гарна побрехенька.", title="Ведмідь у вулику", command=None, question=None
):
    return {
        "kind": kind,
        "reply": reply,
        "question": question,
        "story": {"title": title} if kind in ("story", "both") else None,
        "command": command,
        "commit": "story: test",
    }


def cmd(op, idea=None, position=None, title=None):
    return {"op": op, "idea": idea, "position": position, "title": title}


class FakeBrain:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.tasks = []

    def ask(self, job, task):
        assert job == JOB
        self.tasks.append(task)
        return self.answers.pop(0)


class FakeGit:
    def __init__(self):
        self.synced = []

    def sync(self, message, paths=None):
        self.synced.append(message)
        return True


def make(tmp_path, *answers, ideas=()):
    queue = Queue()
    for title in ideas:
        queue, _ = queue.add(title, "chat", NOW)
    save_queue(queue, tmp_path / "factory/queue.yaml")
    brain, git = FakeBrain(*answers), FakeGit()
    return Intake(brain, tmp_path, git), brain, git


def test_a_tall_tale_lands_in_the_bible_and_the_queue(tmp_path):
    intake, brain, git = make(tmp_path, answer())
    reply = intake.process(TALE, 7, NOW)
    story = tmp_path / "bible/stories/2026-11-26-telegram-7.md"
    text = story.read_text(encoding="utf-8")
    assert "> А було таке: ведмідь заліз у вулик і заснув." in text
    assert "> А бджоли йому колискову." in text
    (idea,) = load_queue(tmp_path / "factory/queue.yaml").items
    assert idea.title == "Ведмідь у вулику"
    assert idea.source == "bible/stories/2026-11-26-telegram-7.md"
    # Thu 12:30: the send deadline of Tue 01.12 is Sat 28.11 07:00, so it is still open.
    assert reply.startswith("Гарна побрехенька.")
    assert "у черзі №1, вийде вт 01.12 о 08:00" in reply
    assert git.synced == ["story: test"]
    assert "Reserved story file: bible/stories/2026-11-26-telegram-7.md" in brain.tasks[0]
    assert brain.tasks[0].rstrip().endswith("А бджоли йому колискову.")


def test_the_brain_sees_the_queue(tmp_path):
    intake, brain, _ = make(tmp_path, answer("command", command=cmd("show")), ideas=["Пошта"])
    intake.process("покажи чергу", 8, NOW)
    assert "#1 at 1: Пошта (2026-12-01)" in brain.tasks[0]


def test_show(tmp_path):
    intake, _, _ = make(
        tmp_path, answer("command", "", command=cmd("show")), ideas=["Пошта", "Ярмарок"]
    )
    reply = intake.process("покажи чергу", 8, NOW)
    assert reply == "Черга:\n1. Пошта, вт 01.12\n2. Ярмарок, чт 03.12"
    assert not (tmp_path / "bible").exists()


def test_empty_queue_is_said(tmp_path):
    assert show_queue(Queue(), Slots(), NOW) == "Черга порожня."


@pytest.mark.parametrize(
    "command, order",
    [
        (cmd("first", 3), ["Ярмарок", "Пошта", "Вечір"]),
        (cmd("up", 2), ["Вечір", "Пошта", "Ярмарок"]),
        (cmd("move", 1, 3), ["Вечір", "Ярмарок", "Пошта"]),
        (cmd("delete", 2), ["Пошта", "Ярмарок"]),
        (cmd("rename", 1, title="Лист"), ["Лист", "Вечір", "Ярмарок"]),
    ],
)
def test_queue_commands(tmp_path, command, order):
    intake, _, _ = make(
        tmp_path, answer("command", "", command=command), ideas=["Пошта", "Вечір", "Ярмарок"]
    )
    reply = intake.process("зроби", 9, NOW)
    assert [i.title for i in load_queue(tmp_path / "factory/queue.yaml").items] == order
    assert reply


def test_a_refused_command_leaves_the_queue(tmp_path):
    intake, _, _ = make(tmp_path, answer("command", "", command=cmd("up", 1)), ideas=["Пошта"])
    reply = intake.process("підніми пошту", 9, NOW)
    assert reply.startswith("З чергою не вийшло")
    assert [i.title for i in load_queue(tmp_path / "factory/queue.yaml").items] == ["Пошта"]


def test_both_story_and_command(tmp_path):
    intake, _, _ = make(tmp_path, answer("both", command=cmd("first", 0)), ideas=["Пошта"])
    reply = intake.process(TALE + "\nПостав першою.", 10, NOW)
    titles = [i.title for i in load_queue(tmp_path / "factory/queue.yaml").items]
    assert titles == ["Ведмідь у вулику", "Пошта"]
    assert "у черзі №1" in reply


def test_unsure_asks_once_then_reads_both_messages(tmp_path):
    intake, brain, git = make(tmp_path, answer("unsure", "", question="Це в чергу?"), answer())
    assert intake.process("ведмідь і вулик", 11, NOW) == "Це в чергу?"
    assert git.synced == []
    assert load_queue(tmp_path / "factory/queue.yaml").items == ()
    intake.process("так, це побрехенька", 12, NOW)
    assert 'Earlier message (you asked: "Це в чергу?"):\nведмідь і вулик' in brain.tasks[1]
    story = tmp_path / "bible/stories/2026-11-26-telegram-11.md"
    text = story.read_text(encoding="utf-8")
    assert "> ведмідь і вулик" in text and "> так, це побрехенька" in text
    assert not (tmp_path / "work/factory/pending.yaml").exists()


def test_story_without_title_is_an_error(tmp_path):
    broken = answer()
    broken["story"] = None
    intake, _, git = make(tmp_path, broken)
    with pytest.raises(BrainError):
        intake.process(TALE, 13, NOW)
    assert git.synced == []


def test_recorded_answer_fits_the_schema(tmp_path):
    recorded = (Path(__file__).parent / "brain/intake-story.json").read_text(encoding="utf-8")
    brain = Brain(root=REPO, runner=lambda args, stdin, cwd, timeout: Run(0, recorded))
    intake = Intake(brain, tmp_path, FakeGit())
    reply = intake.process(TALE, 14, NOW)
    assert "ведмідь у вулику" in reply.lower()
    assert (tmp_path / "bible/stories/2026-11-26-telegram-14.md").exists()


def test_schema_and_prompt_exist():
    schema = json.loads((REPO / "prompts/intake.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) >= {"kind", "reply", "story", "command", "commit"}
    assert "bible/stories" in (REPO / "prompts/intake.md").read_text(encoding="utf-8")


def test_intake_may_write_only_the_bible():
    args = Brain(root=REPO).args(JOB, {})
    assert "Write(bible/**)" in args and "Edit(bible/**)" in args
    assert not any(a.startswith(("Write(factory", "Write(voice")) for a in args)


# --- git sync on a real throwaway repository --------------------------------------------


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repos(tmp_path):
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(tmp_path, "clone", "-q", str(remote), str(work))
    for key, value in (("user.name", "Factory"), ("user.email", "f@example.com")):
        git(work, "config", key, value)
    git(work, "checkout", "-q", "-b", "main")
    (work / "README.md").write_text("x\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "init")
    git(work, "push", "-q", "-u", "origin", "main")
    return remote, work


def test_sync_commits_only_content_and_pushes(repos):
    remote, work = repos
    (work / "bible").mkdir()
    (work / "bible/ideas.md").write_text("seed\n")
    (work / "src.py").write_text("code\n")  # code is never committed by the factory
    assert GitSync(work).sync("story: bear")
    log = git(remote, "log", "--format=%s", "main").stdout.split("\n")
    assert log[0] == "content: story: bear"
    files = git(work, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert files == ["bible/ideas.md"]
    assert "src.py" in git(work, "status", "--porcelain").stdout


def test_sync_waits_on_a_branch(repos):
    _, work = repos
    git(work, "checkout", "-q", "-b", "feat/x")
    (work / "factory").mkdir()
    (work / "factory/queue.yaml").write_text("items: []\n")
    assert not GitSync(work).sync("queue")
    assert git(work, "log", "--format=%s", "-1").stdout.strip() == "init"


def test_rejected_push_rebases_and_pushes(repos, tmp_path):
    remote, work = repos
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(remote), str(other))
    for key, value in (("user.name", "Me"), ("user.email", "m@example.com")):
        git(other, "config", key, value)
    (other / "code.py").write_text("y\n")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "feat: code")
    git(other, "push", "-q")
    (work / "bible").mkdir()
    (work / "bible/x.md").write_text("x\n")
    assert GitSync(work).sync("story: x")
    log = git(remote, "log", "--format=%s", "main").stdout.split("\n")
    assert log[:2] == ["content: story: x", "feat: code"]


def test_retry_pushes_what_is_left(repos):
    remote, work = repos
    (work / "bible").mkdir()
    (work / "bible/x.md").write_text("x\n")
    sync = GitSync(work)
    assert sync.commit("story: x")
    assert sync.ahead()
    sync.retry()
    assert not sync.ahead()
    assert git(remote, "log", "--format=%s", "-1", "main").stdout.strip() == "content: story: x"
