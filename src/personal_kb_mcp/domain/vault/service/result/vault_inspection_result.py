from dataclasses import dataclass


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
    graph_links_total: int
    graph_broken_links_total: int
    graph_orphans_total: int


@dataclass(frozen=True)
class VaultInspectionResult:
    status: VaultStatus
    graph: GraphHealth
    metrics: MetricsSnapshot
