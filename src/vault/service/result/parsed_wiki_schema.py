from pydantic import Field

from common.model import FrozenModel


class ParsedWikiSchema(FrozenModel):
    schema_parse_ok: bool
    allowed_types: list[str]
    required_synthesized_frontmatter: list[str]
    required_raw_frontmatter: list[str]
    tag_taxonomy: dict[str, list[str]] = Field(default_factory=dict)
    allowed_tags: list[str] = Field(default_factory=list)
