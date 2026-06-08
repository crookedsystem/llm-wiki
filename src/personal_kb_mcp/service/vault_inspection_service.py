import re
from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.domain.vault_inspection import (
    GraphHealth,
    MetricsSnapshot,
    VaultInspection,
    VaultStatus,
)
from personal_kb_mcp.infrastructure.repositories.vault_note_repository import VaultNoteRepository

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class VaultInspectionService:
    note_repository: VaultNoteRepository

    def inspect_vault(self) -> VaultInspection:
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
        return VaultInspection(status=status, graph=graph, metrics=metrics)

    def _inspect_graph(self, note_paths: list[Path]) -> GraphHealth:
        note_ids = self._note_ids(note_paths)
        incoming_paths: set[Path] = set()
        link_count = 0
        broken_link_count = 0

        for note_path in note_paths:
            for raw_target in WIKI_LINK_PATTERN.findall(self.note_repository.read_note(note_path)):
                link_count += 1
                target_path = note_ids.get(_normalize_wiki_target(raw_target))
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


def inspect_vault(vault_root: Path) -> VaultInspection:
    return VaultInspectionService(VaultNoteRepository(vault_root)).inspect_vault()


def _normalize_wiki_target(raw_target: str) -> str:
    return raw_target.split("|", 1)[0].split("#", 1)[0].strip()
