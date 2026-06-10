from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from yaml.error import YAMLError

from common.model import FrozenModel
from vault.constant.schema import SYNTHESIZED_DIRS, TAG_PATTERN, TAG_TAXONOMY_HEADING
from vault.entity.vault_note import parse_note
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema
from vault.service.result.taxonomy_reconcile_result import TaxonomyReconcileResult
from vault.service.vault_schema_parser import parse_schema_document


class TaxonomyUsageSnapshot(FrozenModel):
    parsed_schema: ParsedWikiSchema
    tag_usage_counts: dict[str, int]
    unknown_tags: list[str]


class TaxonomyReconcileDecisions(FrozenModel):
    add_tags: list[str]
    rename_tags: dict[str, str]
    remove_tags: set[str]


class TaxonomyReconcilePlan(FrozenModel):
    taxonomy_tags_to_add: list[str]
    planned_changes: list[str]
    rename_tags: dict[str, str]
    remove_tags: set[str]


class VaultTaxonomyReconcileService(FrozenModel):
    """SCHEMA.md의 tag taxonomy와 synthesized note의 frontmatter tag를 정합화합니다.

    입력 데이터는 vault 루트의 `SCHEMA.md` Markdown 문서, synthesized note의 YAML
    frontmatter, 그리고 `{"add": [tag], "rename": {old: new}, "remove": [tag]}` 형식의
    사용자 결정입니다. 출력 데이터는 `TaxonomyReconcileResult`이며 dry-run 여부, 아직
    taxonomy에 없는 tag 목록, tag 사용 횟수, 예정 작업, 실제 변경된 파일 경로를 담습니다.
    """

    note_repository: VaultNoteRepository

    def reconcile_taxonomy(
        self,
        *,
        apply: bool = False,
        decisions: dict[str, object] | None = None,
    ) -> TaxonomyReconcileResult:
        """taxonomy 정합화의 전체 흐름을 dry-run 또는 apply 모드로 실행합니다.

        `decisions`는 외부 도구 호출에서 들어오는 원시 dict이며, 이 메서드는 tag 형식을
        검증한 뒤 계획 데이터로 바꿉니다. `apply=False`이면 파일을 쓰지 않고 현재 unknown
        tag와 예정 작업만 반환하고, `apply=True`이면 SCHEMA.md와 synthesized note를 갱신한
        뒤 다시 계산한 tag 사용 현황을 반환합니다.
        """
        current_taxonomy = self._snapshot_current_taxonomy_usage()
        taxonomy_decisions = self._normalize_user_taxonomy_decisions(decisions or {})
        reconcile_plan = self._plan_taxonomy_reconcile_changes(
            current_taxonomy,
            taxonomy_decisions,
        )
        changed_files: list[str] = []

        if apply:
            changed_files = self._apply_taxonomy_reconcile_plan(reconcile_plan)
            current_taxonomy = self._snapshot_current_taxonomy_usage()

        return self._build_reconcile_result(
            apply=apply,
            current_taxonomy=current_taxonomy,
            reconcile_plan=reconcile_plan,
            changed_files=changed_files,
        )

    def _snapshot_current_taxonomy_usage(self) -> TaxonomyUsageSnapshot:
        """현재 vault 기준으로 schema와 synthesized note의 tag 사용량을 함께 읽습니다.

        입력은 파일 시스템에 있는 `SCHEMA.md`와 synthesized note들의 Markdown 본문입니다.
        출력은 파싱된 schema, `{tag: 사용 횟수}` dict, schema에 등록되지 않은 tag list입니다.
        """
        schema = self._parse_current_schema()
        tag_usage_counts = self._count_synthesized_note_tags()
        unknown_tags = sorted(tag for tag in tag_usage_counts if tag not in schema.allowed_tags)
        return TaxonomyUsageSnapshot(
            parsed_schema=schema,
            tag_usage_counts=tag_usage_counts,
            unknown_tags=unknown_tags,
        )

    def _normalize_user_taxonomy_decisions(
        self,
        decisions: dict[str, object],
    ) -> TaxonomyReconcileDecisions:
        """외부 입력 dict를 reconcile에서 사용할 수 있는 결정 데이터로 정제합니다.

        입력 형식은 `add: list[str]`, `rename: dict[str, str]`, `remove: list[str]`입니다.
        출력은 유효한 tag만 남긴 add/rename/remove 데이터이며, add와 rename의 새 tag는
        `TAG_PATTERN`을 통과한 값만 사용합니다.
        """
        add_tags = sorted(
            tag
            for tag in _string_list_from_decision(decisions.get("add"))
            if TAG_PATTERN.match(tag)
        )
        rename_tags = {
            old_tag: new_tag
            for old_tag, new_tag in _string_mapping_from_decision(decisions.get("rename")).items()
            if TAG_PATTERN.match(new_tag)
        }
        remove_tags = set(_string_list_from_decision(decisions.get("remove")))
        return TaxonomyReconcileDecisions(
            add_tags=add_tags,
            rename_tags=rename_tags,
            remove_tags=remove_tags,
        )

    def _plan_taxonomy_reconcile_changes(
        self,
        current_taxonomy: TaxonomyUsageSnapshot,
        taxonomy_decisions: TaxonomyReconcileDecisions,
    ) -> TaxonomyReconcilePlan:
        """정제된 사용자 결정을 실제 파일 변경 계획으로 변환합니다.

        입력은 현재 schema의 allowed tag 목록과 사용자가 선택한 add/rename/remove 결정입니다.
        출력은 SCHEMA.md에 새로 추가할 tag 목록과 사람이 읽을 수 있는 예정 작업 문자열입니다.
        """
        taxonomy_tags_to_add = sorted(
            {
                tag
                for tag in [
                    *taxonomy_decisions.add_tags,
                    *self._rename_targets_for_used_tags(
                        current_taxonomy,
                        taxonomy_decisions,
                    ),
                ]
                if tag not in current_taxonomy.parsed_schema.allowed_tags
            }
        )
        planned_changes = self._describe_taxonomy_reconcile_changes(
            taxonomy_tags_to_add,
            taxonomy_decisions,
        )
        return TaxonomyReconcilePlan(
            taxonomy_tags_to_add=taxonomy_tags_to_add,
            planned_changes=planned_changes,
            rename_tags=taxonomy_decisions.rename_tags,
            remove_tags=taxonomy_decisions.remove_tags,
        )

    def _rename_targets_for_used_tags(
        self,
        current_taxonomy: TaxonomyUsageSnapshot,
        taxonomy_decisions: TaxonomyReconcileDecisions,
    ) -> list[str]:
        """실제로 사용 중인 tag의 rename 대상만 schema 추가 후보로 반환합니다."""
        return [
            new_tag
            for old_tag, new_tag in taxonomy_decisions.rename_tags.items()
            if old_tag in current_taxonomy.tag_usage_counts
        ]

    def _describe_taxonomy_reconcile_changes(
        self,
        taxonomy_tags_to_add: list[str],
        taxonomy_decisions: TaxonomyReconcileDecisions,
    ) -> list[str]:
        """작업 계획을 MCP 응답에 담을 문자열 목록으로 만듭니다.

        출력 형식은 기존 계약과 동일하게 `add taxonomy tag: tag`, `rename tag: old -> new`,
        `remove tag: tag` 문자열 list입니다.
        """
        planned_changes: list[str] = []
        for tag in taxonomy_tags_to_add:
            planned_changes.append(f"add taxonomy tag: {tag}")
        for old_tag, new_tag in sorted(taxonomy_decisions.rename_tags.items()):
            planned_changes.append(f"rename tag: {old_tag} -> {new_tag}")
        for tag in sorted(taxonomy_decisions.remove_tags):
            planned_changes.append(f"remove tag: {tag}")
        return planned_changes

    def _apply_taxonomy_reconcile_plan(
        self,
        reconcile_plan: TaxonomyReconcilePlan,
    ) -> list[str]:
        """파일 시스템에 taxonomy 정합화 계획을 적용하고 변경 파일 경로를 반환합니다.

        입력은 SCHEMA.md 추가 tag, rename mapping, remove set이 들어 있는 계획 데이터입니다.
        출력은 vault 기준 상대 경로 list이며, schema 변경은 `SCHEMA.md`, note 변경은
        `concepts/name.md` 같은 Markdown 경로로 반환합니다.
        """
        changed_files: list[str] = []
        if self._add_missing_taxonomy_tags_to_schema(reconcile_plan.taxonomy_tags_to_add):
            changed_files.append("SCHEMA.md")
        changed_files.extend(
            self._rewrite_synthesized_note_frontmatter_tags(
                reconcile_plan.rename_tags,
                reconcile_plan.remove_tags,
            )
        )
        return changed_files

    def _add_missing_taxonomy_tags_to_schema(self, taxonomy_tags_to_add: list[str]) -> bool:
        """SCHEMA.md의 Tag taxonomy 섹션에 새 tag를 추가합니다.

        입력은 이미 schema에 없는 것으로 판정된 tag list입니다. 출력은 실제 파일 내용이
        바뀌었는지 나타내는 bool이며, 유효한 tag가 없으면 파일을 쓰지 않고 `False`를 반환합니다.
        """
        if not taxonomy_tags_to_add:
            return False
        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        if not schema_path.exists():
            return False
        content = schema_path.read_text(encoding="utf-8")
        rewritten = _schema_content_with_added_taxonomy_tags(content, taxonomy_tags_to_add)
        if rewritten == content:
            return False
        schema_path.write_text(rewritten, encoding="utf-8")
        return True

    def _rewrite_synthesized_note_frontmatter_tags(
        self,
        rename_tags: dict[str, str],
        remove_tags: set[str],
    ) -> list[str]:
        """synthesized note의 frontmatter tags를 rename/remove 결정에 맞게 갱신합니다.

        입력은 `{기존 tag: 새 tag}` rename dict와 제거할 tag set입니다. 출력은 실제로
        frontmatter가 바뀐 Markdown note의 vault 상대 경로 list입니다.
        """
        changed_files: list[str] = []
        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if not _is_synthesized_path(relative_path):
                continue
            content = path.read_text(encoding="utf-8")
            rewritten = _content_with_reconciled_frontmatter_tags(
                content,
                rename_tags,
                remove_tags,
            )
            if rewritten == content:
                continue
            path.write_text(rewritten, encoding="utf-8")
            changed_files.append(relative_path)
        return changed_files

    def _build_reconcile_result(
        self,
        *,
        apply: bool,
        current_taxonomy: TaxonomyUsageSnapshot,
        reconcile_plan: TaxonomyReconcilePlan,
        changed_files: list[str],
    ) -> TaxonomyReconcileResult:
        """계산된 taxonomy 상태와 적용 결과를 MCP 응답 모델로 변환합니다.

        dry-run 응답의 `unknown_tags`는 현재 schema 기준 미등록 tag이고, apply 응답의
        `unknown_tags`는 파일 변경 후에도 schema에 남아 있는 미해결 tag입니다.
        """
        unresolved_unknown_tags = sorted(
            tag
            for tag in current_taxonomy.tag_usage_counts
            if tag not in current_taxonomy.parsed_schema.allowed_tags
        )
        return TaxonomyReconcileResult(
            dry_run=not apply,
            unknown_tags=current_taxonomy.unknown_tags if not apply else unresolved_unknown_tags,
            tag_usage_counts=current_taxonomy.tag_usage_counts,
            planned_changes=reconcile_plan.planned_changes,
            changed_files=changed_files,
        )

    def _parse_current_schema(self) -> ParsedWikiSchema:
        """SCHEMA.md Markdown 문자열을 파싱해 허용 type/tag 정보를 반환합니다."""
        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        if not schema_path.exists():
            return parse_schema_document("")
        return parse_schema_document(schema_path.read_text(encoding="utf-8"))

    def _count_synthesized_note_tags(self) -> dict[str, int]:
        """synthesized note frontmatter의 tags 필드를 `{tag: 사용 횟수}`로 집계합니다."""
        tag_usage_counts: dict[str, int] = {}
        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if not _is_synthesized_path(relative_path):
                continue
            frontmatter, _body = _read_frontmatter_mapping(path.read_text(encoding="utf-8"))
            if frontmatter is None:
                continue
            tags = _frontmatter_string_list(frontmatter.get("tags")) or []
            for tag in tags:
                tag_usage_counts[tag] = tag_usage_counts.get(tag, 0) + 1
        return dict(sorted(tag_usage_counts.items()))


def _string_list_from_decision(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_mapping_from_decision(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, mapped_value in value.items():
        if isinstance(key, str) and isinstance(mapped_value, str):
            result[key] = mapped_value
    return result


def _schema_content_with_added_taxonomy_tags(content: str, tags: list[str]) -> str:
    tags_to_add = [tag for tag in tags if TAG_PATTERN.match(tag)]
    if not tags_to_add:
        return content
    addition = f"- Added: {', '.join(tags_to_add)}"
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if TAG_TAXONOMY_HEADING.match(line.strip()):
            insert_at = index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines.insert(insert_at, addition)
            return "\n".join(lines) + "\n"
    return f"{content.rstrip()}\n\n## Tag taxonomy\n{addition}\n"


def _content_with_reconciled_frontmatter_tags(
    content: str,
    rename_tags: dict[str, str],
    remove_tags: set[str],
) -> str:
    """Markdown 본문에서 YAML frontmatter의 tags 필드만 정합화해 반환합니다.

    입력은 전체 Markdown 문자열과 rename/remove 결정입니다. 출력은 같은 Markdown 문자열
    형식이며, frontmatter가 없거나 YAML이 유효하지 않으면 원문을 그대로 반환합니다.
    """
    if not rename_tags and not remove_tags:
        return content
    frontmatter, body = _read_frontmatter_mapping(content)
    if frontmatter is None:
        return content
    tags = _frontmatter_string_list(frontmatter.get("tags"))
    if tags is None:
        return content
    rewritten_tags: list[str] = []
    for tag in tags:
        rewritten = rename_tags.get(tag, tag)
        if rewritten in remove_tags:
            continue
        if rewritten not in rewritten_tags:
            rewritten_tags.append(rewritten)
    if rewritten_tags == tags:
        return content
    frontmatter["tags"] = rewritten_tags
    dumped_frontmatter = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{dumped_frontmatter}---\n{body}"


def _read_frontmatter_mapping(content: str) -> tuple[dict[str, Any] | None, str]:
    parsed = parse_note(content)
    if parsed.frontmatter is None:
        return None, parsed.body
    try:
        loaded = yaml.safe_load(parsed.frontmatter) or {}
    except YAMLError:
        return None, parsed.body
    if not isinstance(loaded, dict):
        return None, parsed.body
    return cast(dict[str, Any], loaded), parsed.body


def _frontmatter_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def _is_synthesized_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] in SYNTHESIZED_DIRS
