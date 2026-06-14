import re
from typing import Final

QUERY_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[\w가-힣一-龥ぁ-んァ-ン]+",
    re.UNICODE,
)
MAX_SEARCH_LIMIT: Final = 50
SYNTHESIZED_PAGE_DIRS: Final = frozenset({"concepts", "entities", "comparisons", "queries"})
