from dataclasses import dataclass
from pathlib import Path


class WriteConflictError(RuntimeError):
    """Raised when an update does not satisfy optimistic concurrency."""


@dataclass(frozen=True)
class WriteNoteResult:
    path: Path
    source_hash: str
    content_hash: str
    commit_hash: str | None = None


@dataclass(frozen=True)
class WriteNoteCommand:
    note_path: str | Path
    content: str
    if_hash: str | None = None
