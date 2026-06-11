from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml
from yaml.error import YAMLError

from common.model import FrozenModel
from vault.constant.schema import (
    DATE_PATTERN,
    META_NOTE_PATHS,
    REQUIRED_RAW_FIELDS,
    REQUIRED_SYNTH_FIELDS,
    SYNTHESIZED_DIRS,
    SYNTHESIZED_TYPE_BY_DIR,
)
from vault.entity.vault_note import compute_sha256, parse_note
from vault.error.schema_validation_error import SchemaValidationError
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema
from vault.service.result.schema_validation_result import (
    SchemaValidationIssue,
    ValidationSummary,
    VaultValidationResult,
)
from vault.service.vault_schema_parser import parse_schema_document


class VaultSchemaService(FrozenModel):
    note_repository: VaultNoteRepository

    def validate_write(self, note_path: str, content: str) -> VaultValidationResult:
        issues = self._validate_write_issues(note_path, content)
        return _validation_result(issues)

    def ensure_valid_write(self, note_path: str, content: str) -> None:
        result = self.validate_write(note_path, content)
        if result.issues:
            raise SchemaValidationError(result.issues)

    def validate_vault(self, *, include_raw: bool = True) -> VaultValidationResult:
        issues: list[SchemaValidationIssue] = []
        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        if schema_path.exists():
            issues.extend(self._validate_schema_note(schema_path.read_text(encoding="utf-8")))
        else:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing",
                    path="SCHEMA.md",
                    field="SCHEMA.md",
                    message="Vault schema file is required before validating wiki pages",
                )
            )

        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if relative_path == "SCHEMA.md" or _is_meta_note_path(relative_path):
                continue
            if _is_raw_path(relative_path):
                if include_raw:
                    issues.extend(
                        self._validate_raw_note(relative_path, path.read_text(encoding="utf-8"))
                    )
                continue
            if _is_synthesized_path(relative_path):
                issues.extend(
                    self._validate_synthesized_note(
                        relative_path,
                        path.read_text(encoding="utf-8"),
                        self._parsed_schema(),
                    )
                )
                continue
            issues.append(
                SchemaValidationIssue(
                    code="unsupported_note_path",
                    path=relative_path,
                    field="note_path",
                    value=relative_path,
                    message=(
                        "Note path must be SCHEMA.md, index.md, log.md, raw/**, "
                        "entities/**, concepts/**, comparisons/**, queries/**, or _meta/**"
                    ),
                )
            )
        return _validation_result(issues)

    def _validate_write_issues(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        if note_path == "SCHEMA.md":
            return self._validate_schema_note(content)
        if _is_meta_note_path(note_path):
            return []
        if _is_raw_path(note_path):
            return self._validate_raw_note(note_path, content)
        if _is_synthesized_path(note_path):
            schema_issues = self._schema_write_blocking_issues()
            if schema_issues:
                return schema_issues
            return self._validate_synthesized_note(note_path, content, self._parsed_schema())
        if note_path.startswith("_meta/"):
            return []
        return [
            SchemaValidationIssue(
                code="unsupported_note_path",
                path=note_path,
                field="note_path",
                value=note_path,
                message=(
                    "Note path must be SCHEMA.md, index.md, log.md, raw/**, entities/**, "
                    "concepts/**, comparisons/**, queries/**, or _meta/**"
                ),
            )
        ]

    def _validate_schema_note(self, content: str) -> list[SchemaValidationIssue]:
        parsed = parse_schema_document(content)
        issues: list[SchemaValidationIssue] = []
        if "## Frontmatter" not in content:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_frontmatter_section",
                    path="SCHEMA.md",
                    field="Frontmatter",
                    message="SCHEMA.md must define the synthesized page frontmatter contract",
                )
            )
        if not parsed.tag_taxonomy:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_tag_taxonomy",
                    path="SCHEMA.md",
                    field="Tag taxonomy",
                    message="SCHEMA.md must define a Tag taxonomy section before tags are used",
                )
            )
        return issues

    def _schema_write_blocking_issues(self) -> list[SchemaValidationIssue]:
        schema_text = self._read_optional_note("SCHEMA.md")
        if not schema_text:
            return [
                SchemaValidationIssue(
                    code="schema_missing",
                    path="SCHEMA.md",
                    field="SCHEMA.md",
                    message="Vault schema file is required before validating wiki pages",
                )
            ]
        return self._validate_schema_note(schema_text)

    def _validate_synthesized_note(
        self,
        note_path: str,
        content: str,
        schema: ParsedWikiSchema,
    ) -> list[SchemaValidationIssue]:
        frontmatter, _body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in REQUIRED_SYNTH_FIELDS:
            if field_name not in frontmatter:
                issues.append(
                    SchemaValidationIssue(
                        code="missing_required_field",
                        path=note_path,
                        field=field_name,
                        message=f"Synthesized pages must include frontmatter field: {field_name}",
                    )
                )

        title = _title_string(frontmatter.get("title"))
        if "title" in frontmatter and title is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="title",
                    message="title must be a YAML scalar",
                )
            )
        elif title == "":
            issues.append(
                SchemaValidationIssue(
                    code="invalid_title",
                    path=note_path,
                    field="title",
                    message="title must not be blank",
                )
            )

        page_type = _scalar_string(frontmatter.get("type"))
        if "type" in frontmatter and page_type is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="type",
                    message="type must be a YAML string",
                )
            )
        elif page_type is not None:
            if page_type not in schema.allowed_types:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message="Page type is not declared by SCHEMA.md allowed type values",
                    )
                )
            allowed_types_for_path = _allowed_types_for_path(note_path)
            if allowed_types_for_path and page_type not in allowed_types_for_path:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type_for_path",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message=(
                            f"Path {note_path} only allows type values: "
                            f"{', '.join(sorted(allowed_types_for_path))}"
                        ),
                    )
                )

        for field_name in ("created", "updated"):
            date_value = _date_string(frontmatter.get(field_name))
            if field_name in frontmatter and (
                date_value is None or not DATE_PATTERN.match(date_value)
            ):
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_date",
                        path=note_path,
                        field=field_name,
                        value=str(frontmatter.get(field_name)),
                        message=f"{field_name} must use YYYY-MM-DD format",
                    )
                )

        tags = _frontmatter_list(frontmatter.get("tags"))
        if "tags" in frontmatter and tags is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="tags",
                    message="tags must be a YAML list",
                )
            )
        for tag in tags or []:
            if tag not in schema.allowed_tags:
                issues.append(
                    SchemaValidationIssue(
                        code="unknown_tag",
                        path=note_path,
                        field="tags",
                        value=tag,
                        message="Tag is not declared in SCHEMA.md taxonomy",
                    )
                )

        sources = _frontmatter_list(frontmatter.get("sources"))
        if "sources" in frontmatter and sources is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="sources",
                    message="sources must be a YAML list",
                )
            )
        elif sources is not None and not _nonblank_strings(sources):
            issues.append(
                SchemaValidationIssue(
                    code="empty_sources",
                    path=note_path,
                    field="sources",
                    message="sources must include at least one raw note path or source URL",
                )
            )

        confidence = _scalar_string(frontmatter.get("confidence"))
        if "confidence" in frontmatter and confidence is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="confidence",
                    message="confidence must be a YAML string",
                )
            )
        elif confidence is not None and confidence not in {"high", "medium", "low"}:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_confidence",
                    path=note_path,
                    field="confidence",
                    value=confidence,
                    message="confidence must be one of: high, medium, low",
                )
            )
        contested = frontmatter.get("contested")
        if "contested" in frontmatter and not isinstance(contested, bool):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_contested",
                    path=note_path,
                    field="contested",
                    value=str(contested),
                    message="contested must be a YAML boolean",
                )
            )
        return issues

    def _validate_raw_note(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        frontmatter, body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in REQUIRED_RAW_FIELDS:
            if field_name not in frontmatter:
                code = f"raw_missing_{field_name}"
                issues.append(
                    SchemaValidationIssue(
                        code=code,
                        path=note_path,
                        field=field_name,
                        message=f"Raw notes must include frontmatter field: {field_name}",
                    )
                )

        source_url = _scalar_string(frontmatter.get("source_url"))
        if "source_url" in frontmatter and source_url is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="source_url",
                    message="source_url must be a YAML string",
                )
            )

        source_urls = _frontmatter_list(frontmatter.get("source_urls"))
        if "source_urls" in frontmatter and source_urls is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="source_urls",
                    message="source_urls must be a YAML list of strings",
                )
            )

        ingested = _date_string(frontmatter.get("ingested"))
        if "ingested" in frontmatter and (ingested is None or not DATE_PATTERN.match(ingested)):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_ingested_date",
                    path=note_path,
                    field="ingested",
                    value=str(frontmatter.get("ingested")),
                    message="ingested must use YYYY-MM-DD format",
                )
            )

        if not body.strip():
            issues.append(
                SchemaValidationIssue(
                    code="raw_empty_body",
                    path=note_path,
                    field="body",
                    message="Raw note body must not be empty",
                )
            )

        expected_hash = _scalar_string(frontmatter.get("sha256"))
        if "sha256" in frontmatter and expected_hash is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="sha256",
                    message="sha256 must be a YAML string",
                )
            )
        elif expected_hash is not None:
            actual_hash = compute_sha256(body)
            if expected_hash != actual_hash:
                issues.append(
                    SchemaValidationIssue(
                        code="raw_sha256_mismatch",
                        path=note_path,
                        field="sha256",
                        value=expected_hash,
                        message="raw sha256 must equal SHA-256 of the body after frontmatter",
                    )
                )
        return issues

    def _parsed_schema(self) -> ParsedWikiSchema:
        return parse_schema_document(self._read_optional_note("SCHEMA.md"))

    def _read_optional_note(self, relative_path: str) -> str:
        path = self.note_repository.vault_root / relative_path
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")


def _frontmatter_mapping(
    note_path: str,
    content: str,
) -> tuple[dict[str, Any] | None, str, list[SchemaValidationIssue]]:
    parsed = parse_note(content)
    if parsed.frontmatter is None:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="missing_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="Markdown note must start with YAML frontmatter delimited by ---",
                )
            ],
        )
    try:
        loaded = yaml.safe_load(parsed.frontmatter) or {}
    except YAMLError as error:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message=f"YAML frontmatter could not be parsed: {error}",
                )
            ],
        )
    if not isinstance(loaded, dict):
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="YAML frontmatter must be a mapping/object",
                )
            ],
        )
    return cast(dict[str, Any], loaded), parsed.body, []


def _validation_result(issues: list[SchemaValidationIssue]) -> VaultValidationResult:
    return VaultValidationResult(
        issues=issues,
        summary=ValidationSummary(
            missing_frontmatter=_count_code(issues, "missing_frontmatter"),
            missing_required_fields=_count_code(issues, "missing_required_field"),
            unknown_tags=_count_code(issues, "unknown_tag"),
            invalid_type_for_path=_count_code(issues, "invalid_type_for_path"),
            raw_missing_sha256=_count_code(issues, "raw_missing_sha256"),
            raw_sha256_mismatch=_count_code(issues, "raw_sha256_mismatch"),
            empty_sources=_count_code(issues, "empty_sources"),
            issue_count=len(issues),
        ),
    )


def _count_code(issues: list[SchemaValidationIssue], code: str) -> int:
    return sum(1 for issue in issues if issue.code == code)


def _allowed_types_for_path(note_path: str) -> set[str]:
    first_part = Path(note_path).parts[0]
    return SYNTHESIZED_TYPE_BY_DIR.get(first_part, set())


def _is_synthesized_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] in SYNTHESIZED_DIRS


def _is_raw_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] == "raw"


def _is_meta_note_path(note_path: str) -> bool:
    return note_path in META_NOTE_PATHS or note_path.startswith("_meta/")


def _scalar_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _title_string(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool | int | float | date):
        return str(value)
    return None


def _date_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    return None


def _frontmatter_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def _nonblank_strings(values: list[str]) -> list[str]:
    return [value for value in values if value.strip()]
