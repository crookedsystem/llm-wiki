from pathlib import Path

import pytest

from personal_kb_mcp.domain.vault.entity.vault_path import VaultPathError, VaultPaths


def test_vault_path는_안전한_markdown_상대경로를_vault_내부로_해결한다(tmp_path: Path) -> None:
    # Given: vault root와 안전한 markdown 상대경로가 있다.
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # When: note 경로를 resolve한다.
    resolved_path = VaultPaths(vault_root).resolve_note_path("daily/today.md")

    # Then: 결과는 vault 내부의 절대 markdown 경로가 된다.
    assert resolved_path == vault_root.resolve() / "daily" / "today.md"


def test_vault_path는_parent_traversal을_거부한다(tmp_path: Path) -> None:
    # Given: vault 밖으로 나가려는 parent traversal 경로가 있다.
    paths = VaultPaths(tmp_path / "vault")

    # When / Then: 경로 해결은 outside vault 오류로 실패한다.
    with pytest.raises(VaultPathError, match="outside vault"):
        paths.resolve_note_path("../secret.md")


def test_vault_path는_거부된_vault_디렉터리를_거부한다(tmp_path: Path) -> None:
    # Given: .git 내부 파일처럼 거부된 vault 디렉터리 경로가 있다.
    paths = VaultPaths(tmp_path / "vault")

    # When / Then: 경로 해결은 denied directory 오류로 실패한다.
    with pytest.raises(VaultPathError, match=".git"):
        paths.resolve_note_path(".git/config.md")


def test_vault_path는_symlink로_vault_밖으로_나가는_경로를_거부한다(tmp_path: Path) -> None:
    # Given: vault 내부 symlink가 vault 외부 디렉터리를 가리킨다.
    vault_root = tmp_path / "vault"
    outside_root = tmp_path / "outside"
    vault_root.mkdir()
    outside_root.mkdir()
    (vault_root / "linked").symlink_to(outside_root, target_is_directory=True)

    # When / Then: symlink를 따라 vault 밖으로 나가는 경로는 거부된다.
    with pytest.raises(VaultPathError, match="outside vault"):
        VaultPaths(vault_root).resolve_note_path("linked/note.md")


def test_vault_path는_markdown이_아닌_파일을_거부한다(tmp_path: Path) -> None:
    # Given: .txt 확장자를 가진 note 경로가 있다.
    paths = VaultPaths(tmp_path / "vault")

    # When / Then: markdown이 아닌 파일은 거부된다.
    with pytest.raises(VaultPathError, match="Only markdown"):
        paths.resolve_note_path("daily/today.txt")
