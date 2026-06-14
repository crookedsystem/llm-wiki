from common.model import FrozenModel


class LineMatch(FrozenModel):
    line: int
    snippet: str


class NoteSearchResult(FrozenModel):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatch]


class SearchNotesResult(FrozenModel):
    query: str
    count: int
    results: list[NoteSearchResult]
