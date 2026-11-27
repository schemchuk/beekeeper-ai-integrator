import json
from datetime import datetime
from pathlib import Path

import pytest

from beekeeper.factory import review as review_module
from beekeeper.factory.brain import BrainAuthError, BrainError
from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.intake import Intake
from beekeeper.factory.review import (
    DE_MARKED,
    DE_SAME,
    JOB,
    NOTHING_OPEN,
    Review,
    is_approve,
    mark,
)
from beekeeper.factory.script import JOB as SCRIPT_JOB
from beekeeper.factory.slots import State, load_slots
from test_script import MORNING, NIGHT, FakeGit, answer, episode_yaml, make, make_root

REPO = Path(__file__).resolve().parent.parent
EPISODE = "004-vovchyi-dub"
EDITED = datetime(2026, 11, 28, 9, 0, tzinfo=BERLIN)  # Saturday, after the script came
ACCEPT = datetime(2026, 11, 30, 7, 0, tzinfo=BERLIN)  # T-1d 07:00

UA_OLD = "Сезон закрито. Сім таблиць, і жодна не сходиться з іншою."
UA_NEW = "Сезон закрито. Сім таблиць, і всі брешуть по-різному."


TEMPLATE_DE = "Saison abgeschlossen. Sieben Tabellen, und keine passt zur anderen."
DE_NEW = TEMPLATE_DE.replace("Sieben Tabellen", "Sieben verlogene Tabellen")


def edited_yaml(ua=True, de=True):
    swap = {}
    if ua:
        swap[UA_OLD] = UA_NEW
    if de:
        swap[TEMPLATE_DE] = DE_NEW
    return episode_yaml(slug="vovchyi-dub", **swap)


def edit_answer(text=None, reply="Переписав, тепер таблиці брешуть."):
    commit = "script edit: 004 lying tables"
    return {"yaml": text or edited_yaml(), "reply": reply, "commit": commit}


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


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


@pytest.fixture
def sent(root):
    """A script written at night and sent in the morning: slot 004 is `sent`."""
    scripts, *_ = make(root, answer())
    scripts.tick(NIGHT)
    scripts.tick(MORNING)
    return root


def make_review(root, *answers):
    brain, git, out = FakeBrain(*answers), FakeGit(), []

    def send(text):
        out.append(text)
        return [900 + len(out)]

    review = Review(brain, send, root, git, temp=root / "Desktop/temp")
    return review, brain, git, out


def slot_of(root):
    (slot,) = load_slots(root / "factory/slots.yaml").items
    return slot


# --- marking -------------------------------------------------------------------------


def test_mark_wraps_new_words():
    old = ["Isegrim: Guten Abend.", "Philipp: Sieben Tabellen."]
    new = ["Isegrim: Guten Abend.", "Philipp: Sieben verlogene Tabellen, alle."]
    assert mark(old, new) == [
        "Isegrim: Guten Abend.",
        "Philipp: Sieben *verlogene Tabellen, alle.*",
    ]


def test_mark_a_new_line_and_no_change():
    assert mark(["A b."], ["A b.", "C d."]) == ["A b.", "*C d.*"]
    assert mark(["A b."], ["A b."]) == ["A b."]
    assert mark([], []) == []


def test_approve_words():
    for word in ("погоджую", "Погоджую.", "погоджую!", "згоден", "/approve"):
        assert is_approve(word), word
    for word in ("погоджую, але заміни фінал", "не погоджую", "черга"):
        assert not is_approve(word), word


# --- the edit ------------------------------------------------------------------------


def test_an_edit_rewrites_ua_and_de_and_marks_the_german(sent):
    review, brain, git, out = make_review(sent, edit_answer())
    assert review.edit("Хай таблиці брешуть по-різному.", EDITED) == ""
    yaml_text = (sent / f"episodes/{EPISODE}/episode.yaml").read_text(encoding="utf-8")
    assert UA_NEW in yaml_text and DE_NEW in yaml_text
    (text,) = out
    assert text.startswith("Переписав, тепер таблиці брешуть.")
    assert DE_MARKED in text
    assert "Новий сценарій 004" in text
    assert f"Пилип: {UA_NEW}" in text  # UA without marks
    assert "*verlogene*" in text
    assert "Isegrim: Guten Abend." in text  # an unchanged German line is not marked
    slot = slot_of(sent)
    assert slot.state == State.SENT
    assert slot.messages == {"script": 901}  # a "Reply" now points to the new message
    assert slot.times["sent"] == EDITED
    copy = (sent / f"Desktop/temp/{EPISODE}-script.md").read_text(encoding="utf-8")
    assert UA_NEW in copy
    assert git.synced == [("script edit: 004 lying tables", ("bible", "factory", "episodes"))]
    task = brain.tasks[0]
    assert "His edit:\nХай таблиці брешуть по-різному." in task
    assert "The current episode.yaml:" in task and UA_OLD in task


def test_a_ua_only_edit_says_the_german_is_the_same(sent):
    review, _, _, out = make_review(sent, edit_answer(edited_yaml(de=False)))
    review.edit("Заміни рядок.", EDITED)
    assert DE_SAME in out[0]
    assert "*" not in out[0].split("🇩🇪")[1].split("Обкладинка")[0]


def test_a_broken_edit_goes_back_with_its_problems(sent):
    broken = edited_yaml().replace("scene: hut, camera: medium", "scene: barn, camera: medium")
    review, brain, _, out = make_review(sent, edit_answer(broken), BrainError("x"), edit_answer())
    review.edit("Правка.", EDITED)
    assert len(brain.tasks) == 3
    assert "'barn'" in brain.tasks[1] and "Your last attempt:" in brain.tasks[1]
    assert UA_NEW in (sent / f"episodes/{EPISODE}/episode.yaml").read_text(encoding="utf-8")
    assert len(out) == 1


def test_a_failed_edit_keeps_the_old_script(sent):
    path = sent / f"episodes/{EPISODE}/episode.yaml"
    before = path.read_text(encoding="utf-8")
    wrong_id = edited_yaml().replace('id: "004"', 'id: "009"')
    review, brain, git, out = make_review(
        sent, edit_answer(wrong_id), edit_answer(wrong_id), BrainError("timeout")
    )
    reply = review.edit("Правка.", EDITED)
    assert reply.startswith("Правку не вніс з 3 спроб: timeout.")
    assert path.read_text(encoding="utf-8") == before
    assert out == [] and git.synced == []
    assert slot_of(sent).messages == {"script": 501}


def test_logged_out_claude_is_raised(sent):
    review, *_ = make_review(sent, BrainAuthError())
    with pytest.raises(BrainAuthError):
        review.edit("Правка.", EDITED)


def test_nothing_to_edit_without_a_waiting_script(root):
    review, brain, *_ = make_review(root)
    assert review.edit("Правка.", EDITED) == NOTHING_OPEN
    assert review.approve(EDITED) == NOTHING_OPEN
    assert brain.tasks == []


# --- approval ------------------------------------------------------------------------


def test_pogodzhuyu_accepts_at_once(sent):
    review, brain, git, out = make_review(sent)
    reply = review.approve(EDITED)
    assert reply == "Прийняв 004 «Вечір з Сірим» на вт 01.12. Далі ролик."
    slot = slot_of(sent)
    assert slot.state == State.ACCEPTED and slot.times["accepted"] == EDITED
    assert git.synced[-1][0] == f"script accepted (approved): {EPISODE}"
    assert brain.tasks == [] and out == []
    review.tick(ACCEPT)  # the silence rule finds nothing to do any more
    assert out == []


def test_silence_accepts_at_t_minus_one_day_seven(sent):
    review, _, git, out = make_review(sent)
    assert review.tick(datetime(2026, 11, 30, 6, 45, tzinfo=BERLIN)) == 0
    assert slot_of(sent).state == State.SENT
    assert review.tick(ACCEPT) == 1
    assert out == ["Мовчання — знак згоди: прийняв 004 «Вечір з Сірим» на вт 01.12. Далі ролик."]
    assert slot_of(sent).state == State.ACCEPTED
    assert git.synced[-1][0] == f"script accepted (silence): {EPISODE}"
    assert review.tick(ACCEPT) == 0


def test_after_an_edit_silence_still_accepts(sent):
    review, _, _, out = make_review(sent, edit_answer())
    review.edit("Правка.", EDITED)
    review.tick(ACCEPT)
    assert slot_of(sent).state == State.ACCEPTED
    assert UA_NEW in (sent / f"episodes/{EPISODE}/episode.yaml").read_text(encoding="utf-8")


# --- routing ------------------------------------------------------------------------


def test_route_reply_to_the_script_is_an_edit(sent):
    review, brain, _, out = make_review(sent, edit_answer())
    assert review.route("Хай брешуть.", 501, EDITED) == ""
    assert len(brain.tasks) == 1 and len(out) == 1


def test_route_approve_and_the_rest(sent):
    review, brain, *_ = make_review(sent)
    assert review.route("Тут нова побрехенька.", None, EDITED) is None
    assert review.route("Тут нова побрехенька.", 77, EDITED) is None  # a reply to another one
    assert review.route("Погоджую.", None, EDITED).startswith("Прийняв 004")
    assert review.route("погоджую", None, EDITED) is None  # nothing waits any more
    assert brain.tasks == []


# --- intake: the brain may call it an edit or an approval ---------------------------


class IntakeBrain:
    def __init__(self, answer):
        self.answer = answer
        self.tasks = []

    def ask(self, job, task):
        assert job.name == "intake"
        self.tasks.append(task)
        return self.answer


def intake_answer(kind, episode=EPISODE):
    return {
        "kind": kind,
        "reply": "",
        "question": None,
        "story": None,
        "command": None,
        "episode": episode,
        "commit": "x",
    }


def test_intake_edit_goes_to_the_review(sent):
    review, brain, _, out = make_review(sent, edit_answer())
    ibrain = IntakeBrain(intake_answer("edit"))
    intake = Intake(ibrain, sent, FakeGit(), review=review)
    assert intake.process("Хай таблиці брешуть.", 31, EDITED) == ""
    assert "Scripts waiting for his approval" in ibrain.tasks[0]
    assert f"{EPISODE}: «Вечір з Сірим» (2026-12-01)" in ibrain.tasks[0]
    assert "His edit:\nХай таблиці брешуть." in brain.tasks[0]
    assert len(out) == 1
    assert not (sent / "bible/stories").exists()


def test_intake_approve(sent):
    review, *_ = make_review(sent)
    intake = Intake(IntakeBrain(intake_answer("approve")), sent, FakeGit(), review=review)
    assert intake.process("Добре, хай іде.", 32, EDITED).startswith("Прийняв 004")
    assert slot_of(sent).state == State.ACCEPTED


def test_intake_edit_without_a_waiting_script_is_an_error(root):
    review, *_ = make_review(root)
    intake = Intake(IntakeBrain(intake_answer("edit")), root, FakeGit(), review=review)
    with pytest.raises(BrainError):
        intake.process("Заміни фінал.", 33, EDITED)


# --- the prompt files --------------------------------------------------------------


def test_edit_prompt_and_schema_exist():
    schema = json.loads((REPO / "prompts/edit.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) == {"yaml", "reply", "commit"}
    prompt = (REPO / "prompts/edit.md").read_text(encoding="utf-8")
    assert "do not translate word for word" in prompt
    intake = json.loads((REPO / "prompts/intake.schema.json").read_text(encoding="utf-8"))
    assert {"edit", "approve"} <= set(intake["properties"]["kind"]["enum"])


def test_the_edit_job_writes_nothing():
    assert JOB.writes == () and SCRIPT_JOB.writes == ()
    assert review_module.JOB.name == "edit"
