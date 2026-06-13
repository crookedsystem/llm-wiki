from datetime import UTC, datetime

from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_note_renderer import VaultNoteRenderer


def _write_command(
    *,
    title: str = "Today",
    body: str = "## Summary\nBody text",
    tags: tuple[str, ...] = ("agent-memory",),
    sources: tuple[str, ...] = ("raw/articles/source.md",),
    contested: bool | None = False,
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path="concepts/today.md",
        title=title,
        type="concept",
        tags=tags,
        sources=sources,
        body=body,
        created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
        updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        confidence="medium",
        contested=contested,
    )


def test_note_renderer는_structured_command를_markdown_note로_렌더링한다() -> None:
    # Given: frontmatter로 렌더링할 structured write command가 있다.
    command = _write_command()

    # When: Markdown note를 렌더링한다.
    rendered = VaultNoteRenderer().render(command)

    # Then: YAML frontmatter, title heading, body가 정해진 순서로 조립된다.
    assert rendered == (
        "---\n"
        "title: Today\n"
        'created: "2026-06-12T09:30:45Z"\n'
        'updated: "2026-06-12T10:31:46Z"\n'
        "type: concept\n"
        "tags:\n"
        "  - agent-memory\n"
        "sources:\n"
        "  - raw/articles/source.md\n"
        "confidence: medium\n"
        "contested: false\n"
        "---\n\n"
        "# Today\n\n"
        "## Summary\n"
        "Body text\n"
    )


def test_note_renderer는_yaml_scalar를_필요할_때만_quote한다() -> None:
    # Given: YAML plain scalar로 안전하지 않은 문자와 boolean 생략 케이스가 있다.
    command = _write_command(
        title='Title: "Quoted"',
        tags=("agent-memory", "needs:quote"),
        contested=None,
    )

    # When: Markdown note를 렌더링한다.
    rendered = VaultNoteRenderer().render(command)

    # Then: frontmatter scalar는 quote/escape되고 None 필드는 출력되지 않는다.
    assert 'title: "Title: \\"Quoted\\""' in rendered
    assert '  - "needs:quote"\n' in rendered
    assert "contested:" not in rendered
    assert '# Title: "Quoted"\n' in rendered
