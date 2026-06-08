from personal_kb_mcp.domain.vault.entity.vault_note import (
    append_provenance_trailer,
    compute_sha256,
    parse_note,
)


def test_sha256은_같은_본문에_항상_같은_hex_digest를_반환한다() -> None:
    # Given: hash를 계산할 markdown 본문이 있다.
    content = "hello"

    # When: SHA-256 digest를 계산한다.
    digest = compute_sha256(content)

    # Then: 안정적인 64자리 hex digest가 반환된다.
    assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_note_parser는_frontmatter와_body를_분리한다() -> None:
    # Given: YAML frontmatter와 markdown body가 함께 있는 note가 있다.
    raw_note = "---\ntitle: Today\n---\nBody text\n"

    # When: note를 parse한다.
    note = parse_note(raw_note)

    # Then: frontmatter 원문과 body가 분리된다.
    assert note.frontmatter == "title: Today"
    assert note.body == "Body text\n"


def test_note_parser는_frontmatter가_없는_markdown을_body로만_처리한다() -> None:
    # Given: frontmatter 없이 heading과 본문만 있는 markdown이 있다.
    raw_note = "# Heading\nBody\n"

    # When: note를 parse한다.
    note = parse_note(raw_note)

    # Then: frontmatter는 없고 전체 markdown이 body로 유지된다.
    assert note.frontmatter is None
    assert note.body == "# Heading\nBody\n"


def test_provenance_trailer는_machine_readable_comment를_추가한다() -> None:
    # Given: 원본 본문 hash, operation, actor가 있다.
    source_hash = compute_sha256("source")

    # When: provenance trailer를 본문에 추가한다.
    updated = append_provenance_trailer(
        "Body text",
        source_hash=source_hash,
        operation="write_note",
        actor="tester",
    )

    # Then: source_hash, operation, actor가 HTML comment로 남는다.
    assert updated.startswith("Body text\n")
    assert f"source_hash={source_hash}" in updated
    assert "operation=write_note" in updated
    assert "actor=tester" in updated
    assert updated.endswith("-->\n")
