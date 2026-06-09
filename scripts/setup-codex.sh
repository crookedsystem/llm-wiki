#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv or run: python3 scripts/setup_agents.py codex $*" >&2
  exit 1
fi

exec uv run python scripts/setup_agents.py codex "$@"
