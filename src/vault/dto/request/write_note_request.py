from common.model import FrozenModel
from vault.service.command.write_note_command import (
    ConfidenceLevel,
    WikiNoteType,
    WriteNoteCommand,
)
from vault.service.note_timestamp import NoteTimestamp


class WriteNoteRequest(FrozenModel):
    note_path: str
    title: str
    type: WikiNoteType
    tags: list[str]
    sources: list[str]
    body: str
    created: NoteTimestamp
    updated: NoteTimestamp
    confidence: ConfidenceLevel | None = None
    contested: bool | None = None
    if_hash: str | None = None

    def to_command(self) -> WriteNoteCommand:
        return WriteNoteCommand(
            note_path=self.note_path,
            title=self.title,
            type=self.type,
            tags=tuple(self.tags),
            sources=tuple(self.sources),
            body=self.body,
            created=self.created,
            updated=self.updated,
            confidence=self.confidence,
            contested=self.contested,
            if_hash=self.if_hash,
        )
