from pathlib import Path

from common.model import FrozenModel
from vault.infrastructure.repository.vault_note_repository import (
    VaultNoteRepository,
)
from vault.service.result.vault_inspection_result import (
    GraphHealth,
    MetricsSnapshot,
    VaultInspectionResult,
    VaultStatus,
)
from vault.service.vault_wiki_link import extract_wiki_links, normalize_wiki_target


class VaultInspectionService(FrozenModel):
    note_repository: VaultNoteRepository

    def inspect_vault(self) -> VaultInspectionResult:
        note_paths = self.note_repository.markdown_notes()
        status = VaultStatus(
            note_count=len(note_paths),
            total_bytes=self.note_repository.total_bytes(note_paths),
            note_paths=[self.note_repository.relative_path(path) for path in note_paths],
        )
        graph = self._inspect_graph(note_paths)
        metrics = MetricsSnapshot(
            vault_notes_total=status.note_count,
            vault_bytes_total=status.total_bytes,
            graph_links_total=graph.link_count,
            graph_broken_links_total=graph.broken_link_count,
            graph_orphans_total=graph.orphan_count,
        )
        return VaultInspectionResult(status=status, graph=graph, metrics=metrics)

    def _inspect_graph(self, note_paths: list[Path]) -> GraphHealth:
        note_ids = self._note_ids(note_paths)
        incoming_paths: set[Path] = set()
        link_count = 0
        broken_link_count = 0

        for note_path in note_paths:
            for raw_target in extract_wiki_links(self.note_repository.read_note(note_path)):
                link_count += 1
                target_path = note_ids.get(normalize_wiki_target(raw_target))
                if target_path is None:
                    broken_link_count += 1
                    continue
                incoming_paths.add(target_path)

        return GraphHealth(
            link_count=link_count,
            broken_link_count=broken_link_count,
            orphan_count=sum(1 for path in note_paths if path not in incoming_paths),
        )

    def _note_ids(self, note_paths: list[Path]) -> dict[str, Path]:
        ids: dict[str, Path] = {}
        for note_path in note_paths:
            relative_path = Path(self.note_repository.relative_path(note_path))
            ids[relative_path.with_suffix("").as_posix()] = note_path
            ids[note_path.stem] = note_path
        return ids
