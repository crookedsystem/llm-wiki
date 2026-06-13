from common.model import FrozenModel
from vault.service.result.git_push_result import GitPushResult


class GitPushResponse(FrozenModel):
    committed: bool
    commit_hash: str | None
    pushed: bool
    remote: str
    branch: str
    push_tool: str
    push_command: str


def git_push_response(result: GitPushResult) -> GitPushResponse:
    return GitPushResponse(
        committed=result.committed,
        commit_hash=result.commit_hash,
        pushed=result.pushed,
        remote=result.remote,
        branch=result.branch,
        push_tool=result.push_tool,
        push_command=result.push_command,
    )
