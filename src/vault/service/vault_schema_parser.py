import re

from vault.constant.schema import (
    DEFAULT_ALLOWED_TYPES,
    LEVEL_TWO_HEADING,
    REQUIRED_RAW_FIELDS,
    REQUIRED_SYNTH_FIELDS,
    TAG_PATTERN,
    TAG_TAXONOMY_HEADING,
)
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema


def parse_schema_document(content: str) -> ParsedWikiSchema:
    """SCHEMA.md Markdown 문서에서 frontmatter/type/tag taxonomy 계약을 파싱합니다.

    입력은 `SCHEMA.md`의 전체 Markdown 문자열입니다. 출력은 허용 type, 필수 frontmatter
    필드, tag taxonomy, allowed tag list를 담는 `ParsedWikiSchema` 모델입니다.
    """
    tag_taxonomy = _extract_tag_taxonomy(content)
    allowed_tags = sorted({tag for tags in tag_taxonomy.values() for tag in tags})
    allowed_types = _extract_allowed_types(content) or list(DEFAULT_ALLOWED_TYPES)
    return ParsedWikiSchema(
        schema_parse_ok=bool(content and tag_taxonomy),
        allowed_types=allowed_types,
        required_synthesized_frontmatter=list(REQUIRED_SYNTH_FIELDS),
        required_raw_frontmatter=list(REQUIRED_RAW_FIELDS),
        tag_taxonomy=tag_taxonomy,
        allowed_tags=allowed_tags,
    )


def _extract_allowed_types(content: str) -> list[str]:
    match = re.search(r"Allowed `type` values:\s*([^\n]+)", content)
    if match is None:
        return []
    return [
        token for token in _extract_tags_from_text(match.group(1)) if token in DEFAULT_ALLOWED_TYPES
    ]


def _extract_tag_taxonomy(content: str) -> dict[str, list[str]]:
    lines = content.splitlines()
    taxonomy_lines: list[str] = []
    in_taxonomy = False
    for line in lines:
        if TAG_TAXONOMY_HEADING.match(line.strip()):
            in_taxonomy = True
            continue
        if in_taxonomy and LEVEL_TWO_HEADING.match(line.strip()):
            break
        if in_taxonomy:
            taxonomy_lines.append(line)

    taxonomy: dict[str, list[str]] = {}
    current_section = "General"
    in_fence = False
    for raw_line in taxonomy_lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            current_section = stripped[:-1].strip() or current_section
            taxonomy.setdefault(current_section, [])
            continue
        if not stripped.startswith("-"):
            continue

        item = stripped[1:].strip()
        if not item or item.startswith("["):
            continue
        values = item
        if ":" in item:
            raw_section, values = item.split(":", 1)
            current_section = raw_section.strip().strip("`") or current_section
        tags = _extract_tags_from_text(values)
        if not tags:
            continue
        section_tags = taxonomy.setdefault(current_section, [])
        for tag in tags:
            if tag not in section_tags:
                section_tags.append(tag)

    return {section: sorted(tags) for section, tags in taxonomy.items() if tags}


def _extract_tags_from_text(text: str) -> list[str]:
    code_tags = [tag for tag in re.findall(r"`([^`]+)`", text) if TAG_PATTERN.match(tag)]
    if code_tags:
        return code_tags

    candidates = [part.strip().strip("`.;") for part in text.split(",")]
    if len(candidates) == 1:
        single = candidates[0]
        return [single] if TAG_PATTERN.match(single) else []
    return [candidate for candidate in candidates if TAG_PATTERN.match(candidate)]
