import re
from typing import Final

SYNTHESIZED_TYPE_BY_DIR: Final[dict[str, set[str]]] = {
    "entities": {"entity"},
    "concepts": {"concept", "summary"},
    "comparisons": {"comparison"},
    "queries": {"query", "summary"},
}
SYNTHESIZED_DIRS: Final = frozenset(SYNTHESIZED_TYPE_BY_DIR)
META_NOTE_PATHS: Final = frozenset({"index.md", "log.md"})
REQUIRED_SYNTH_FIELDS: Final = (
    "title",
    "created",
    "updated",
    "type",
    "tags",
    "sources",
    "confidence",
    "contested",
)
REQUIRED_RAW_FIELDS: Final = ("ingested", "sha256")
DEFAULT_ALLOWED_TYPES: Final = ("entity", "concept", "comparison", "query", "summary")
DATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TAG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TAG_TAXONOMY_HEADING: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Tag taxonomy\s*$",
    re.IGNORECASE,
)
LEVEL_TWO_HEADING: Final[re.Pattern[str]] = re.compile(r"^##\s+")
WIKILINK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<!!)\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]"
)
