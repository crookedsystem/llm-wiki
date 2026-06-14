from pydantic import Field

from common.model import FrozenModel

_FRONTMATTER_BOUNDARY = "---"


class FrontmatterMetadata(FrozenModel):
    title: str | None = None
    page_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class NoteMetadata(FrozenModel):
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]


def extract_note_metadata(content: str) -> NoteMetadata:
    frontmatter = _frontmatter(content)
    frontmatter_metadata = _frontmatter_metadata(frontmatter)
    headings = _headings(content)
    title = frontmatter_metadata.title or (headings[0] if headings else None)
    return NoteMetadata(
        title=title,
        page_type=frontmatter_metadata.page_type,
        tags=frontmatter_metadata.tags,
        headings=headings,
    )


def _frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_BOUNDARY:
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_BOUNDARY:
            return "\n".join(lines[1:index])
    return ""


def _frontmatter_metadata(frontmatter: str) -> FrontmatterMetadata:
    title: str | None = None
    page_type: str | None = None
    tags: list[str] = []
    lines = frontmatter.splitlines()

    for index, line in enumerate(lines):
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue
        key_name = key.strip()
        if key_name == "title" and raw_value.strip():
            title = _normalize_frontmatter_scalar(raw_value)
        elif key_name == "type" and raw_value.strip():
            page_type = _normalize_frontmatter_scalar(raw_value)
        elif key_name == "tags":
            tags = _frontmatter_tags(lines, index, raw_value)

    return FrontmatterMetadata(title=title, page_type=page_type, tags=tags)


def _frontmatter_tags(lines: list[str], index: int, raw_value: str) -> list[str]:
    stripped_value = raw_value.strip()
    if stripped_value.startswith("[") and stripped_value.endswith("]"):
        return [
            _normalize_frontmatter_scalar(part)
            for part in stripped_value[1:-1].split(",")
            if part.strip()
        ]

    tags: list[str] = []
    for following_line in lines[index + 1 :]:
        stripped_line = following_line.strip()
        if not stripped_line.startswith("-"):
            break
        tag = _normalize_frontmatter_scalar(stripped_line[1:])
        if tag:
            tags.append(tag)
    return tags


def _normalize_frontmatter_scalar(raw_value: str) -> str:
    return raw_value.strip().strip("'\"")


def _headings(content: str) -> list[str]:
    headings: list[str] = []
    for line in content.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            heading = stripped_line.lstrip("#").strip()
            if heading:
                headings.append(heading)
    return headings
