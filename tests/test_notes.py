from personal_kb_mcp.vault.notes import (
    append_provenance_trailer,
    compute_sha256,
    parse_note,
)


def test_compute_sha256_returns_stable_hex_digest() -> None:
    digest = compute_sha256("hello")

    assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_parse_note_separates_raw_frontmatter_from_body() -> None:
    note = parse_note("---\ntitle: Today\n---\nBody text\n")

    assert note.frontmatter == "title: Today"
    assert note.body == "Body text\n"


def test_parse_note_treats_plain_markdown_as_body_only() -> None:
    note = parse_note("# Heading\nBody\n")

    assert note.frontmatter is None
    assert note.body == "# Heading\nBody\n"


def test_append_provenance_trailer_adds_machine_readable_comment() -> None:
    source_hash = compute_sha256("source")

    updated = append_provenance_trailer(
        "Body text",
        source_hash=source_hash,
        operation="write_note",
        actor="tester",
    )

    assert updated.startswith("Body text\n")
    assert f"source_hash={source_hash}" in updated
    assert "operation=write_note" in updated
    assert "actor=tester" in updated
    assert updated.endswith("-->\n")
