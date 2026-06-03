import asyncio
import subprocess
from pathlib import Path

from personal_kb_mcp.git.repository import GitRepository
from personal_kb_mcp.vault.paths import VaultPaths
from personal_kb_mcp.writes.queue import WriteQueue
from personal_kb_mcp.writes.writer import VaultWriter


def test_write_note_commits_change_and_returns_commit_hash(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        writer = VaultWriter(
            VaultPaths(vault_root),
            WriteQueue(),
            actor="tester",
            git_repository=GitRepository(vault_root),
        )

        result = await writer.write_note("daily/today.md", "Body text")

        assert result.commit_hash is not None
        assert len(result.commit_hash) == 40
        assert _git_stdout(vault_root, "rev-parse", "HEAD") == result.commit_hash
        assert "daily/today.md" in _git_stdout(
            vault_root,
            "show",
            "--name-only",
            "--format=",
            result.commit_hash,
        )

    asyncio.run(exercise_writer())


def _git_stdout(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
