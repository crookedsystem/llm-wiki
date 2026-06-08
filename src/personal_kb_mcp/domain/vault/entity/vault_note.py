from dataclasses import dataclass
from hashlib import sha256
from typing import Final

FRONTMATTER_DELIMITER: Final = "---"
PROVENANCE_PREFIX: Final = "<!-- kb-provenance:"


@dataclass(frozen=True)
class ParsedNote:
    """Markdown note split into optional raw frontmatter and body text."""

    frontmatter: str | None
    body: str


def compute_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def parse_note(raw_note: str) -> ParsedNote:
    if not raw_note.startswith(f"{FRONTMATTER_DELIMITER}\n"):
        return ParsedNote(frontmatter=None, body=raw_note)

    closing_delimiter = raw_note.find(f"\n{FRONTMATTER_DELIMITER}\n", 4)
    if closing_delimiter == -1:
        return ParsedNote(frontmatter=None, body=raw_note)

    frontmatter = raw_note[4:closing_delimiter]
    body_start = closing_delimiter + len(f"\n{FRONTMATTER_DELIMITER}\n")
    return ParsedNote(frontmatter=frontmatter, body=raw_note[body_start:])


def append_provenance_trailer(
    content: str,
    *,
    source_hash: str,
    operation: str,
    actor: str,
) -> str:
    content_with_newline = content if content.endswith("\n") else f"{content}\n"
    trailer = (
        f"{PROVENANCE_PREFIX} source_hash={source_hash}; operation={operation}; actor={actor} -->\n"
    )
    return f"{content_with_newline}{trailer}"
