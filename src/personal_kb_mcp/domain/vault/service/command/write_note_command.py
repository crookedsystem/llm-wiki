from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WriteNoteCommand:
    note_path: str | Path
    content: str
    if_hash: str | None = None
