import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from common.model import FrozenModel

DEFAULT_REMOTE = "origin"
VAULT_PATHSPEC = "."


@dataclass(frozen=True)
class GitPushOutcome:
    remote: str
    branch: str
    push_tool: str
    push_command: str


class GitRepository(FrozenModel):
    """Small git adapter for committing changed vault paths."""

    root: Path
    committer_name: str = "LLM Wiki MCP"
    committer_email: str = "llm-wiki@example.invalid"

    def commit_paths(self, paths: list[Path], message: str) -> str:
        relative_paths = [self._relative_path(path) for path in paths]
        self._run(["add", "--", *relative_paths])
        self._commit(message, relative_paths)
        return self.head_hash()

    def commit_all_changed(self, message: str) -> str | None:
        if not self.has_changes():
            return None
        self._run(["add", "-A", "--", VAULT_PATHSPEC])
        if not self.has_staged_changes():
            return None
        self._commit(message, [VAULT_PATHSPEC])
        return self.head_hash()

    def has_changes(self) -> bool:
        return bool(self._run(["status", "--porcelain", "--", VAULT_PATHSPEC]).strip())

    def has_staged_changes(self) -> bool:
        completed = self._run_unchecked(["diff", "--cached", "--quiet", "--", VAULT_PATHSPEC])
        if completed.returncode not in (0, 1):
            completed.check_returncode()
        return completed.returncode == 1

    def head_hash(self) -> str:
        return self._run(["rev-parse", "HEAD"]).strip()

    def push(self) -> GitPushOutcome:
        resolved_branch = self.current_branch()
        if shutil.which("gh") is not None:
            gh_status = self._run_gh_unchecked(["auth", "status"])
            if gh_status.returncode == 0:
                self._run(["push", DEFAULT_REMOTE, resolved_branch])
                return GitPushOutcome(
                    remote=DEFAULT_REMOTE,
                    branch=resolved_branch,
                    push_tool="gh+git",
                    push_command=f"gh auth status && git push {DEFAULT_REMOTE} {resolved_branch}",
                )

        self._run(["push", DEFAULT_REMOTE, resolved_branch])
        return GitPushOutcome(
            remote=DEFAULT_REMOTE,
            branch=resolved_branch,
            push_tool="git",
            push_command=f"git push {DEFAULT_REMOTE} {resolved_branch}",
        )

    def current_branch(self) -> str:
        branch = self._run(["branch", "--show-current"]).strip()
        if not branch:
            raise RuntimeError("cannot push vault because HEAD is detached and no branch was set")
        return branch

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def _commit(self, message: str, pathspecs: list[str]) -> None:
        self._run(
            [
                "-c",
                f"user.name={self.committer_name}",
                "-c",
                f"user.email={self.committer_email}",
                "commit",
                "-m",
                message,
                "--",
                *pathspecs,
            ]
        )

    def _run(self, args: list[str]) -> str:
        completed = self._run_unchecked(args)
        completed.check_returncode()
        return completed.stdout

    def _run_unchecked(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )

    def _run_gh_unchecked(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gh", *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
