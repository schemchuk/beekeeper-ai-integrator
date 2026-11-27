"""The brain: one `claude -p` run per job (ADR 008).

Each job has a prompt file `prompts/<job>.md` and an answer schema
`prompts/<job>.schema.json`, both in git. A run gets the prompt plus the job's input on
stdin, answers JSON (`--json-schema`), and is checked here against the schema again.
Tools are narrow: reading anywhere in the repo, writing only where the job may write
(`bible/` or one episode folder). No shell, no network, no MCP, no git: the factory commits.

The runner (how `claude` is started) is injectable; tests use recorded answers, so CI never
runs Claude.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROMPTS = Path("prompts")
VOICE = Path("voice/volodymyr.md")  # his way of speaking (F1.4), sent with `Job.voice`
READ_TOOLS = ("Read", "Glob", "Grep")
DEFAULT_TIMEOUT = 15 * 60  # seconds; a script job is a few minutes (architecture §5)

AUTH_HINTS = (
    "login",
    "log in",
    "logged out",
    "authenticat",
    "oauth",
    "api key",
    "401",
    "unauthorized",
)

AUTH_MESSAGE = (
    "Claude Code на ноутбуці розлогінився, тож писати й розбирати я зараз не можу. "
    "Відкрий термінал, набери claude і зроби /login. Решта фабрики працює далі."
)


class BrainError(RuntimeError):
    """A brain job failed: timeout, a broken answer, or an answer off the schema."""


class BrainAuthError(BrainError):
    """Claude Code is not logged in. The message is meant for Volodymyr as it is."""

    def __init__(self) -> None:
        super().__init__(AUTH_MESSAGE)


@dataclass(frozen=True)
class Run:
    """What the runner reports back: exit code and the two output streams."""

    returncode: int
    stdout: str
    stderr: str = ""


Runner = Callable[[Sequence[str], str, Path, int], Run]


def subprocess_runner(args: Sequence[str], stdin: str, cwd: Path, timeout: int) -> Run:
    try:
        done = subprocess.run(
            list(args),
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BrainError(f"claude did not answer in {timeout} s") from None
    except FileNotFoundError:
        raise BrainError(f"{args[0]} is not installed or not on PATH") from None
    return Run(done.returncode, done.stdout, done.stderr)


@dataclass(frozen=True)
class Job:
    """A brain job: which prompt, which folders it may write to, how long it may take."""

    name: str
    writes: tuple[str, ...] = ()  # repo-relative folders, e.g. ("bible",)
    timeout: int = DEFAULT_TIMEOUT
    model: str | None = None  # None: Claude Code's default
    voice: bool = False  # send voice/volodymyr.md with the prompt: the job writes to him


class Brain:
    def __init__(
        self,
        root: Path = Path("."),
        runner: Runner = subprocess_runner,
        claude: str = "claude",
    ) -> None:
        self.root = root
        self.runner = runner
        self.claude = claude

    def prompt(self, job: Job) -> str:
        return self._read(f"{job.name}.md")

    def schema(self, job: Job) -> dict:
        try:
            return json.loads(self._read(f"{job.name}.schema.json"))
        except json.JSONDecodeError as e:
            raise BrainError(f"prompts/{job.name}.schema.json is not JSON: {e}") from None

    def voice(self) -> str:
        """His style notes as a block for the prompt; a note if the file is missing."""
        path = self.root / VOICE
        body = path.read_text(encoding="utf-8").strip() if path.is_file() else "(missing)"
        return f"How Volodymyr speaks ({VOICE}); write to him in this manner:\n\n{body}"

    def _read(self, name: str) -> str:
        path = self.root / PROMPTS / name
        if not path.is_file():
            raise BrainError(f"missing prompt file {PROMPTS / name}")
        return path.read_text(encoding="utf-8")

    def args(self, job: Job, schema: dict) -> list[str]:
        tools = list(READ_TOOLS)
        allowed = list(READ_TOOLS)
        if job.writes:
            tools += ["Edit", "Write"]
            for folder in job.writes:
                folder = folder.strip("/")
                if not folder or ".." in Path(folder).parts:
                    raise BrainError(f"job {job.name}: bad write folder {folder!r}")
                allowed += [f"Edit({folder}/**)", f"Write({folder}/**)"]
        args = [
            self.claude,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema),
            "--tools",
            ",".join(tools),
            "--allowedTools",
            *allowed,
            "--permission-mode",
            "dontAsk",  # anything not allowed above is refused, never asked
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if job.model:
            args += ["--model", job.model]
        return args

    def ask(self, job: Job, task: str) -> dict:
        """Run the job with `task` (his words, the idea, the edit ...); the checked answer."""
        schema = self.schema(job)
        stdin = f"{self.prompt(job).rstrip()}\n\n---\n\n"
        if job.voice:
            stdin += f"{self.voice()}\n\n---\n\n"
        stdin += f"{task.strip()}\n"
        run = self.runner(self.args(job, schema), stdin, self.root, job.timeout)
        answer = parse_result(run, job.name)
        problems = check(answer, schema)
        if problems:
            raise BrainError(f"{job.name}: answer off the schema: {'; '.join(problems)}")
        return answer


def parse_result(run: Run, name: str) -> dict:
    """The structured answer from `claude -p --output-format json`, or a clear error."""
    try:
        body = json.loads(run.stdout) if run.stdout.strip() else None
    except json.JSONDecodeError:
        body = None
    message = ""
    if isinstance(body, dict):
        message = str(body.get("result", ""))
        if not body.get("is_error") and body.get("subtype") == "success":
            answer = body.get("structured_output")
            if isinstance(answer, dict):
                return answer
            raise BrainError(f"{name}: no structured answer in the result")
    text = f"{message}\n{run.stderr}".lower()
    if any(hint in text for hint in AUTH_HINTS):
        raise BrainAuthError()
    detail = (message or run.stderr or run.stdout).strip().splitlines()
    first = detail[0][:300] if detail else f"exit code {run.returncode}"
    raise BrainError(f"{name}: claude failed: {first}")


def check(value: object, schema: dict, where: str = "answer") -> list[str]:
    """Problems of `value` against a JSON schema (the subset the prompts use)."""
    problems: list[str] = []
    kind = schema.get("type")
    if kind is not None:
        kinds = kind if isinstance(kind, list) else [kind]
        if not any(_is(value, k) for k in kinds):
            return [f"{where}: expected {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: {value!r} not one of {schema['enum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{where}: missing '{key}'")
        for key, item in value.items():
            if key in props:
                problems += check(item, props[key], f"{where}.{key}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{where}: unexpected '{key}'")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            problems += check(item, schema["items"], f"{where}[{i}]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{where}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{where}: too long")
    return problems


def _is(value: object, kind: str) -> bool:
    if kind == "boolean":
        return isinstance(value, bool)
    if isinstance(value, bool):  # True is an int in Python, not in JSON
        return False
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "null": type(None),
    }
    return kind in types and isinstance(value, types[kind])


def smoke_test() -> None:
    """By hand, on the subscription: `python -m beekeeper.factory.brain`."""
    answer = Brain().ask(Job("hello", timeout=120), "Скажи, що мозок фабрики на місці.")
    print(answer)


if __name__ == "__main__":
    smoke_test()
