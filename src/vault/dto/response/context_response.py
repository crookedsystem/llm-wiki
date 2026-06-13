from typing_extensions import TypedDict

from vault.service.result.context_result import (
    BrokenWikiLink,
    ContextReference,
    ContextResult,
    EntityGuidance,
    SuggestedLink,
)


class ContextReferenceResponse(TypedDict):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    content_hash: str
    relation: str
    followup_search: str


class BrokenWikiLinkResponse(TypedDict):
    source_path: str
    source_content_hash: str
    target: str
    normalized_target: str
    occurrences: int
    suggested_path: str
    followup_search: str


class SuggestedLinkResponse(TypedDict):
    source_path: str
    source_content_hash: str
    target_path: str
    target_title: str | None
    relation: str
    reason: str
    followup_search: str


class EntityGuidanceResponse(TypedDict):
    criteria: list[str]
    preferred_paths: list[str]
    prewrite_checks: list[str]


class ContextResponse(TypedDict):
    query: str
    mode: str
    count: int
    usage: list[str]
    entity_guidance: EntityGuidanceResponse
    orientation: list[ContextReferenceResponse]
    broken_links: list[BrokenWikiLinkResponse]
    link_targets: list[ContextReferenceResponse]
    suggested_links: list[SuggestedLinkResponse]


class ContextResponseMapper:
    @staticmethod
    def to_response(result: ContextResult) -> ContextResponse:
        return {
            "query": result.query,
            "mode": result.mode,
            "count": result.count,
            "usage": result.usage,
            "entity_guidance": ContextResponseMapper._entity_guidance_response(
                result.entity_guidance
            ),
            "orientation": [
                ContextResponseMapper._context_reference_response(reference)
                for reference in result.orientation
            ],
            "broken_links": [
                ContextResponseMapper._broken_wiki_link_response(link)
                for link in result.broken_links
            ],
            "link_targets": [
                ContextResponseMapper._context_reference_response(reference)
                for reference in result.link_targets
            ],
            "suggested_links": [
                ContextResponseMapper._suggested_link_response(link)
                for link in result.suggested_links
            ],
        }

    @staticmethod
    def _context_reference_response(reference: ContextReference) -> ContextReferenceResponse:
        return {
            "path": reference.path,
            "title": reference.title,
            "page_type": reference.page_type,
            "tags": reference.tags,
            "content_hash": reference.content_hash,
            "relation": reference.relation,
            "followup_search": reference.followup_search,
        }

    @staticmethod
    def _broken_wiki_link_response(link: BrokenWikiLink) -> BrokenWikiLinkResponse:
        return {
            "source_path": link.source_path,
            "source_content_hash": link.source_content_hash,
            "target": link.target,
            "normalized_target": link.normalized_target,
            "occurrences": link.occurrences,
            "suggested_path": link.suggested_path,
            "followup_search": link.followup_search,
        }

    @staticmethod
    def _suggested_link_response(link: SuggestedLink) -> SuggestedLinkResponse:
        return {
            "source_path": link.source_path,
            "source_content_hash": link.source_content_hash,
            "target_path": link.target_path,
            "target_title": link.target_title,
            "relation": link.relation,
            "reason": link.reason,
            "followup_search": link.followup_search,
        }

    @staticmethod
    def _entity_guidance_response(guidance: EntityGuidance) -> EntityGuidanceResponse:
        return {
            "criteria": guidance.criteria,
            "preferred_paths": guidance.preferred_paths,
            "prewrite_checks": guidance.prewrite_checks,
        }
