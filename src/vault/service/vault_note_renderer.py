from typing import TypeAlias

from common.model import FrozenModel
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.note_timestamp import format_note_timestamp

FrontmatterValue: TypeAlias = str | bool | tuple[str, ...] | None


class VaultNoteRenderer(FrozenModel):
    """Render a structured write command into Markdown before provenance is appended."""

    def render(self, command: WriteNoteCommand) -> str:
        frontmatter = self._render_frontmatter(
            {
                "title": command.title,
                "created": format_note_timestamp(command.created),
                "updated": format_note_timestamp(command.updated),
                "type": command.type,
                "tags": command.tags,
                "sources": command.sources,
                "confidence": command.confidence,
                "contested": command.contested,
            }
        )
        return f"---\n{frontmatter}---\n\n# {command.title}\n\n{command.body}\n"

    def _render_frontmatter(self, fields: dict[str, FrontmatterValue]) -> str:
        lines: list[str] = []
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, tuple):
                lines.extend(self._render_yaml_list(key, value))
                continue
            lines.append(f"{key}: {self._render_yaml_scalar(value)}")
        return "\n".join(lines) + "\n"

    def _render_yaml_list(self, key: str, values: tuple[str, ...]) -> list[str]:
        if not values:
            return [f"{key}: []"]
        lines = [f"{key}:"]
        lines.extend(f"  - {self._render_yaml_scalar(value)}" for value in values)
        return lines

    def _render_yaml_scalar(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value)
        if self._is_plain_yaml_scalar(text):
            return text
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _is_plain_yaml_scalar(self, value: str) -> bool:
        if not value:
            return False
        forbidden = set(":#[]{}&,*!?|>'\"%@`")
        if value[0].isspace() or value[-1].isspace() or value[0] in "-?":
            return False
        return not any(char in forbidden for char in value)
