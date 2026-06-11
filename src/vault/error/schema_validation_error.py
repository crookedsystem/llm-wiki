import json

from vault.service.result.schema_validation_result import SchemaValidationIssue


class SchemaValidationError(ValueError):
    """Raised when note content violates the vault schema write contract."""

    def __init__(self, issues: list[SchemaValidationIssue]) -> None:
        self.issues = issues
        payload = {
            "code": "schema_validation_failed",
            "message": "Note violates LLM Wiki schema",
            "issues": [issue.model_dump(exclude_none=True) for issue in issues],
        }
        super().__init__(json.dumps(payload, ensure_ascii=False))
