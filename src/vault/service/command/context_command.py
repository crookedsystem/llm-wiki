from typing import Literal, TypeAlias

from pydantic import field_validator

from common.model import FrozenModel
from vault.constant.search import MAX_SEARCH_LIMIT

ContextMode: TypeAlias = Literal["prompt", "prewrite", "stop"]


class ContextCommand(FrozenModel):
    query: str
    mode: ContextMode = "prompt"
    limit: int = 16
    path_prefix: str | None = None

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be empty")
        return normalized

    @field_validator("limit")
    @classmethod
    def _validate_limit(cls, value: int) -> int:
        if not 1 <= value <= MAX_SEARCH_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")
        return value
