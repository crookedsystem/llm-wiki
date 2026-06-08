from dataclasses import dataclass, field


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
class SearchNotesResult:
    query: str
    count: int
    results: list[NoteSearchResult]


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
