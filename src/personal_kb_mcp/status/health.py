import re
from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.vault.paths import DEFAULT_DENIED_NAMES

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class VaultStatus:
    note_count: int
    total_bytes: int
    note_paths: list[str]


@dataclass(frozen=True)
class GraphHealth:
    link_count: int
    broken_link_count: int
    orphan_count: int


@dataclass(frozen=True)
class MetricsSnapshot:
    vault_notes_total: int
    vault_bytes_total: int
    graph_broken_links_total: int


@dataclass(frozen=True)
class VaultInspection:
    status: VaultStatus
    graph: GraphHealth
    metrics: MetricsSnapshot


def inspect_vault(vault_root: Path) -> VaultInspection:
    root = vault_root.resolve()
    note_paths = _markdown_notes(root)
    status = VaultStatus(
        note_count=len(note_paths),
        total_bytes=sum(path.stat().st_size for path in note_paths),
        note_paths=[path.relative_to(root).as_posix() for path in note_paths],
    )
    graph = _inspect_graph(root, note_paths)
    metrics = MetricsSnapshot(
        vault_notes_total=status.note_count,
        vault_bytes_total=status.total_bytes,
        graph_broken_links_total=graph.broken_link_count,
    )
    return VaultInspection(status=status, graph=graph, metrics=metrics)


def _markdown_notes(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob("*.md") if not _uses_denied_directory(root, path.resolve())
    )


def _uses_denied_directory(root: Path, path: Path) -> bool:
    return any(part in DEFAULT_DENIED_NAMES for part in path.relative_to(root).parts)


def _inspect_graph(root: Path, note_paths: list[Path]) -> GraphHealth:
    note_ids = _note_ids(root, note_paths)
    incoming_paths: set[Path] = set()
    link_count = 0
    broken_link_count = 0

    for note_path in note_paths:
        for raw_target in WIKI_LINK_PATTERN.findall(note_path.read_text(encoding="utf-8")):
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


def _note_ids(root: Path, note_paths: list[Path]) -> dict[str, Path]:
    ids: dict[str, Path] = {}
    for note_path in note_paths:
        relative_without_suffix = note_path.relative_to(root).with_suffix("").as_posix()
        ids[relative_without_suffix] = note_path
        ids[note_path.stem] = note_path
    return ids


def _normalize_wiki_target(raw_target: str) -> str:
    return raw_target.split("|", 1)[0].split("#", 1)[0].strip()
