import re
from dataclasses import dataclass, field
from typing import Final

QUERY_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[\w가-힣一-龥ぁ-んァ-ン]+",
    re.UNICODE,
)
FRONTMATTER_BOUNDARY: Final = "---"
MAX_SEARCH_LIMIT: Final = 50
SYNTHESIZED_PAGE_DIRS: Final = frozenset({"concepts", "entities", "comparisons", "queries"})


@dataclass(frozen=True)
class SearchQuery:
    query: str
    limit: int


@dataclass(frozen=True)
class LineMatch:
    line: int
    snippet: str


@dataclass(frozen=True)
class NoteSearchResult:
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatch]


@dataclass(frozen=True)
class FrontmatterMetadata:
    title: str | None = None
    page_type: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NoteMetadata:
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]
