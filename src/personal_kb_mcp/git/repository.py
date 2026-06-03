import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitRepository:
    """Small git adapter for committing changed vault paths."""

    root: Path
    committer_name: str = "Personal KB MCP"
    committer_email: str = "personal-kb@example.invalid"

    def commit_paths(self, paths: list[Path], message: str) -> str:
        relative_paths = [self._relative_path(path) for path in paths]
        self._run(["add", "--", *relative_paths])
        self._run(
            [
                "-c",
                f"user.name={self.committer_name}",
                "-c",
                f"user.email={self.committer_email}",
                "commit",
                "-m",
                message,
            ]
        )
        return self.head_hash()

    def head_hash(self) -> str:
        return self._run(["rev-parse", "HEAD"]).strip()

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def _run(self, args: list[str]) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout
