from common.model import FrozenModel
from vault.service.command.context_command import ContextCommand, ContextMode


class ContextRequest(FrozenModel):
    query: str
    mode: ContextMode = "prompt"
    limit: int = 16
    path_prefix: str | None = None

    def to_command(self) -> ContextCommand:
        return ContextCommand(
            query=self.query,
            mode=self.mode,
            limit=self.limit,
            path_prefix=self.path_prefix,
        )
