from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.status.health import VaultInspection, inspect_vault
from personal_kb_mcp.vault.search import search_notes
from personal_kb_mcp.vault.search_dto import NoteSearchResult


@dataclass(frozen=True)
class VaultService:
    vault_root: Path

    def search_notes(
        self,
        query: str,
        *,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> list[NoteSearchResult]:
        """설정된 vault root를 기준으로 Markdown note 검색을 실행합니다."""
        return search_notes(self.vault_root, query, limit=limit, path_prefix=path_prefix)

    def inspect_vault(self) -> VaultInspection:
        """설정된 vault root의 파일 수와 wiki graph 지표를 검사합니다."""
        return inspect_vault(self.vault_root)
