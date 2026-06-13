from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from common.model import FrozenModel
from vault.entity.vault_note import FRONTMATTER_DELIMITER, PROVENANCE_PREFIX
from vault.service.note_timestamp import NoteTimestamp

WikiNoteType: TypeAlias = Literal[
    "raw",
    "entity",
    "concept",
    "comparison",
    "query",
    "summary",
    "schema",
    "index",
    "log",
]
ConfidenceLevel: TypeAlias = Literal["high", "medium", "low"]

_ROOT_TYPES: dict[str, frozenset[WikiNoteType]] = {
    "raw": frozenset({"raw"}),
    "entities": frozenset({"entity"}),
    "concepts": frozenset({"concept", "summary"}),
    "comparisons": frozenset({"comparison"}),
    "queries": frozenset({"query", "summary"}),
}
_ROOT_FILE_TYPES: dict[str, frozenset[WikiNoteType]] = {
    "SCHEMA.md": frozenset({"schema"}),
    "index.md": frozenset({"index"}),
    "log.md": frozenset({"log"}),
}


class WriteNoteCommand(FrozenModel):
    note_path: str | Path
    title: str = Field(min_length=1)
    type: WikiNoteType
    tags: tuple[str, ...]
    sources: tuple[str, ...]
    body: str = Field(min_length=1)
    created: NoteTimestamp
    updated: NoteTimestamp
    confidence: ConfidenceLevel | None = None
    contested: bool | None = None
    if_hash: str | None = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        if _has_line_separator(value):
            raise ValueError("title must be a single line")
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized

    @field_validator("tags", "sources", mode="before")
    @classmethod
    def _validate_string_list(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list | tuple):
            raise ValueError("value must be a list of strings")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("value must be a list of strings")
            if _has_line_separator(item):
                raise ValueError("list values must be single-line strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError("list values must not be empty")
            normalized.append(stripped)
        return tuple(normalized)

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        normalized = value.strip("\n")
        if not normalized.strip():
            raise ValueError("body must not be empty")
        if normalized.lstrip().startswith(f"{FRONTMATTER_DELIMITER}\n"):
            raise ValueError("body must not include YAML frontmatter")
        if PROVENANCE_PREFIX in normalized:
            raise ValueError("body must not include a provenance trailer")
        if _contains_top_level_heading(normalized):
            raise ValueError("body must not include a top-level heading; title is rendered by tool")
        return normalized

    @model_validator(mode="after")
    def _validate_contract(self) -> "WriteNoteCommand":
        note_path = Path(self.note_path)
        if _contains_parent_segment(note_path):
            raise ValueError("note_path must not contain parent directory segments")
        allowed_types = _allowed_types_for_path(note_path)
        if allowed_types is None:
            raise ValueError(
                "note_path must be SCHEMA.md, index.md, log.md, or live under "
                "raw/, entities/, concepts/, comparisons/, or queries/"
            )
        if self.type not in allowed_types:
            allowed = ", ".join(sorted(allowed_types))
            raise ValueError(f"type {self.type!r} is not allowed for note_path; expected {allowed}")
        if self.updated < self.created:
            raise ValueError("updated must be greater than or equal to created")
        return self


def _allowed_types_for_path(note_path: Path) -> frozenset[WikiNoteType] | None:
    if note_path.name in _ROOT_FILE_TYPES and len(note_path.parts) == 1:
        return _ROOT_FILE_TYPES[note_path.name]
    if not note_path.parts:
        return None
    return _ROOT_TYPES.get(note_path.parts[0])


def _contains_parent_segment(note_path: Path) -> bool:
    return ".." in note_path.parts


def _has_line_separator(value: str) -> bool:
    return value.splitlines() != [value]


def _contains_top_level_heading(markdown: str) -> bool:
    in_fence = False
    fence_marker = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if in_fence and marker == fence_marker:
                in_fence = False
                fence_marker = ""
            elif not in_fence:
                in_fence = True
                fence_marker = marker
            continue
        if not in_fence and line.startswith("# "):
            return True
    return False
