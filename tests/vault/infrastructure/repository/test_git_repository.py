import asyncio
import subprocess
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from pytest import MonkeyPatch

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_path import VaultPaths
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_git_push_service import VaultGitPushService
from vault.service.vault_write_service import VaultWriteService


def test_git_repository가_연결된_note_작성은_commit_hash를_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: git repository로 초기화된 vault와 git repository adapter가 있다.
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        writer = VaultWriteService(
            paths=VaultPaths(root=vault_root),
            queue=VaultWriteQueue(),
            actor="tester",
            git_repository=GitRepository(root=vault_root),
        )

        # When: note를 작성한다.
        result = await writer.write_note(
            WriteNoteCommand(
                note_path="concepts/today.md",
                title="Today",
                type="concept",
                tags=("git",),
                sources=("raw/articles/source.md",),
                body="## Summary\nBody text",
                created=date(2026, 6, 12),
                updated=date(2026, 6, 12),
            )
        )

        # Then: 작성된 note는 git commit에 포함되고 40자리 commit hash가 반환된다.
        assert result.commit_hash is not None
        assert len(result.commit_hash) == 40
        assert _git_stdout(vault_root, "rev-parse", "HEAD") == result.commit_hash
        assert "concepts/today.md" in _git_stdout(
            vault_root,
            "show",
            "--name-only",
            "--format=",
            result.commit_hash,
        )

    asyncio.run(exercise_writer())


KST = timezone(timedelta(hours=9))


def test_git_push_service는_utc_time_commit_후_git_fallback으로_push한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    async def exercise_push() -> None:
        # Given: 원격 bare repository가 연결된 vault에 변경 파일이 있다.
        vault_root = tmp_path / "vault"
        remote_root = tmp_path / "remote.git"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=vault_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "init", "--bare", remote_root], check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_root)],
            cwd=vault_root,
            check=True,
            capture_output=True,
        )
        (vault_root / "daily.md").write_text("# Daily\n", encoding="utf-8")
        monkeypatch.setattr(
            "vault.infrastructure.repository.git_repository.shutil.which",
            lambda _: None,
        )
        push_service = VaultGitPushService(
            repository=GitRepository(root=vault_root),
            queue=VaultWriteQueue(),
            clock=lambda: datetime(2026, 6, 12, 22, 45, tzinfo=KST),
        )

        # When: gh를 사용할 수 없는 환경에서 push를 수행한다.
        result = await push_service.push_vault()

        # Then: UTC commit message로 커밋된 뒤 원격 main branch로 push된다.
        assert result.committed is True
        assert result.commit_hash is not None
        assert result.push_tool == "git"
        assert result.push_command == "git push origin main"
        assert (
            _git_stdout(vault_root, "log", "-1", "--format=%s") == "2026-06-12 13:45 - vault sync"
        )
        assert _git_stdout(vault_root, "rev-parse", "HEAD") == _git_stdout(
            remote_root,
            "rev-parse",
            "main",
            bare=True,
        )

    asyncio.run(exercise_push())


def test_git_push_service는_상위_worktree에서_vault_path만_commit한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    async def exercise_push() -> None:
        # Given: vault가 더 큰 git worktree의 하위 디렉터리이고 외부 변경도 함께 있다.
        repo_root = tmp_path / "repo"
        vault_root = repo_root / "vault"
        remote_root = tmp_path / "remote.git"
        vault_root.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "init", "--bare", remote_root], check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_root)],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        (vault_root / "index.md").write_text("# Index\n", encoding="utf-8")
        (repo_root / "app.py").write_text("print('initial')\n", encoding="utf-8")
        _git_commit_all(repo_root, "initial")

        (vault_root / "daily.md").write_text("# Daily\n", encoding="utf-8")
        (repo_root / "app.py").write_text("print('outside change')\n", encoding="utf-8")
        (repo_root / "secret.txt").write_text("secret\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repo_root, check=True, capture_output=True)
        monkeypatch.setattr(
            "vault.infrastructure.repository.git_repository.shutil.which",
            lambda _: None,
        )
        push_service = VaultGitPushService(
            repository=GitRepository(root=vault_root),
            queue=VaultWriteQueue(),
            clock=lambda: datetime(2026, 6, 12, 22, 45, tzinfo=UTC),
        )

        # When: vault 하위 경로에서 GitHub push를 수행한다.
        result = await push_service.push_vault()

        # Then: vault 변경만 커밋되고 worktree의 외부 변경은 stage/working tree에 남아 있다.
        assert result.committed is True
        assert result.commit_hash is not None
        assert set(
            _git_stdout(repo_root, "show", "--name-only", "--format=", result.commit_hash).split()
        ) == {"vault/daily.md"}
        assert GitRepository(root=vault_root).has_changes() is False
        status_lines = _git_stdout(repo_root, "status", "--porcelain").splitlines()
        assert any(line.endswith("app.py") for line in status_lines)
        assert "?? secret.txt" in status_lines
        assert _git_stdout(repo_root, "rev-parse", "HEAD") == _git_stdout(
            remote_root,
            "rev-parse",
            "main",
            bare=True,
        )

    asyncio.run(exercise_push())


def _git_commit_all(repo_root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            message,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )


def _git_stdout(repo_root: Path, *args: str, bare: bool = False) -> str:
    git_command = ["git", "--git-dir", str(repo_root), *args] if bare else ["git", *args]
    completed = subprocess.run(
        git_command,
        cwd=None if bare else repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
