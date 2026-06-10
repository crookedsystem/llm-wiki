from pydantic import ConfigDict, Field

from common.model import FrozenModel
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema
from vault.service.result.schema_validation_result import IssueSeverity


class WikiContextSummary(FrozenModel):
    total_notes: int
    synthesized_pages: int
    raw_sources: int
    last_log_entries: int


class WikiContextHealth(FrozenModel):
    schema_parse_ok: bool
    unknown_tag_count: int
    missing_frontmatter_count: int


class WikiPageContext(FrozenModel):
    path: str
    title: str
    page_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    outbound_links: list[str] = Field(default_factory=list)
    inbound_links: list[str] = Field(default_factory=list)
    indexed: bool = False


class WikiContextMap(FrozenModel):
    pages: list[WikiPageContext] = Field(default_factory=list)
    pages_by_type: dict[str, list[str]] = Field(default_factory=dict)
    raw_sources: list[str] = Field(default_factory=list)
    link_graph: dict[str, list[str]] = Field(default_factory=dict)


class WikiContextIssueCandidate(FrozenModel):
    code: str
    path: str
    message: str
    severity: IssueSeverity = "warning"
    related_paths: list[str] = Field(default_factory=list)


class WikiUpdateSuggestion(FrozenModel):
    action: str
    path: str
    reason: str
    related_paths: list[str] = Field(default_factory=list)


class WikiPageDraft(FrozenModel):
    path: str
    title: str
    page_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    body: str = ""


class WikiContext(FrozenModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, populate_by_name=True)

    schema_text: str = Field(alias="schema")
    index: str
    recent_log: str
    parsed_schema: ParsedWikiSchema
    summary: WikiContextSummary
    health: WikiContextHealth
    wiki_map: WikiContextMap = Field(default_factory=WikiContextMap)
    entities: list[WikiPageContext] = Field(default_factory=list)
    issue_candidates: list[WikiContextIssueCandidate] = Field(default_factory=list)
    update_suggestions: list[WikiUpdateSuggestion] = Field(default_factory=list)
