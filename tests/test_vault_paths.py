from pathlib import Path

import pytest

from personal_kb_mcp.vault.paths import VaultPathError, VaultPaths


def test_resolve_note_path_accepts_safe_markdown_path(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    resolved_path = VaultPaths(vault_root).resolve_note_path("daily/today.md")

    assert resolved_path == vault_root.resolve() / "daily" / "today.md"


def test_resolve_note_path_rejects_parent_traversal(tmp_path: Path) -> None:
    paths = VaultPaths(tmp_path / "vault")

    with pytest.raises(VaultPathError, match="outside vault"):
        paths.resolve_note_path("../secret.md")


def test_resolve_note_path_rejects_denied_vault_directories(tmp_path: Path) -> None:
    paths = VaultPaths(tmp_path / "vault")

    with pytest.raises(VaultPathError, match=".git"):
        paths.resolve_note_path(".git/config.md")


def test_resolve_note_path_rejects_symlink_escape(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    outside_root = tmp_path / "outside"
    vault_root.mkdir()
    outside_root.mkdir()
    (vault_root / "linked").symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(VaultPathError, match="outside vault"):
        VaultPaths(vault_root).resolve_note_path("linked/note.md")


def test_resolve_note_path_rejects_non_markdown_files(tmp_path: Path) -> None:
    paths = VaultPaths(tmp_path / "vault")

    with pytest.raises(VaultPathError, match="Only markdown"):
        paths.resolve_note_path("daily/today.txt")
