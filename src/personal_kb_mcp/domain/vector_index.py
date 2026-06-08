from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IndexedNote:
    path: str
    content: str
    content_hash: str


@dataclass(frozen=True)
class VectorSearchResult:
    path: str
    score: float
    content_hash: str


class VectorIndex(Protocol):
    async def upsert(self, note: IndexedNote) -> None: ...

    async def delete(self, path: str) -> None: ...

    async def search(self, query: str, *, limit: int) -> list[VectorSearchResult]: ...


class NullVectorIndex:
    """No-op vector index used until a provider is configured."""

    async def upsert(self, note: IndexedNote) -> None:
        _ = note

    async def delete(self, path: str) -> None:
        _ = path

    async def search(self, query: str, *, limit: int) -> list[VectorSearchResult]:
        _ = query, limit
        return []
