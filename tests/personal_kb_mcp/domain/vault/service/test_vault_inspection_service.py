from pathlib import Path

from personal_kb_mcp.domain.vault.service.vault_inspection_service import inspect_vault


def test_vault_점검은_상태와_그래프_건강도와_메트릭을_함께_계산한다(tmp_path: Path) -> None:
    # Given: 두 개의 note와 하나의 깨진 wiki link가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "daily").mkdir(parents=True)
    (vault_root / "daily" / "a.md").write_text("[[b]] [[missing]]\n", encoding="utf-8")
    (vault_root / "daily" / "b.md").write_text("# B\n", encoding="utf-8")

    # When: vault 상태를 점검한다.
    inspection = inspect_vault(vault_root)

    # Then: note 수, link 수, broken link 수, orphan 수가 함께 보고된다.
    assert inspection.status.note_count == 2
    assert inspection.status.total_bytes > 0
    assert inspection.graph.link_count == 2
    assert inspection.graph.broken_link_count == 1
    assert inspection.graph.orphan_count == 1
    assert inspection.metrics.vault_notes_total == 2
    assert inspection.metrics.graph_links_total == 2
    assert inspection.metrics.graph_broken_links_total == 1
    assert inspection.metrics.graph_orphans_total == 1


def test_vault_점검은_거부된_디렉터리의_markdown을_무시한다(tmp_path: Path) -> None:
    # Given: .git 디렉터리 안의 markdown과 vault 루트의 markdown이 함께 있다.
    vault_root = tmp_path / "vault"
    (vault_root / ".git").mkdir(parents=True)
    (vault_root / ".git" / "hidden.md").write_text("Hidden", encoding="utf-8")
    (vault_root / "visible.md").write_text("Visible", encoding="utf-8")

    # When: vault 상태를 점검한다.
    inspection = inspect_vault(vault_root)

    # Then: 거부된 디렉터리의 note는 수집 결과에서 제외된다.
    assert inspection.status.note_count == 1
    assert inspection.status.note_paths == ["visible.md"]
