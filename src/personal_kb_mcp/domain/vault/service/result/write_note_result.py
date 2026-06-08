from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WriteNoteResult:
    path: Path
    source_hash: str
    content_hash: str
    commit_hash: str | None = None
