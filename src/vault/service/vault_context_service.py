from collections.abc import Iterable

from common.model import FrozenModel
from vault.service.command.context_command import ContextCommand, ContextMode
from vault.service.command.search_notes_command import SearchNotesCommand
from vault.service.result.context_result import (
    ContextNote,
    ContextResult,
    ContextSection,
    EntityGuidance,
)
from vault.service.result.search_notes_result import NoteSearchResult
from vault.service.vault_search_service import VaultSearchService


class _SectionSpec(FrozenModel):
    name: str
    purpose: str
    query_terms: tuple[str, ...]
    quota: int
    path_prefix: str | None = None
    explicit_paths: tuple[str, ...] = ()


_SECTION_SPECS_BY_MODE: dict[ContextMode, tuple[_SectionSpec, ...]] = {
    "prompt": (
        _SectionSpec(
            name="orientation",
            purpose="Vault schema, index, and recent log orientation before answering or coding.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        _SectionSpec(
            name="entity_candidates",
            purpose="Existing entity anchors that may own or scope the requested knowledge.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=3,
            path_prefix="entities",
        ),
        _SectionSpec(
            name="project_context",
            purpose="Project or repository context that should constrain the answer.",
            query_terms=("project-context", "repository", "service"),
            quota=3,
        ),
        _SectionSpec(
            name="code_conventions",
            purpose="Code conventions and development style that should guide implementation.",
            query_terms=("code-style", "naming-convention", "development style", "maintainability"),
            quota=3,
        ),
        _SectionSpec(
            name="domain_rules",
            purpose="Domain rules and architecture constraints related to the request.",
            query_terms=("domain-rule", "domain rules", "architecture", "module"),
            quota=3,
        ),
        _SectionSpec(
            name="direct_matches",
            purpose="Highest scoring direct matches for the original prompt.",
            query_terms=(),
            quota=50,
        ),
    ),
    "prewrite": (
        _SectionSpec(
            name="orientation",
            purpose="Schema/index/log pages needed before writing durable wiki knowledge.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        _SectionSpec(
            name="entity_candidates",
            purpose="Existing entity pages to update or link before creating new entities.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=4,
            path_prefix="entities",
        ),
        _SectionSpec(
            name="direct_matches",
            purpose="Potential duplicate or related pages for the knowledge being written.",
            query_terms=(),
            quota=5,
        ),
        _SectionSpec(
            name="domain_rules",
            purpose="Domain rules that should be linked from the new or updated note.",
            query_terms=("domain-rule", "domain rules", "architecture", "module"),
            quota=3,
        ),
        _SectionSpec(
            name="code_conventions",
            purpose="Code conventions and development style worth linking when relevant.",
            query_terms=("code-style", "naming-convention", "development style", "maintainability"),
            quota=2,
        ),
    ),
    "stop": (
        _SectionSpec(
            name="orientation",
            purpose="Schema/index/log pages needed for a safe end-of-turn wiki update.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        _SectionSpec(
            name="entity_candidates",
            purpose="Entity anchors that should receive links or updates after this turn.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=4,
            path_prefix="entities",
        ),
        _SectionSpec(
            name="direct_matches",
            purpose="Existing pages likely to absorb this turn's durable knowledge.",
            query_terms=(),
            quota=5,
        ),
        _SectionSpec(
            name="relationship_targets",
            purpose="Related concepts/entities for wikilinks and relationship updates.",
            query_terms=("relationship", "related", "concept", "entity", "open question"),
            quota=3,
        ),
    ),
}

_USAGE_BY_MODE: dict[ContextMode, tuple[str, ...]] = {
    "prompt": (
        "Use this context as orientation before answering or editing code.",
        "Prefer project/entity/domain rule sections over generic direct matches "
        "when they conflict.",
        "Do not update existing notes from snippets alone; fetch full content before writing.",
    ),
    "prewrite": (
        "Use this context to avoid duplicate wiki pages before kb_write_note.",
        "If an entity candidate matches the subject, update/link it instead of creating "
        "a parallel page.",
        "Create an entity only for a named project, service, API, standard, product, "
        "organization, or stable module boundary.",
    ),
    "stop": (
        "Use this context only if the turn produced durable wiki-worthy knowledge.",
        "Prefer updating existing entity/concept/query pages over creating new pages.",
        "Append index/log changes only when a durable wiki write is actually made.",
    ),
}

_ENTITY_GUIDANCE = EntityGuidance(
    criteria=[
        "Create an entity for a named project, repository, service, product, API, "
        "protocol, dataset, standard, organization, person, or stable module boundary.",
        "Do not create an entity for broad ideas, qualities, techniques, or one-off "
        "mentions; use concept, query, or tags instead.",
        "Prefer an entity when the subject can be the stable subject/object of "
        "relationships across multiple notes.",
        "For code work, project/service/module entities should anchor related code "
        "conventions, development style, and domain rules.",
    ],
    preferred_paths=[
        "entities/{project-or-repository}.md",
        "entities/{service-or-api}.md",
        "entities/{stable-module-boundary}.md",
    ],
    prewrite_checks=[
        "prewrite: search entities/ for the exact name, aliases, and repository slug "
        "before creating a new entity.",
        "prewrite: link new concept/query pages to the matching entity when scope is "
        "project-specific.",
        "prewrite: if only a broad practice is involved, create or update a concept page "
        "instead of an entity.",
    ],
)


class VaultContextService(FrozenModel):
    search_service: VaultSearchService

    def context(self, command: ContextCommand) -> ContextResult:
        seen_paths: set[str] = set()
        total_count = 0
        sections: list[ContextSection] = []

        for spec in _SECTION_SPECS_BY_MODE[command.mode]:
            remaining = command.limit - total_count
            if remaining <= 0:
                sections.append(ContextSection(name=spec.name, purpose=spec.purpose, notes=[]))
                continue

            notes = self._section_notes(
                command,
                spec,
                seen_paths=seen_paths,
                limit=min(spec.quota, remaining),
            )
            total_count += len(notes)
            sections.append(ContextSection(name=spec.name, purpose=spec.purpose, notes=notes))

        return ContextResult(
            query=command.query,
            mode=command.mode,
            count=total_count,
            usage=list(_USAGE_BY_MODE[command.mode]),
            entity_guidance=_ENTITY_GUIDANCE,
            sections=sections,
        )

    def _section_notes(
        self,
        command: ContextCommand,
        spec: _SectionSpec,
        *,
        seen_paths: set[str],
        limit: int,
    ) -> list[ContextNote]:
        if spec.explicit_paths:
            return self._explicit_path_notes(command, spec, seen_paths=seen_paths, limit=limit)

        query = _bucket_query(command.query, spec.query_terms)
        path_prefix = command.path_prefix or spec.path_prefix
        result = self.search_service.search_notes(
            SearchNotesCommand(query=query, limit=limit, path_prefix=path_prefix)
        )

        notes: list[ContextNote] = []
        for search_note in result.results:
            if search_note.path in seen_paths:
                continue
            seen_paths.add(search_note.path)
            notes.append(_context_note(search_note, spec))
        return notes

    def _explicit_path_notes(
        self,
        command: ContextCommand,
        spec: _SectionSpec,
        *,
        seen_paths: set[str],
        limit: int,
    ) -> list[ContextNote]:
        query = _bucket_query(command.query, spec.query_terms)
        notes: list[ContextNote] = []
        for path in spec.explicit_paths:
            if len(notes) >= limit:
                break
            result = self.search_service.search_notes(
                SearchNotesCommand(query=query, limit=1, path_prefix=path)
            )
            for search_note in result.results:
                if search_note.path in seen_paths:
                    continue
                seen_paths.add(search_note.path)
                notes.append(_context_note(search_note, spec))
                break
        return notes


def _bucket_query(query: str, query_terms: Iterable[str]) -> str:
    terms = [term for term in query_terms if term]
    if not terms:
        return query
    return f"{query} {' '.join(terms)}"


def _context_note(search_note: NoteSearchResult, spec: _SectionSpec) -> ContextNote:
    return ContextNote(
        path=search_note.path,
        title=search_note.title,
        page_type=search_note.page_type,
        tags=search_note.tags,
        score=search_note.score,
        content_hash=search_note.content_hash,
        matches=search_note.matches,
        why_included=f"{spec.name}: {spec.purpose}",
    )
