from typing import Literal

from pydantic import Field

from common.model import FrozenModel

IssueSeverity = Literal["error", "warning"]


class SchemaValidationIssue(FrozenModel):
    code: str
    path: str
    message: str
    severity: IssueSeverity = "error"
    field: str | None = None
    value: str | None = None


class ValidationSummary(FrozenModel):
    missing_frontmatter: int = 0
    missing_required_fields: int = 0
    unknown_tags: int = 0
    invalid_type_for_path: int = 0
    raw_missing_sha256: int = 0
    raw_sha256_mismatch: int = 0
    empty_sources: int = 0
    issue_count: int = 0


class VaultValidationResult(FrozenModel):
    issues: list[SchemaValidationIssue] = Field(default_factory=list)
    summary: ValidationSummary = Field(default_factory=ValidationSummary)
