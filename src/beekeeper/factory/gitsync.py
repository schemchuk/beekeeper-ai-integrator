"""Git sync: the factory commits its content changes to `main` and pushes (ADR 007, A3).

Only content paths are committed (`bible/`, `factory/`, later `episodes/`), never code, and
only while the checkout is on `main`: if someone works on a branch in the same folder, the
changes wait in the working tree and go in with the next sync on `main`. A failed push is
retried on the clock's next tick.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

log = logging.getLogger("beekeeper.factory.git")

BRANCH = "main"
REMOTE = "origin"
CONTENT = ("bible", "factory")

Git = Callable[[Sequence[str], Path], subprocess.CompletedProcess]


def run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)


class GitSync:
    def __init__(self, root: Path = Path("."), git: Git = run_git) -> None:
        self.root = root
        self.git = git

    def _ok(self, *args: str) -> subprocess.CompletedProcess:
        done = self.git(args, self.root)
        if done.returncode != 0:
            log.warning("git %s: %s", " ".join(args), (done.stderr or done.stdout).strip())
        return done

    def on_main(self) -> bool:
        done = self._ok("rev-parse", "--abbrev-ref", "HEAD")
        branch = done.stdout.strip()
        if done.returncode == 0 and branch == BRANCH:
            return True
        log.warning("checkout is on %r, not %s: content waits in the working tree", branch, BRANCH)
        return False

    def commit(self, message: str, paths: Sequence[str] = CONTENT) -> bool:
        """Commit the content paths with `content: <message>`; True if a commit was made."""
        if not self.on_main():
            return False
        paths = [p for p in paths if (self.root / p).exists()]
        if not paths:
            return False
        self._ok("add", "-A", "--", *paths)
        if self.git(["diff", "--cached", "--quiet", "--", *paths], self.root).returncode == 0:
            return False  # nothing changed
        done = self._ok("commit", "-m", f"content: {message}", "--", *paths)
        return done.returncode == 0

    def push(self) -> bool:
        """Push `main`; on a rejected push rebase on the remote once and push again."""
        if not self.on_main():
            return False
        if self._ok("push", REMOTE, BRANCH).returncode == 0:
            return True
        if self._ok("pull", "--rebase", "--autostash", REMOTE, BRANCH).returncode != 0:
            self.git(["rebase", "--abort"], self.root)
            return False
        return self._ok("push", REMOTE, BRANCH).returncode == 0

    def ahead(self) -> bool:
        done = self.git(["rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD"], self.root)
        return done.returncode == 0 and done.stdout.strip() not in ("", "0")

    def sync(self, message: str, paths: Sequence[str] = CONTENT) -> bool:
        """Commit and push. False if anything is left for a later try."""
        if not self.on_main():
            return False
        self.commit(message, paths)
        return self.push() if self.ahead() else True

    def retry(self, _now: object = None) -> None:
        """Clock handler: push commits a failed push left behind."""
        if self.on_main() and self.ahead():
            self.push()
