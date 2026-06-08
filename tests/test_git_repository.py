import asyncio
import subprocess
from pathlib import Path

from personal_kb_mcp.domain.vault_path import VaultPaths
from personal_kb_mcp.infrastructure.repositories.git_repository import GitRepository
from personal_kb_mcp.service.vault_write_queue import VaultWriteQueue
from personal_kb_mcp.service.vault_write_service import VaultWriteService


def test_git_repository가_연결된_note_작성은_commit_hash를_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: git repository로 초기화된 vault와 git repository adapter가 있다.
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        writer = VaultWriteService(
            VaultPaths(vault_root),
            VaultWriteQueue(),
            actor="tester",
            git_repository=GitRepository(vault_root),
        )

        # When: note를 작성한다.
        result = await writer.write_note("daily/today.md", "Body text")

        # Then: 작성된 note는 git commit에 포함되고 40자리 commit hash가 반환된다.
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
