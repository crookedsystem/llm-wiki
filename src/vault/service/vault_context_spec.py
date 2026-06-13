from vault.service.command.context_command import ContextMode
from vault.service.result.context_result import EntityGuidance

ORIENTATION_PATHS = ("SCHEMA.md", "index.md", "log.md")

USAGE_BY_MODE: dict[ContextMode, tuple[str, ...]] = {
    "prompt": (
        "Use kb_context as a link/navigation map, not as evidence text.",
        "Use broken_links, link_targets, and suggested_links to decide what wiki pages to "
        "connect or inspect.",
        "When connection evidence is needed, run kb_search_notes with followup_search before "
        "editing notes.",
    ),
    "prewrite": (
        "Use kb_context before kb_write_note to pick an existing target or repair a broken link.",
        "Prefer updating/linking existing link_targets over creating a parallel page.",
        "Run kb_search_notes with followup_search when you need textual evidence for the link.",
    ),
    "stop": (
        "Use kb_context only if the turn produced durable wiki-worthy knowledge.",
        "Prioritize repairing broken_links and adding suggested_links over creating new pages.",
        "Fetch or search for evidence before writing; kb_context intentionally omits snippets.",
    ),
}

ENTITY_GUIDANCE = EntityGuidance(
    criteria=[
        "Treat entities as stable link anchors: named projects, repositories, services, "
        "products, APIs, standards, organizations, people, or module boundaries.",
        "Do not create an entity for broad ideas, qualities, techniques, or one-off mentions; "
        "use concept/query pages or tags instead.",
        "Prefer a link target when the subject can be reused as a relationship subject/object "
        "across multiple notes.",
        "For code work, project/service/module entities should anchor related code conventions, "
        "development style, and domain rules.",
    ],
    preferred_paths=[
        "entities/{project-or-repository}.md",
        "entities/{service-or-api}.md",
        "entities/{stable-module-boundary}.md",
    ],
    prewrite_checks=[
        "prewrite: inspect broken_links and link_targets before creating a new page.",
        "prewrite: if followup_search is present, run kb_search_notes for evidence before "
        "adding or changing links.",
        "prewrite: link new concept/query pages to the matching entity when scope is "
        "project-specific.",
    ],
)
