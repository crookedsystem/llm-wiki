from common.model import FrozenModel
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.result.context_result import ContextResult
from vault.service.vault_context_graph_builder import VaultContextGraphBuilder
from vault.service.vault_context_spec import ENTITY_GUIDANCE, USAGE_BY_MODE


class VaultContextService(FrozenModel):
    note_repository: VaultNoteRepository

    def context(self, command: ContextCommand) -> ContextResult:
        graph = VaultContextGraphBuilder(note_repository=self.note_repository).build_graph(command)
        count = (
            len(graph.orientation)
            + len(graph.broken_links)
            + len(graph.link_targets)
            + len(graph.suggested_links)
        )

        return ContextResult(
            query=command.query,
            mode=command.mode,
            count=count,
            usage=list(USAGE_BY_MODE[command.mode]),
            entity_guidance=ENTITY_GUIDANCE,
            orientation=graph.orientation,
            broken_links=graph.broken_links,
            link_targets=graph.link_targets,
            suggested_links=graph.suggested_links,
        )
