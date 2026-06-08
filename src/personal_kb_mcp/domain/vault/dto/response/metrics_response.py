from pydantic import BaseModel, Field

from personal_kb_mcp.domain.vault.service.result.vault_inspection_result import MetricsSnapshot


class MetricsResponse(BaseModel):
    vault_notes_total: int = Field(ge=0, description="Vault에서 검색 가능한 Markdown note 수")
    vault_bytes_total: int = Field(ge=0, description="Vault Markdown note 파일의 총 byte 크기")
    graph_links_total: int = Field(ge=0, description="Wiki link 전체 개수")
    graph_broken_links_total: int = Field(
        ge=0, description="대상 note를 찾지 못한 broken wiki link 수"
    )
    graph_orphans_total: int = Field(ge=0, description="다른 note에서 링크되지 않은 orphan note 수")


def metrics_response(snapshot: MetricsSnapshot) -> MetricsResponse:
    return MetricsResponse(
        vault_notes_total=snapshot.vault_notes_total,
        vault_bytes_total=snapshot.vault_bytes_total,
        graph_links_total=snapshot.graph_links_total,
        graph_broken_links_total=snapshot.graph_broken_links_total,
        graph_orphans_total=snapshot.graph_orphans_total,
    )
