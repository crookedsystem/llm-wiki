from dataclasses import dataclass


@dataclass(frozen=True)
class SearchNotesCommand:
    query: str
    limit: int = 10
    path_prefix: str | None = None
