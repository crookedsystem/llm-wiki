from common.model import FrozenModel


class GitPushResult(FrozenModel):
    committed: bool
    commit_hash: str | None
    pushed: bool
    remote: str
    branch: str
    push_tool: str
    push_command: str
