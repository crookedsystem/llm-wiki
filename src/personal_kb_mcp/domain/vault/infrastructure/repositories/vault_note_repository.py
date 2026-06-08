from dataclasses import dataclass, field
from pathlib import Path

from personal_kb_mcp.domain.vault.entity.vault_path import DEFAULT_DENIED_NAMES, VaultPathError


@dataclass(frozen=True)
class VaultNoteRepository:
    """Filesystem repository for Markdown notes stored under one vault root."""

    root: Path
    denied_names: frozenset[str] = field(default_factory=lambda: DEFAULT_DENIED_NAMES)

    @property
    def vault_root(self) -> Path:
        return self.root.expanduser().resolve()

    def resolve_search_root(self, path_prefix: str | None) -> Path:
        root = self.vault_root
        if path_prefix is None or path_prefix.strip() in {"", "."}:
            return root

        relative_prefix = Path(path_prefix)
        if relative_prefix.is_absolute():
            raise VaultPathError("path_prefix must be relative to the vault")

        resolved_prefix = (root / relative_prefix).resolve()
        try:
            resolved_prefix.relative_to(root)
        except ValueError as error:
            raise VaultPathError(f"path_prefix escapes outside vault: {resolved_prefix}") from error

        if self.uses_denied_directory(resolved_prefix):
            raise VaultPathError("path_prefix uses denied vault directory")
        return resolved_prefix

    def markdown_notes(self, search_root: Path | None = None) -> list[Path]:
        root = self.vault_root
        resolved_search_root = search_root or root
        if not resolved_search_root.exists():
            return []
        if resolved_search_root.is_file():
            candidates = [resolved_search_root] if resolved_search_root.suffix == ".md" else []
        else:
            candidates = list(resolved_search_root.rglob("*.md"))
        return sorted(
            path
            for candidate in candidates
            if (path := self.searchable_note(candidate)) is not None
        )

    def searchable_note(self, candidate: Path) -> Path | None:
        if not candidate.is_file():
            return None
        root = self.vault_root
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(root)
        except ValueError:
            return None
        if self.uses_denied_directory(resolved_candidate):
            return None
        return resolved_candidate

    def read_note(self, note_path: Path) -> str:
        return note_path.read_text(encoding="utf-8")

    def relative_path(self, note_path: Path) -> str:
        return note_path.relative_to(self.vault_root).as_posix()

    def total_bytes(self, note_paths: list[Path]) -> int:
        return sum(path.stat().st_size for path in note_paths)

    def uses_denied_directory(self, path: Path) -> bool:
        return any(part in self.denied_names for part in path.relative_to(self.vault_root).parts)
