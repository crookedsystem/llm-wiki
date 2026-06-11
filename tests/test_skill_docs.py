from pathlib import Path


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("project root not found")


PROJECT_ROOT = _project_root()
SKILL = PROJECT_ROOT / "skills" / "llm-wiki" / "SKILL.md"


def test_llm_wiki_skill_embeds_content_modeling_guidance() -> None:
    content = SKILL.read_text(encoding="utf-8")

    required_fragments = [
        "## Content model and page types",
        "| `entity` | `entities/` |",
        "| `concept` | `concepts/` |",
        "## SCHEMA.md bootstrap",
        "## index.md structure",
        "## log.md structure",
        "## Concrete examples",
        "## MCP context-first workflow",
        "SCHEMA.md` is not documentation; it is the write contract",
        "Raw write contract",
        "kb_validate_vault",
        "kb_reconcile_taxonomy",
        "## Write-time graph maintenance",
        "build a write set from `wiki_map`, `issue_candidates`, and `update_suggestions`",
        "## Entity update policy",
        "Entity pages are canonical profiles, not one-source summaries.",
        "## Adding an entity page",
        "Read `entities` from `kb_wiki_context`",
        "Create `entities/<stable-slug>.md` only after identity resolution",
        "## Broken-link self-repair policy",
        "`broken_wikilink`: if a canonical target exists",
        "Do not use `kb_reconcile_taxonomy` for link repair",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_llm_wiki_skill_explains_hash_and_hook_rules() -> None:
    content = SKILL.read_text(encoding="utf-8")

    provenance_trailer = (
        "<!-- kb-provenance: source_hash=<sha256-of-content-before-trailer>; "
        "operation=write_note; actor=llm-wiki -->"
    )
    required_fragments = [
        provenance_trailer,
        "For the next update, pass `content_hash` as `if_hash`, not `source_hash`.",
        "MCP-only mode",
        "UserPromptSubmit",
        "Stop",
        "Hook-driven always-on usage",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_docs_do_not_keep_legacy_personal_kb_names() -> None:
    legacy_fragments = [
        "personal-kb-mcp",
        "personal-kb",
        "personal_kb",
        "Personal KB",
        "KB MCP",
    ]
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "README.ko.md",
        PROJECT_ROOT / "README.zh.md",
        PROJECT_ROOT / "README.ja.md",
        PROJECT_ROOT / "skills",
        PROJECT_ROOT / "mcp",
        PROJECT_ROOT / "scripts",
    ]
    text_suffixes = {".json", ".md", ".py", ".sh", ".toml", ".yaml", ".yml"}

    files: list[Path] = []
    for root in scan_roots:
        if root.is_file():
            files.append(root)
            continue
        files.extend(path for path in root.rglob("*") if path.suffix in text_suffixes)

    for path in files:
        content = path.read_text(encoding="utf-8")
        for fragment in legacy_fragments:
            assert fragment not in content, (
                f"{fragment!r} found in {path.relative_to(PROJECT_ROOT)}"
            )
