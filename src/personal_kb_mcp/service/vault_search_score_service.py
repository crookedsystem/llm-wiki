from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.domain.vault_search import SYNTHESIZED_PAGE_DIRS, NoteMetadata


@dataclass(frozen=True)
class VaultSearchScoreService:
    """검색어와 LLM Wiki 구조를 함께 반영해 note 검색 순위를 계산합니다."""

    def score_note(
        self,
        relative_path: str,
        content: str,
        metadata: NoteMetadata,
        query: str,
        terms: list[str],
    ) -> float:
        path_lower = relative_path.lower()
        content_lower = content.lower()
        query_lower = query.lower()
        title_lower = (metadata.title or "").lower()
        page_type_lower = (metadata.page_type or "").lower()
        tags_lower = " ".join(metadata.tags).lower()
        headings_lower = "\n".join(metadata.headings).lower()

        score = 0.0
        if query_lower in content_lower:
            score += 5.0
        if query_lower in path_lower:
            score += 8.0
        if query_lower in title_lower:
            score += 12.0

        for term in terms:
            if term in title_lower:
                score += 10.0
            if term in path_lower:
                score += 6.0
            if term in page_type_lower:
                score += 4.0
            if term in tags_lower:
                score += 5.0
            score += min(headings_lower.count(term), 3) * 4.0
            score += min(content_lower.count(term), 10) * 1.0

        if score <= 0:
            return 0.0
        return score + self.structure_boost(relative_path)

    def structure_boost(self, relative_path: str) -> float:
        """LLM Wiki에서 사람이 읽는 synthesized page를 raw source보다 조금 우선합니다."""
        path = Path(relative_path)
        if relative_path == "index.md":
            return 8.0
        if relative_path == "SCHEMA.md":
            return 5.0
        if path.parts and path.parts[0] in SYNTHESIZED_PAGE_DIRS:
            return 2.0
        if path.parts and path.parts[0] == "raw":
            return -10.0
        return 0.0
