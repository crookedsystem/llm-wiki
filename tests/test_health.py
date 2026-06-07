from pathlib import Path

from personal_kb_mcp.status.health import inspect_vault


def test_inspect_vault_reports_status_graph_health_and_metrics(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    (vault_root / "daily").mkdir(parents=True)
    (vault_root / "daily" / "a.md").write_text("[[b]] [[missing]]\n", encoding="utf-8")
    (vault_root / "daily" / "b.md").write_text("# B\n", encoding="utf-8")

    inspection = inspect_vault(vault_root)

    assert inspection.status.note_count == 2
    assert inspection.status.total_bytes > 0
    assert inspection.graph.link_count == 2
    assert inspection.graph.broken_link_count == 1
    assert inspection.graph.orphan_count == 1
    assert inspection.metrics.vault_notes_total == 2
    assert inspection.metrics.graph_broken_links_total == 1


def test_inspect_vault_ignores_denied_directories(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    (vault_root / ".git").mkdir(parents=True)
    (vault_root / ".git" / "hidden.md").write_text("Hidden", encoding="utf-8")
    (vault_root / "visible.md").write_text("Visible", encoding="utf-8")

    inspection = inspect_vault(vault_root)

    assert inspection.status.note_count == 1
    assert inspection.status.note_paths == ["visible.md"]
