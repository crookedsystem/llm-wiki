from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LINK_CONTEXT_KEYS = ("orientation", "broken_links", "link_targets", "suggested_links")


def is_link_context_payload(payload: Mapping[str, Any]) -> bool:
    return any(isinstance(payload.get(key), list) for key in LINK_CONTEXT_KEYS)
