import json
from pathlib import Path

import pytest

from beekeeper.factory.brain import (
    AUTH_MESSAGE,
    Brain,
    BrainAuthError,
    BrainError,
    Job,
    Run,
    check,
    parse_result,
)

REPO = Path(__file__).resolve().parent.parent
RECORDED = Path(__file__).parent / "brain"


class Recorder:
    """A fake runner: remembers the call, answers with a canned Run."""

    def __init__(self, run):
        self.run = run
        self.calls = []

    def __call__(self, args, stdin, cwd, timeout):
        self.calls.append((list(args), stdin, cwd, timeout))
        return self.run


def recorded(name):
    return Run(0, (RECORDED / f"{name}.json").read_text(encoding="utf-8"))


def result(**fields):
    body = {"type": "result", "subtype": "success", "is_error": False, "result": ""}
    body.update(fields)
    return Run(0, json.dumps(body))


def test_hello_with_a_recorded_answer():
    runner = Recorder(recorded("hello"))
    answer = Brain(root=REPO, runner=runner).ask(Job("hello"), "Скажи, що мозок на місці.")
    assert answer["reply"].startswith("Мозок фабрики на місці")
    args, stdin, cwd, timeout = runner.calls[0]
    assert stdin.startswith((REPO / "prompts/hello.md").read_text(encoding="utf-8").rstrip())
    assert stdin.rstrip().endswith("Скажи, що мозок на місці.")
    assert cwd == REPO


def test_read_only_job_gets_no_write_tools():
    args = Brain(root=REPO).args(Job("hello"), {"type": "object"})
    tools = args[args.index("--tools") + 1]
    assert tools == "Read,Glob,Grep"
    assert args[args.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in args and "--no-session-persistence" in args
    assert not any("Bash" in a or "Write" in a or "Edit" in a for a in args)


def test_writing_job_writes_only_in_its_folder():
    args = Brain(root=REPO).args(Job("sort", writes=("bible",)), {"type": "object"})
    assert args[args.index("--tools") + 1] == "Read,Glob,Grep,Edit,Write"
    allowed = args[args.index("--allowedTools") + 1 : args.index("--permission-mode")]
    assert allowed == ["Read", "Glob", "Grep", "Edit(bible/**)", "Write(bible/**)"]


@pytest.mark.parametrize("folder", ["", "/", "../etc", "bible/../.."])
def test_bad_write_folder_refused(folder):
    with pytest.raises(BrainError, match="bad write folder"):
        Brain(root=REPO).args(Job("x", writes=(folder,)), {})


def test_model_and_timeout_passed():
    runner = Recorder(recorded("hello"))
    Brain(root=REPO, runner=runner).ask(Job("hello", timeout=42, model="haiku"), "hi")
    args, _, _, timeout = runner.calls[0]
    assert args[args.index("--model") + 1] == "haiku"
    assert timeout == 42


def test_answer_off_schema_refused():
    runner = Recorder(result(structured_output={"reply": ""}))
    with pytest.raises(BrainError, match="off the schema"):
        Brain(root=REPO, runner=runner).ask(Job("hello"), "hi")


def test_missing_prompt_file(tmp_path):
    with pytest.raises(BrainError, match="missing prompt file"):
        Brain(root=tmp_path, runner=Recorder(None)).ask(Job("nope"), "hi")


def test_auth_error_is_plain_words():
    run = Run(1, json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}))
    with pytest.raises(BrainAuthError) as e:
        parse_result(run, "hello")
    assert str(e.value) == AUTH_MESSAGE


def test_auth_error_from_stderr():
    with pytest.raises(BrainAuthError):
        parse_result(Run(1, "", "Invalid API key · Fix external API key"), "hello")


def test_other_failures_are_brain_errors():
    with pytest.raises(BrainError, match="overloaded"):
        parse_result(Run(1, json.dumps({"is_error": True, "result": "API overloaded"})), "x")
    with pytest.raises(BrainError, match="exit code 3"):
        parse_result(Run(3, ""), "x")
    with pytest.raises(BrainError, match="no structured answer"):
        parse_result(result(result="plain text"), "x")


def test_schema_check():
    schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["story", "command"]},
            "ids": {"type": "array", "items": {"type": "integer"}},
            "ok": {"type": "boolean"},
        },
        "required": ["kind"],
        "additionalProperties": False,
    }
    assert check({"kind": "story", "ids": [1, 2], "ok": True}, schema) == []
    assert check({"kind": "poem"}, schema) == [
        "answer.kind: 'poem' not one of ['story', 'command']"
    ]
    assert check({}, schema) == ["answer: missing 'kind'"]
    assert check({"kind": "story", "x": 1}, schema) == ["answer: unexpected 'x'"]
    assert check({"kind": "story", "ids": [True]}, schema) == ["answer.ids[0]: expected integer"]
    assert check({"kind": "story", "ok": 1}, schema) == ["answer.ok: expected boolean"]
    assert check([], schema) == ["answer: expected object"]
