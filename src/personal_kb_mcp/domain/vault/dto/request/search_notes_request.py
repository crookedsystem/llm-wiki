from dataclasses import dataclass

from personal_kb_mcp.domain.vault.service.command.search_notes_command import SearchNotesCommand


@dataclass(frozen=True)
class SearchNotesRequest:
    query: str
    limit: int = 10
    path_prefix: str | None = None

    def to_command(self) -> SearchNotesCommand:
        return SearchNotesCommand(
            query=self.query,
            limit=self.limit,
            path_prefix=self.path_prefix,
        )
