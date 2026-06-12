from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prompts.installer import HOOK_SCRIPT_TEMPLATE, HOOKS_README_TEMPLATE

from setup_support.config import ResolvedConfig, stable_repo_root

CONTEXT_HOOK_NAME = "llm-wiki-context-hook.sh"
STOP_HOOK_NAME = "llm-wiki-stop-hook.sh"


@dataclass(frozen=True)
class HookInstallResult:
    context_hook: Path
    stop_hook: Path
    settings_path: Path | None = None
    settings_changed: bool = False


def install_agent_hooks(config: ResolvedConfig) -> HookInstallResult | None:
    if not config.install_hooks:
        print("LLM Wiki hook setup disabled; skipping agent hook installation.")
        return None

    hooks_dir = hooks_dir_for_agent(config)
    context_hook = hooks_dir / CONTEXT_HOOK_NAME
    stop_hook = hooks_dir / STOP_HOOK_NAME
    if config.dry_run:
        print(f"[dry-run] install LLM Wiki hooks into {hooks_dir}")
    else:
        hooks_dir.mkdir(parents=True, exist_ok=True)
        context_hook.write_text(render_hook_script(config, mode="context"), encoding="utf-8")
        stop_hook.write_text(
            render_hook_script(
                config,
                mode="stop",
                # Claude Code and Codex share the same Stop-hook schema, so both consume the
                # decision=block JSON. Hermes only exposes finalize-style session hooks (no
                # re-prompt), so it gets the plain-text reason instead.
                extra_args=["--block-json"] if config.agent in {"claude", "codex"} else [],
            ),
            encoding="utf-8",
        )
        context_hook.chmod(0o755)
        stop_hook.chmod(0o755)
        write_hooks_readme(config, hooks_dir, context_hook, stop_hook)

    settings_changed = False
    settings_path: Path | None = None
    if config.agent == "claude":
        settings_path = config.claude_settings_path
        settings_changed = merge_claude_hook_settings(
            settings_path=settings_path,
            context_command=str(context_hook),
            stop_command=str(stop_hook),
            dry_run=config.dry_run,
        )
    elif config.agent == "codex":
        settings_path = config.codex_hooks_json_path
        settings_changed = merge_codex_hook_settings(
            settings_path=settings_path,
            context_command=str(context_hook),
            stop_command=str(stop_hook),
            dry_run=config.dry_run,
        )
    elif config.agent == "hermes":
        print(
            "Installed reusable LLM Wiki hook commands for hermes. Hermes exposes only "
            "finalize-style session hooks (on_session_end/on_session_finalize/subagent_stop) "
            "without Claude-style Stop re-prompting, so wire these scripts into a Hermes "
            "plugin/wrapper or finalize hook for an out-of-loop update pass."
        )

    return HookInstallResult(
        context_hook=context_hook,
        stop_hook=stop_hook,
        settings_path=settings_path,
        settings_changed=settings_changed,
    )


def hooks_dir_for_agent(config: ResolvedConfig) -> Path:
    if config.agent == "claude":
        return config.claude_hooks_dir
    if config.agent == "codex":
        return config.codex_hooks_dir
    return config.hermes_hooks_dir


def render_hook_script(
    config: ResolvedConfig,
    *,
    mode: str,
    extra_args: list[str] | None = None,
) -> str:
    # Only the path baked into the hook (uv --project + helper) must survive
    # worktree churn, so resolve the stable main worktree here. `.env` and skill
    # sources deliberately stay on config.repo_root (the invoking checkout).
    hook_repo_root = stable_repo_root(config.repo_root)
    helper = hook_repo_root / "scripts" / "agent_hooks" / "llm_wiki_agent_hook.py"
    rendered_extra = " ".join(shlex.quote(arg) for arg in (extra_args or []))
    if rendered_extra:
        rendered_extra = f" {rendered_extra}"

    return HOOK_SCRIPT_TEMPLATE.format(
        server_name=shlex.quote(config.server_name),
        server_url=shlex.quote(config.server_url),
        repo_root=shlex.quote(str(hook_repo_root)),
        helper=shlex.quote(str(helper)),
        mode=shlex.quote(mode),
        extra=rendered_extra,
    )


def write_hooks_readme(
    config: ResolvedConfig,
    hooks_dir: Path,
    context_hook: Path,
    stop_hook: Path,
) -> None:
    readme = hooks_dir / "README.md"
    readme.write_text(
        HOOKS_README_TEMPLATE.format(
            agent=config.agent,
            repo_root=config.repo_root,
            context_hook=context_hook,
            stop_hook=stop_hook,
            server_name=config.server_name,
            server_url=config.server_url,
            claude_settings_path=config.claude_settings_path,
        ),
        encoding="utf-8",
    )


def merge_claude_hook_settings(
    *,
    settings_path: Path,
    context_command: str,
    stop_command: str,
    dry_run: bool,
) -> bool:
    """Merge UserPromptSubmit/Stop hooks into Claude Code's `settings.json`."""
    return merge_hook_settings_json(
        settings_path=settings_path,
        context_command=context_command,
        stop_command=stop_command,
        dry_run=dry_run,
        label="Claude",
    )


def merge_codex_hook_settings(
    *,
    settings_path: Path,
    context_command: str,
    stop_command: str,
    dry_run: bool,
) -> bool:
    """Merge UserPromptSubmit/Stop hooks into Codex's `hooks.json`.

    Codex (2026+) shares Claude Code's hook JSON schema — same `hooks` object, event
    names, command shape, and decision=block Stop semantics — so the merge logic is
    identical; only the destination file differs.
    """
    return merge_hook_settings_json(
        settings_path=settings_path,
        context_command=context_command,
        stop_command=stop_command,
        dry_run=dry_run,
        label="Codex",
    )


def merge_hook_settings_json(
    *,
    settings_path: Path,
    context_command: str,
    stop_command: str,
    dry_run: bool,
    label: str,
) -> bool:
    settings = load_json_object(settings_path, label=label)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks

    changed = False
    changed |= ensure_hook_command(
        hooks,
        event="UserPromptSubmit",
        command=context_command,
        timeout=5,
    )
    changed |= ensure_hook_command(
        hooks,
        event="Stop",
        command=stop_command,
        timeout=10,
    )

    if changed:
        if dry_run:
            print(f"[dry-run] merge {label} LLM Wiki hooks into {settings_path}")
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Merged {label} LLM Wiki hooks into {settings_path}.")
    else:
        print(f"{label} LLM Wiki hooks already exist in {settings_path}; not duplicating.")
    return changed


def load_json_object(path: Path, *, label: str = "Hook settings") -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot parse {label} settings JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} settings must be a JSON object: {path}")
    return parsed


def ensure_hook_command(
    hooks: dict[str, Any],
    *,
    event: str,
    command: str,
    timeout: int,
) -> bool:
    event_entries = hooks.setdefault(event, [])
    if not isinstance(event_entries, list):
        event_entries = []
        hooks[event] = event_entries

    if hook_command_exists(event_entries, command):
        return False

    event_entries.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": timeout,
                }
            ]
        }
    )
    return True


def hook_command_exists(entries: list[Any], command: str) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook_items = entry.get("hooks")
        if not isinstance(hook_items, list):
            continue
        for hook in hook_items:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False
