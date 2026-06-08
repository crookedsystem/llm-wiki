from personal_kb_mcp.vault.search_constants import MAX_SEARCH_LIMIT
from personal_kb_mcp.vault.search_dto import SearchQuery


def validate_search_request(query: str, limit: int) -> SearchQuery:
    """검색어 공백과 limit 범위를 검증해 검색 엔진이 사용할 query DTO를 만듭니다."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")
    return SearchQuery(query=normalized_query, limit=limit)
