from typing_extensions import TypedDict

from personal_kb_mcp.domain.vault.service.result.write_note_result import WriteNoteResult


class WriteNoteResponse(TypedDict):
    path: str
    source_hash: str
    content_hash: str
    commit_hash: str | None


def write_note_response(result: WriteNoteResult) -> WriteNoteResponse:
    return {
        "path": result.path.as_posix(),
        "source_hash": result.source_hash,
        "content_hash": result.content_hash,
        "commit_hash": result.commit_hash,
    }
